import asyncio
import json
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from interview_copilot.app import create_app
from interview_copilot.models import AnalysisPacket, ResearchPacket


class FakeRuntime:
    available = True
    model = "openai/test"

    def __init__(self) -> None:
        self.last_analysis_request = None

    async def analyze(self, request):
        self.last_analysis_request = request
        return AnalysisPacket(engine="openai")

    async def report(self, request):
        raise RuntimeError("offline")

    async def close(self):
        return None


class FakeTranscriber:
    available = True
    model = "/tmp/ggml-test.bin"
    language = "en"

    def transcribe(self, audio: bytes, suffix: str) -> str:
        assert audio == b"audio"
        assert suffix == ".webm"
        return "A clear transcript"


def test_health_reports_local_capabilities() -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber())) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["agent"]["model"] == "openai/test"
    assert response.json()["transcription"]["available"] is True


def test_default_and_validation_configuration_endpoints() -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber())) as client:
        default = client.get("/api/config/default")
        invalid = default.json()
        invalid["unknown"] = True
        validation = client.post("/api/config/validate", json=invalid)

    assert default.status_code == 200
    assert default.json()["schema_version"] == 1
    assert validation.status_code == 422
    assert validation.json()["detail"][0]["type"] == "extra_forbidden"


def test_transcribe_upload_is_durable(tmp_path: Path) -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber(), archive_root=tmp_path)) as client:
        response = client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
            data={
                "session_id": "cofounder-session",
                "sequence": "7",
                "speaker": "Interviewer",
                "elapsed_seconds": "42",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"text": "A clear transcript"}
    directory = tmp_path / "cofounder-session"
    audio_files = list((directory / "audio").glob("*.webm"))
    assert len(audio_files) == 1
    assert audio_files[0].read_bytes() == b"audio"
    record = json.loads((directory / "transcript.jsonl").read_text().strip())
    assert record["text"] == "A clear transcript"
    assert record["speaker"] == "Interviewer"
    assert record["elapsed_seconds"] == 42
    assert "**[00:42] Interviewer:** A clear transcript" in (directory / "transcript.md").read_text()


class FailingTranscriber(FakeTranscriber):
    def transcribe(self, audio: bytes, suffix: str) -> str:
        raise ValueError("decoder failed")


def test_audio_is_saved_when_whisper_fails(tmp_path: Path) -> None:
    with TestClient(create_app(FakeRuntime(), FailingTranscriber(), archive_root=tmp_path)) as client:
        response = client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
            data={"session_id": "failed-session", "sequence": "1"},
        )
    assert response.status_code == 422
    directory = tmp_path / "failed-session"
    assert next((directory / "audio").glob("*.webm")).read_bytes() == b"audio"
    record = json.loads((directory / "transcript.jsonl").read_text().strip())
    assert record["status"] == "error"
    assert "decoder failed" in record["error"]


def test_analysis_uses_live_runtime() -> None:
    runtime = FakeRuntime()
    with TestClient(create_app(runtime, FakeTranscriber())) as client:
        response = client.post(
            "/api/analyze",
            json={
                "transcript": [
                    {"id": "turn-1", "speaker": "Participant", "text": "This is difficult."}
                ]
            },
        )
    assert response.status_code == 200
    assert response.json()["engine"] == "openai"
    assert runtime.last_analysis_request.configuration.schema_version == 1


def test_report_falls_back_and_freezes_numbered_html(tmp_path: Path) -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber(), archive_root=tmp_path)) as client:
        response = client.post(
            "/api/report",
            json={
                "session_id": "report-session",
                "transcript": [
                    {"id": "turn-1", "speaker": "Participant", "text": "This is difficult."}
                ],
                "evidence": [],
            },
        )
        second = client.post(
            "/api/report",
            json={
                "session_id": "second-report-session",
                "transcript": [
                    {"id": "turn-2", "speaker": "Participant", "text": "This is still difficult."}
                ],
                "evidence": [],
            },
        )
        saved = client.get("/api/reports/1")
        html = client.get("/reports/1")
        index = client.get("/reports")
    assert response.status_code == 200
    assert response.json()["engine"] == "local"
    assert "RuntimeError" in response.json()["notice"]
    assert response.json()["report_id"] == 1
    assert response.json()["html_url"] == "/reports/1"
    assert any(item["type"] == "insight" for item in response.json()["evidence"])
    assert second.json()["report_id"] == 2
    assert saved.json()["session_id"] == "report-session"
    assert "Full conversation transcript" in html.text
    assert "This is difficult." in html.text
    assert "Report 001" in index.text
    assert (tmp_path / "reports" / "000001" / "report.json").is_file()
    assert (tmp_path / "reports" / "000001" / "report.html").is_file()


def test_session_stores_frozen_configuration_before_audio(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    with TestClient(create_app(runtime, FakeTranscriber(), archive_root=tmp_path)) as client:
        configuration = client.get("/api/config/default").json()
        configuration["template"]["name"] = "Frozen interview"
        started = client.post("/api/interviews/start", json={
            "session_id": "frozen-session",
            "configuration": configuration,
            "mode": "live",
        })
        configuration["template"]["name"] = "Edited later"
        transcribed = client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
            data={"session_id": "frozen-session", "sequence": "1"},
        )

    assert started.status_code == 200
    assert transcribed.status_code == 200
    archived = yaml.safe_load((tmp_path / "frozen-session" / "configuration.yaml").read_text())
    assert archived["template"]["name"] == "Frozen interview"
    metadata = json.loads((tmp_path / "frozen-session" / "session.json").read_text())
    assert metadata["schema_version"] == 1
    assert metadata["model"] == "openai/gpt-5.6-sol"
    assert metadata["whisper"]["active_model"] == "/tmp/ggml-test.bin"


def test_session_can_disable_raw_audio_persistence(tmp_path: Path) -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber(), archive_root=tmp_path)) as client:
        configuration = client.get("/api/config/default").json()
        configuration["audio"]["persist_raw_audio"] = False
        client.post("/api/interviews/start", json={
            "session_id": "no-audio",
            "configuration": configuration,
            "mode": "live",
        })
        response = client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
            data={"session_id": "no-audio", "sequence": "1"},
        )

    assert response.status_code == 200
    assert not (tmp_path / "no-audio" / "audio").exists()
    record = json.loads((tmp_path / "no-audio" / "transcript.jsonl").read_text())
    assert record["audio_file"] is None


class SlowResearchCoordinator:
    class Provider:
        available = True

    provider = Provider()

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run(self, request) -> ResearchPacket:
        self.started.set()
        await self.release.wait()
        return ResearchPacket(revision=request.revision)


@pytest.mark.asyncio
async def test_transcription_continues_while_research_is_running(tmp_path: Path) -> None:
    research = SlowResearchCoordinator()
    app = create_app(
        FakeRuntime(),
        FakeTranscriber(),
        archive_root=tmp_path,
        research_coordinator=research,  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        research_task = asyncio.create_task(client.post("/api/research", json={
            "session_id": "parallel-session",
            "revision": 1,
            "transcript": [{
                "id": "turn-1",
                "speaker": "Participant",
                "text": "There are no events for meeting locals.",
            }],
        }))
        await asyncio.wait_for(research.started.wait(), timeout=1)

        transcription = await client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
            data={"session_id": "parallel-session", "sequence": "1"},
        )

        assert transcription.status_code == 200
        assert research_task.done() is False
        research.release.set()
        assert (await research_task).status_code == 200
