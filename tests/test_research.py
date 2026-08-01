import asyncio

import pytest
from pydantic import ValidationError

from interview_copilot.models import ResearchCard, ResearchRequest, TranscriptTurn
from interview_copilot.research import (
    ResearchCoordinator,
    ResearchDraft,
    ResearchTrigger,
    SearchDocument,
    detect_research_trigger,
    validate_drafts,
)


def request_for(text: str, *, revision: int = 1, mode: str = "live") -> ResearchRequest:
    return ResearchRequest(
        session_id="research-session",
        revision=revision,
        mode=mode,
        transcript=[TranscriptTurn(id=f"turn-{revision}", speaker="Participant", text=text)],
    )


@pytest.mark.parametrize(
    "text",
    [
        "There are no events for meeting local people here.",
        "I tried the Chiang Mai Smart City program last month.",
        "I visited Punspace for their community event yesterday.",
        "Chiang Mai needs one central smart city data platform.",
    ],
)
def test_high_value_claims_trigger_research(text: str) -> None:
    assert detect_research_trigger(request_for(text)) is not None


def test_mundane_story_does_not_trigger_research() -> None:
    request = request_for("I went for coffee with a friend yesterday.")
    assert detect_research_trigger(request) is None


def test_research_card_requires_a_source_url() -> None:
    with pytest.raises(ValidationError):
        ResearchCard.model_validate({
            "id": "research_missing",
            "signal": "A factual claim.",
            "ask_next": "What happened next?",
            "why_now": "There are no events.",
            "judge_lens": "Real",
            "source_title": "Missing source",
            "source_date": None,
            "confidence": 0.8,
            "related_evidence_ids": [],
        })


def test_validation_rejects_invented_urls_and_deduplicates_semantics() -> None:
    documents = [
        SearchDocument(
            title="Official city plan",
            url="https://example.org/plan",
            published="2026-07-01",
            content="The city plan includes a shared city data platform for public services.",
        ),
        SearchDocument(
            title="Second city plan",
            url="https://example.org/second",
            published=None,
            content="The city plan includes a shared city data platform for public services.",
        ),
    ]
    trigger = ResearchTrigger(
        text="We need one central platform.",
        turn_id="turn-1",
        related_evidence_ids=("evidence-1",),
        kind="existing_solution_check",
        query="city platform",
    )
    base = {
        "signal": "The official plan already includes a shared city data platform.",
        "ask_next": "Is the gap availability, awareness, trust, or implementation?",
        "judge_lens": "New",
        "confidence": 0.91,
        "supporting_excerpt": "includes a shared city data platform",
    }
    drafts = [
        ResearchDraft(**base, source_url="https://invented.example/result"),
        ResearchDraft(**base, source_url="https://example.org/plan"),
        ResearchDraft(**base, source_url="https://example.org/second"),
        ResearchDraft(**base, source_url="https://example.org/plan/"),
    ]

    cards = validate_drafts(drafts, documents, trigger)

    assert len(cards) == 1
    assert str(cards[0].source_url).rstrip("/") == "https://example.org/plan"
    assert cards[0].related_evidence_ids == ["evidence-1"]


class OfflineProvider:
    available = False

    async def search(self, query: str) -> list[SearchDocument]:
        raise AssertionError("disabled provider must not be called")


class FakeRuntime:
    available = True

    async def research(self, request, trigger, documents):
        return []


class CountingProvider:
    available = True

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str) -> list[SearchDocument]:
        self.calls += 1
        return [
            SearchDocument(
                title="Source",
                url="https://example.org/source",
                published=None,
                content="Events connect local people with remote workers.",
            )
        ]


@pytest.mark.asyncio
async def test_offline_search_returns_no_cards() -> None:
    coordinator = ResearchCoordinator(FakeRuntime(), OfflineProvider(), cooldown_seconds=0)
    packet = await coordinator.run(request_for("There are no events for meeting locals."))
    assert packet.cards == []
    assert packet.stale is False


@pytest.mark.asyncio
async def test_semantically_duplicate_queries_search_once() -> None:
    provider = CountingProvider()
    coordinator = ResearchCoordinator(FakeRuntime(), provider, cooldown_seconds=0)
    await coordinator.run(request_for("There are no events for meeting locals.", revision=1))
    await coordinator.run(request_for("There are no events for meeting locals!", revision=2))
    assert provider.calls == 1


class WaitingProvider:
    available = True

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(self, query: str) -> list[SearchDocument]:
        self.started.set()
        await self.release.wait()
        return [
            SearchDocument(
                title="Meetup listing",
                url="https://example.org/meetup",
                published=None,
                content="Events connect Chiang Mai local people and remote workers.",
            )
        ]


@pytest.mark.asyncio
async def test_stale_research_result_is_suppressed() -> None:
    provider = WaitingProvider()
    coordinator = ResearchCoordinator(FakeRuntime(), provider, cooldown_seconds=0)
    first = asyncio.create_task(
        coordinator.run(request_for("There are no events for meeting locals.", revision=1))
    )
    await provider.started.wait()

    mundane = await coordinator.run(
        request_for("I went for coffee with a friend yesterday.", revision=2)
    )
    provider.release.set()
    stale = await first

    assert mundane.cards == []
    assert stale.cards == []
    assert stale.stale is True


@pytest.mark.asyncio
async def test_demo_research_is_deterministic_and_needs_no_provider() -> None:
    coordinator = ResearchCoordinator(FakeRuntime(), OfflineProvider(), cooldown_seconds=0)
    first = await coordinator.run(
        request_for("There are no events where nomads meet locals.", mode="demo")
    )
    second_request = request_for(
        "There are no events where nomads meet locals.", revision=2, mode="demo"
    )
    second = await coordinator.run(second_request)

    assert first.cards[0].id == second.cards[0].id
    assert first.cards[0].ask_next.endswith("?")
    assert str(first.cards[0].source_url).startswith("https://www.meetup.com/")
