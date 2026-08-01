import json

import pytest

from interview_copilot.configuration import get_default_configuration
from interview_copilot.models import (
    AnalysisRequest,
    InterviewConfiguration,
    ResearchRequest,
    TranscriptTurn,
)
from interview_copilot.opencode_runtime import OpenCodeRuntime
from interview_copilot.research import ResearchTrigger, SearchDocument


def test_json_object_tolerates_markdown_fence() -> None:
    payload = OpenCodeRuntime._json_object('```json\n{"suggestions": [], "evidence": []}\n```')
    assert payload == {"suggestions": [], "evidence": []}


@pytest.mark.asyncio
async def test_runtime_validates_structured_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = OpenCodeRuntime()

    async def fake_prompt(system: str, prompt: str, model: str) -> str:
        assert "shared evidence pool" in system
        assert "Depth protocol for every interview phase" in system
        assert "desired outcome" in system
        assert "turn-1" in prompt
        assert model == "openai/gpt-5.6-sol"
        return '{"suggestions": [], "evidence": []}'

    monkeypatch.setattr(runtime, "_prompt", fake_prompt)
    result = await runtime.analyze(
        AnalysisRequest(
            transcript=[TranscriptTurn(id="turn-1", speaker="Participant", text="It takes a day.")]
        )
    )
    assert result.engine == "openai"


@pytest.mark.asyncio
async def test_runtime_uses_request_prompts_lenses_and_context_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = OpenCodeRuntime()
    payload = get_default_configuration().model_dump()
    payload["copilot"]["system_prompt"] = "CUSTOM SYSTEM"
    payload["copilot"]["task_prompt"] = "CUSTOM TASK"
    payload["copilot"]["limits"]["transcript_turns"] = 1
    payload["copilot"]["limits"]["suggestions"] = 1
    payload["copilot"]["lenses"]["research"] = False
    payload["runtime"]["model"] = "openai/request-model"
    configuration = InterviewConfiguration.model_validate(payload)

    async def fake_prompt(system: str, prompt: str, model: str) -> str:
        assert system.startswith("CUSTOM SYSTEM")
        assert "Research" not in system.split("Enabled specialist lenses:", 1)[1].split(".", 1)[0]
        assert prompt.startswith("CUSTOM TASK")
        assert "turn-old" not in prompt
        assert "turn-new" in prompt
        assert model == "openai/request-model"
        return json.dumps({
            "suggestions": [
                {
                    "id": "research",
                    "agent": "Research",
                    "kind": "research",
                    "text": "Search externally",
                    "rationale": "Named tool",
                    "evidence_ids": [],
                    "priority": "medium",
                },
                {
                    "id": "clarify",
                    "agent": "Clarification",
                    "kind": "question",
                    "text": "How often?",
                    "rationale": "Missing frequency",
                    "evidence_ids": [],
                    "priority": "high",
                },
            ],
            "evidence": [],
        })

    monkeypatch.setattr(runtime, "_prompt", fake_prompt)
    result = await runtime.analyze(AnalysisRequest(
        transcript=[
            TranscriptTurn(id="turn-old", speaker="Participant", text="An old detail."),
            TranscriptTurn(id="turn-new", speaker="Participant", text="A new detail."),
        ],
        configuration=configuration,
    ))

    assert [suggestion.agent for suggestion in result.suggestions] == ["Clarification"]


@pytest.mark.asyncio
async def test_runtime_builds_research_only_from_retrieved_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = OpenCodeRuntime()

    async def fake_prompt(system: str, prompt: str, model: str) -> str:
        assert "Never lecture" in system
        assert "https://example.org/official" in prompt
        assert "supporting_excerpt" in prompt
        return json.dumps({
            "cards": [{
                "signal": "An official program already runs local connection events.",
                "ask_next": "Which part of those events failed to create a meaningful connection?",
                "judge_lens": "New",
                "source_url": "https://example.org/official",
                "confidence": 0.88,
                "supporting_excerpt": "runs events for local people and remote workers",
            }]
        })

    monkeypatch.setattr(runtime, "_prompt", fake_prompt)
    request = ResearchRequest(
        session_id="session-1",
        revision=1,
        transcript=[
            TranscriptTurn(
                id="turn-1",
                speaker="Participant",
                text="There are no events for nomads to meet locals.",
            )
        ],
    )
    drafts = await runtime.research(
        request,
        ResearchTrigger(
            text=request.transcript[0].text,
            turn_id="turn-1",
            related_evidence_ids=(),
            kind="universal_or_absence_claim",
            query="events",
        ),
        [
            SearchDocument(
                title="Official program",
                url="https://example.org/official",
                published=None,
                content="The program runs events for local people and remote workers.",
            )
        ],
    )

    assert len(drafts) == 1
    assert str(drafts[0].source_url).rstrip("/") == "https://example.org/official"
