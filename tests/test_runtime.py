import pytest

from interview_copilot.models import AnalysisRequest, TranscriptTurn
from interview_copilot.opencode_runtime import OpenCodeRuntime


def test_json_object_tolerates_markdown_fence() -> None:
    payload = OpenCodeRuntime._json_object('```json\n{"suggestions": [], "evidence": []}\n```')
    assert payload == {"suggestions": [], "evidence": []}


@pytest.mark.asyncio
async def test_runtime_validates_structured_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = OpenCodeRuntime()

    async def fake_prompt(system: str, prompt: str) -> str:
        assert "shared evidence pool" in system
        assert "turn-1" in prompt
        return '{"suggestions": [], "evidence": []}'

    monkeypatch.setattr(runtime, "_prompt", fake_prompt)
    result = await runtime.analyze(
        AnalysisRequest(
            transcript=[TranscriptTurn(id="turn-1", speaker="Participant", text="It takes a day.")]
        )
    )
    assert result.engine == "openai"
