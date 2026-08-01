from fastapi.testclient import TestClient

from interview_copilot.app import create_app
from interview_copilot.models import AnalysisPacket


class FakeRuntime:
    available = True
    model = "openai/test"

    async def analyze(self, request):
        return AnalysisPacket(engine="openai")

    async def report(self, request):
        raise RuntimeError("offline")

    async def close(self):
        return None


class FakeTranscriber:
    available = True
    model = "/tmp/ggml-test.bin"

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


def test_transcribe_upload() -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber())) as client:
        response = client.post(
            "/api/transcribe",
            files={"file": ("chunk.webm", b"audio", "audio/webm")},
        )
    assert response.status_code == 200
    assert response.json() == {"text": "A clear transcript"}


def test_analysis_uses_live_runtime() -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber())) as client:
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


def test_report_falls_back_when_runtime_fails() -> None:
    with TestClient(create_app(FakeRuntime(), FakeTranscriber())) as client:
        response = client.post(
            "/api/report",
            json={
                "transcript": [
                    {"id": "turn-1", "speaker": "Participant", "text": "This is difficult."}
                ],
                "evidence": [],
            },
        )
    assert response.status_code == 200
    assert response.json()["engine"] == "local"
    assert "RuntimeError" in response.json()["notice"]
