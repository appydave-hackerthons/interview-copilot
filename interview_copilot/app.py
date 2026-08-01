"""FastAPI application for the local Interview Copilot MVP."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncIterator

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from interview_copilot.archive import InterviewArchive
from interview_copilot.configuration import get_default_configuration, resolve_archive_root
from interview_copilot.fallback import analyse_locally, build_local_report
from interview_copilot.models import (
    AnalysisPacket,
    AnalysisRequest,
    InterviewConfiguration,
    InterviewReport,
    PersistentInterviewReport,
    ReportRequest,
    ReportIndexItem,
    ResearchPacket,
    ResearchRequest,
    StartInterviewRequest,
)
from interview_copilot.opencode_runtime import OpenCodeRuntime
from interview_copilot.research import ResearchCoordinator
from interview_copilot.reports import ReportArchive, render_report_index
from interview_copilot.transcription import WhisperTranscriber

ROOT = Path(__file__).resolve().parent.parent


def create_app(
    runtime: OpenCodeRuntime | None = None,
    transcriber: WhisperTranscriber | None = None,
    archive_root: Path | None = None,
    research_coordinator: ResearchCoordinator | None = None,
) -> FastAPI:
    """Create an injectable application for production and tests."""

    agent_runtime = runtime or OpenCodeRuntime()
    research_agent = research_coordinator or ResearchCoordinator(agent_runtime)
    whisper = transcriber or WhisperTranscriber()
    default_configuration = get_default_configuration()
    fixed_archive_root = archive_root.resolve() if archive_root else None
    archives_by_root: dict[Path, InterviewArchive] = {}
    session_archives: dict[str, InterviewArchive] = {}
    session_configurations: dict[str, InterviewConfiguration] = {}

    def archive_for(configuration: InterviewConfiguration) -> InterviewArchive:
        root = fixed_archive_root or resolve_archive_root(configuration.runtime.archive_root)
        if root not in archives_by_root:
            archives_by_root[root] = InterviewArchive(root)
        return archives_by_root[root]

    default_archive = archive_for(default_configuration)
    report_archive = ReportArchive(default_archive.root)
    whisper_model = getattr(whisper, "model", None)
    whisper_language = getattr(whisper, "language", "auto")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await agent_runtime.close()

    api = FastAPI(title="Interview Copilot", version="0.2.0", lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "agent": {"available": agent_runtime.available, "model": agent_runtime.model},
            "research": {"available": research_agent.provider.available},
            "transcription": {
                "available": whisper.available,
                "model": Path(whisper_model).name if whisper_model else None,
                "model_path": whisper_model,
                "language": whisper_language,
            },
        }

    @api.get("/api/config/default", response_model=InterviewConfiguration)
    async def configuration_default() -> InterviewConfiguration:
        return default_configuration.model_copy(deep=True)

    @api.post("/api/config/validate", response_model=InterviewConfiguration)
    async def configuration_validate(payload: Annotated[dict[str, Any], Body()]) -> InterviewConfiguration:
        try:
            return InterviewConfiguration.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc

    @api.post("/api/interviews/start")
    async def start_interview(request: StartInterviewRequest) -> dict[str, str]:
        archive = archive_for(request.configuration)
        try:
            archive.start_session(
                request.session_id,
                request.configuration,
                mode=request.mode,
                active_model=request.configuration.runtime.model,
                active_whisper_model=whisper_model,
                active_whisper_language=whisper_language,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        session_archives[request.session_id] = archive
        session_configurations[request.session_id] = request.configuration.model_copy(deep=True)
        return {"session_id": request.session_id}

    @api.post("/api/analyze", response_model=AnalysisPacket)
    async def analyze(request: AnalysisRequest) -> AnalysisPacket:
        effective_request = request.model_copy(
            update={"configuration": request.effective_configuration(), "template": None}, deep=True
        )
        if effective_request.mode == "demo" or not agent_runtime.available:
            packet = analyse_locally(effective_request)
            notice = None if effective_request.mode == "demo" else "OpenAI unavailable; using local extraction."
            return packet.model_copy(update={"notice": notice})
        try:
            return await agent_runtime.analyze(effective_request)
        except Exception as exc:
            packet = analyse_locally(effective_request)
            return packet.model_copy(
                update={"notice": f"Live analysis paused; local extraction is active ({type(exc).__name__})."}
            )

    async def synthesize_report(request: ReportRequest) -> InterviewReport:
        effective_request = request.model_copy(
            update={"configuration": request.effective_configuration(), "template": None}, deep=True
        )
        if effective_request.mode == "demo" or not agent_runtime.available:
            return build_local_report(effective_request)
        try:
            return await agent_runtime.report(effective_request)
        except Exception as exc:
            fallback = build_local_report(effective_request)
            return fallback.model_copy(
                update={"notice": f"Live synthesis paused; local report is shown ({type(exc).__name__})."}
            )

    @api.post("/api/report", response_model=PersistentInterviewReport)
    async def report(request: ReportRequest) -> PersistentInterviewReport:
        """Synthesize and freeze a numbered report on the same local app origin."""

        synthesis = await synthesize_report(request)
        configuration = request.effective_configuration()
        return report_archive.save(
            session_id=request.session_id or "unassigned",
            report=synthesis,
            template=configuration.template,
            transcript=request.transcript,
            evidence=request.evidence,
        )

    @api.get("/api/reports", response_model=list[ReportIndexItem])
    async def reports_index() -> list[ReportIndexItem]:
        return report_archive.list()

    @api.get("/api/reports/{report_id}", response_model=PersistentInterviewReport)
    async def saved_report(report_id: int) -> PersistentInterviewReport:
        try:
            return report_archive.load(report_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Report not found") from exc

    @api.get("/reports", response_class=HTMLResponse)
    async def report_library() -> HTMLResponse:
        return HTMLResponse(render_report_index(report_archive.list()))

    @api.get("/reports/{report_id}", response_class=HTMLResponse)
    async def report_html(report_id: int) -> HTMLResponse:
        try:
            path = report_archive.html_path(report_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Report not found") from exc
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @api.get("/reports/{report_id}/download", response_class=FileResponse)
    async def download_report_html(report_id: int) -> FileResponse:
        try:
            path = report_archive.html_path(report_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Report not found") from exc
        return FileResponse(
            path,
            media_type="text/html",
            filename=f"interview-report-{report_id:06d}.html",
        )

    @api.post("/api/research", response_model=ResearchPacket)
    async def research(request: ResearchRequest) -> ResearchPacket:
        """Run the debounced research lane without coupling it to analysis or audio."""

        effective_request = request.model_copy(
            update={"configuration": request.effective_configuration()},
            deep=True,
        )
        try:
            return await research_agent.run(effective_request)
        except Exception:
            # Research is deliberately optional: a search outage must never
            # interrupt transcript capture, extraction, or the interview UI.
            return ResearchPacket(revision=request.revision)

    @api.post("/api/transcribe")
    async def transcribe(
        file: Annotated[UploadFile, File()],
        session_id: Annotated[str, Form()] = "unassigned",
        sequence: Annotated[int, Form()] = 0,
        speaker: Annotated[str | None, Form()] = None,
        elapsed_seconds: Annotated[int, Form()] = 0,
    ) -> dict[str, str]:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        configuration = session_configurations.get(session_id, default_configuration)
        archive = session_archives.get(session_id, default_archive)
        attributed_speaker = speaker or configuration.audio.default_speaker
        if attributed_speaker not in ("Interviewer", "Participant"):
            raise HTTPException(status_code=422, detail="Speaker must be Interviewer or Participant")
        suffix = Path(file.filename or "chunk.webm").suffix or ".webm"
        audio_path = (
            archive.save_audio(session_id, sequence, suffix, data)
            if configuration.audio.persist_raw_audio
            else None
        )
        result_fields = {
            "session_id": session_id,
            "sequence": sequence,
            "speaker": attributed_speaker,
            "elapsed_seconds": elapsed_seconds,
            "audio_path": audio_path,
        }
        if not whisper.available:
            archive.append_result(**result_fields, text=None, error="Local Whisper is not configured")
            raise HTTPException(status_code=503, detail="Local Whisper is not configured")
        try:
            text = whisper.transcribe(data, suffix)
        except (RuntimeError, OSError) as exc:
            archive.append_result(**result_fields, text=None, error=str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            archive.append_result(**result_fields, text=None, error=f"{type(exc).__name__}: {exc}")
            raise HTTPException(status_code=422, detail="Audio could not be transcribed") from exc
        archive.append_result(**result_fields, text=text)
        return {"text": text}

    dist = ROOT / "frontend/dist"
    if dist.is_dir():
        api.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return api


app = create_app()
