"""FastAPI application for the local Interview Copilot MVP."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from interview_copilot.fallback import analyse_locally, build_local_report
from interview_copilot.models import AnalysisPacket, AnalysisRequest, InterviewReport, ReportRequest
from interview_copilot.opencode_runtime import OpenCodeRuntime
from interview_copilot.transcription import WhisperTranscriber

ROOT = Path(__file__).resolve().parent.parent


def create_app(
    runtime: OpenCodeRuntime | None = None,
    transcriber: WhisperTranscriber | None = None,
) -> FastAPI:
    """Create an injectable application for production and tests."""

    agent_runtime = runtime or OpenCodeRuntime()
    whisper = transcriber or WhisperTranscriber()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await agent_runtime.close()

    api = FastAPI(title="Interview Copilot", version="0.1.0", lifespan=lifespan)
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
            "transcription": {
                "available": whisper.available,
                "model": Path(whisper.model).name if whisper.model else None,
            },
        }

    @api.post("/api/analyze", response_model=AnalysisPacket)
    async def analyze(request: AnalysisRequest) -> AnalysisPacket:
        if request.mode == "demo" or not agent_runtime.available:
            packet = analyse_locally(request)
            notice = None if request.mode == "demo" else "OpenAI unavailable; using local extraction."
            return packet.model_copy(update={"notice": notice})
        try:
            return await agent_runtime.analyze(request)
        except Exception as exc:
            packet = analyse_locally(request)
            return packet.model_copy(
                update={"notice": f"Live analysis paused; local extraction is active ({type(exc).__name__})."}
            )

    @api.post("/api/report", response_model=InterviewReport)
    async def report(request: ReportRequest) -> InterviewReport:
        if request.mode == "demo" or not agent_runtime.available:
            return build_local_report(request)
        try:
            return await agent_runtime.report(request)
        except Exception as exc:
            fallback = build_local_report(request)
            return fallback.model_copy(
                update={"notice": f"Live synthesis paused; local report is shown ({type(exc).__name__})."}
            )

    @api.post("/api/transcribe")
    async def transcribe(file: Annotated[UploadFile, File()]) -> dict[str, str]:
        if not whisper.available:
            raise HTTPException(status_code=503, detail="Local Whisper is not configured")
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        suffix = Path(file.filename or "chunk.webm").suffix or ".webm"
        try:
            text = whisper.transcribe(data, suffix)
        except (RuntimeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Audio could not be transcribed") from exc
        return {"text": text}

    dist = ROOT / "frontend/dist"
    if dist.is_dir():
        api.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return api


app = create_app()
