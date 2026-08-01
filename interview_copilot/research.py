"""Gated, source-grounded internet research for live interview follow-ups."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from interview_copilot.models import ResearchCard, ResearchPacket, ResearchRequest

logger = logging.getLogger(__name__)

UNIVERSAL_RE = re.compile(
    r"\b(?:no one|nobody|nothing|never|always|everyone|everybody|all\s+\w+|"
    r"there (?:is|are)(?:n't| not| no)|does not exist|doesn't exist|none)\b",
    re.IGNORECASE,
)
NAMED_ENTITY_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&.'’-]+(?:\s+[A-Z][A-Za-z0-9&.'’-]+)+|"
    r"[A-Z]{2,}(?:\.[A-Z]{2,})?|Google|Wise|WhatsApp|Meetup|Grab|Airbnb|"
    r"Facebook|Slack|Notion|Reddit|LINE)\b"
)
NAMED_CUE_RE = re.compile(
    r"\b(?:at|called|named|using?|tried|visited|joined|booked)\s+(?:the\s+)?"
    r"[A-Z][A-Za-z0-9&.'’-]{2,}\b"
)
CURRENT_RE = re.compile(
    r"\b(?:today|currently|now|recent(?:ly)?|this (?:week|month|year)|"
    r"open(?:ing)?|closed|available|launched|cancelled|scheduled|visa|policy|"
    r"permit|regulation|law|official|government|municipality)\b",
    re.IGNORECASE,
)
SOLUTION_RE = re.compile(
    r"\b(?:should|need(?:s)?|could)\s+(?:build|create|make|launch|have|offer)|"
    r"\b(?:one|single|central|new)\s+(?:app|platform|service|hub|database|tool)|"
    r"\bproposed solution\b",
    re.IGNORECASE,
)
CONSTRAINT_RE = re.compile(
    r"\b(?:price|cost|baht|fee|free|language|thai|english|opening|closing|hours?|"
    r"nearby|distance|location|geograph\w*|regulation|permit|eligible|eligibility|"
    r"access|accessible|wheelchair|age limit|booking|required)\b",
    re.IGNORECASE,
)
FEASIBILITY_RE = re.compile(
    r"\b(?:partner|partnership|dataset|open data|API|venue|pilot|sponsor|host|"
    r"municipality|university|association|provider)\b",
    re.IGNORECASE,
)
STAKEHOLDER_RE = re.compile(
    r"\b(?:locals?|residents?|organizers?|owners?|staff|drivers?|students?|"
    r"workers?|officials?|government|businesses|venues?|families|older people|"
    r"disabled people|migrants?)\b",
    re.IGNORECASE,
)
DEFINITION_RE = re.compile(r"^\s*(?:what (?:is|are)|define|what does .+ mean)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ResearchTrigger:
    """The exact interview item and policy reason that earned a search."""

    text: str
    turn_id: str | None
    related_evidence_ids: tuple[str, ...]
    kind: str
    query: str


@dataclass(frozen=True)
class SearchDocument:
    """A retrieved source with enough text to validate a factual signal."""

    title: str
    url: str
    published: str | None
    content: str


class ResearchDraft(BaseModel):
    """Internal model output; the support excerpt never crosses the API."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    signal: str = Field(min_length=1, max_length=500)
    ask_next: str = Field(min_length=1, max_length=500)
    judge_lens: str
    source_url: HttpUrl
    confidence: float = Field(ge=0, le=1)
    supporting_excerpt: str = Field(min_length=8, max_length=600)


class ResearchRuntime(Protocol):
    available: bool

    async def research(
        self,
        request: ResearchRequest,
        trigger: ResearchTrigger,
        documents: list[SearchDocument],
    ) -> list[ResearchDraft]: ...


class SearchProvider(Protocol):
    available: bool

    async def search(self, query: str) -> list[SearchDocument]: ...


class ExaMcpSearchProvider:
    """Anonymous, keyless access to the Exa MCP endpoint supported by OpenCode."""

    def __init__(self) -> None:
        self.url = os.getenv("INTERVIEW_RESEARCH_SEARCH_URL", "https://mcp.exa.ai/mcp")
        self.available = os.getenv("INTERVIEW_RESEARCH_ENABLED", "1").lower() not in {
            "0",
            "false",
            "off",
        }

    async def search(self, query: str) -> list[SearchDocument]:
        if not self.available:
            return []
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "web_search_exa",
                "arguments": {
                    "query": query,
                    "numResults": 5,
                    "livecrawl": "preferred",
                    "type": "auto",
                    "contextMaxCharacters": 12_000,
                },
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=5)) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={"Accept": "application/json, text/event-stream"},
            )
            response.raise_for_status()
        return parse_exa_response(response.text)


def parse_exa_response(body: str) -> list[SearchDocument]:
    """Parse Exa's streamable-HTTP MCP response without adding an MCP SDK."""

    messages: list[dict] = []
    if body.lstrip().startswith("{"):
        messages.append(json.loads(body))
    else:
        for line in body.splitlines():
            if line.startswith("data: "):
                messages.append(json.loads(line[6:]))
    text_blocks: list[str] = []
    for message in messages:
        for item in message.get("result", {}).get("content", []):
            if item.get("type") == "text" and item.get("text"):
                text_blocks.append(item["text"])
    documents: list[SearchDocument] = []
    for block in "\n---\n".join(text_blocks).split("\n---\n"):
        match = re.search(
            r"Title:\s*(?P<title>.+?)\nURL:\s*(?P<url>https?://\S+)"
            r"(?:\nPublished:\s*(?P<published>.*?))?\n(?:Author:.*?\n)?Highlights:\s*(?P<content>.*)",
            block.strip(),
            re.DOTALL,
        )
        if not match:
            continue
        published = (match.group("published") or "").strip()
        if not published or published.upper() in {"N/A", "NULL", "NONE", "UNKNOWN"}:
            published = None
        documents.append(
            SearchDocument(
                title=match.group("title").strip(),
                url=match.group("url").strip(),
                published=published,
                content=match.group("content").strip(),
            )
        )
    unique: dict[str, SearchDocument] = {}
    for document in documents:
        unique.setdefault(normalize_url(document.url), document)
    return list(unique.values())[:5]


def detect_research_trigger(request: ResearchRequest) -> ResearchTrigger | None:
    """Return one high-value trigger from the latest meaningful interview state."""

    if not request.transcript:
        return None
    latest = request.transcript[-1]
    if latest.speaker != "Participant":
        return None
    text = latest.text.strip()
    if len(text.split()) < 4 or DEFINITION_RE.search(text):
        return None

    evidence_ids = tuple(
        item.id for item in request.evidence if latest.id in item.source_turn_ids
    )
    kind: str | None = None
    if UNIVERSAL_RE.search(text):
        kind = "universal_or_absence_claim"
    elif SOLUTION_RE.search(text):
        kind = "existing_solution_check"
    elif FEASIBILITY_RE.search(text):
        kind = "feasibility"
    elif CURRENT_RE.search(text):
        kind = "current_or_local_claim"
    elif CONSTRAINT_RE.search(text):
        kind = "local_constraint"
    elif NAMED_ENTITY_RE.search(text) or NAMED_CUE_RE.search(text):
        kind = "named_initiative"
    elif STAKEHOLDER_RE.search(text) and re.search(
        r"\b(?:think|want|need|avoid|cannot|can't|prefer|excluded|affected)\b", text, re.I
    ):
        kind = "stakeholder_perspective"
    if kind is None:
        return None

    configuration = request.effective_configuration()
    local_hint = "Chiang Mai" if re.search(
        r"chiang mai|nimman|thailand", f"{text} {configuration.template.name} {configuration.template.objective}", re.I
    ) else ""
    priority = (
        "Find a current counterexample or primary source. Prefer official/local sources. "
        if kind in {"universal_or_absence_claim", "existing_solution_check", "current_or_local_claim"}
        else "Find a current primary or direct-experience source. "
    )
    query = f"{priority}{local_hint}. Claim to test: {text}".strip()[:500]
    return ResearchTrigger(
        text=text,
        turn_id=latest.id,
        related_evidence_ids=evidence_ids,
        kind=kind,
        query=query,
    )


def normalize_url(value: str) -> str:
    """Create a stable URL key without altering the direct URL shown to users."""

    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def semantic_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", value.lower())
        if token not in {"the", "and", "that", "this", "with", "what", "which", "from"}
    }


def semantically_duplicate(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= 0.72


def validate_drafts(
    drafts: list[ResearchDraft],
    documents: list[SearchDocument],
    trigger: ResearchTrigger,
) -> list[ResearchCard]:
    """Reject invented URLs, unsupported signals, leading asks, and duplicates."""

    sources = {normalize_url(document.url): document for document in documents}
    cards: list[ResearchCard] = []
    seen_urls: set[str] = set()
    seen_semantics: list[set[str]] = []
    for draft in drafts:
        key = normalize_url(str(draft.source_url))
        document = sources.get(key)
        if not document or key in seen_urls:
            continue
        excerpt = re.sub(r"\s+", " ", draft.supporting_excerpt).strip().casefold()
        source_text = re.sub(r"\s+", " ", document.content).strip().casefold()
        if excerpt not in source_text:
            continue
        excerpt_tokens = semantic_tokens(draft.supporting_excerpt)
        signal_tokens = semantic_tokens(draft.signal)
        if len(signal_tokens & excerpt_tokens) < 2 or draft.confidence < 0.65:
            continue
        host = urlsplit(document.url).netloc.casefold()
        if ("reddit.com" in host or "facebook.com" in host) and "anecdot" not in draft.signal.casefold():
            continue
        tokens = semantic_tokens(f"{draft.signal} {draft.ask_next}")
        if any(semantically_duplicate(tokens, previous) for previous in seen_semantics):
            continue
        digest = hashlib.sha1(f"{key}|{draft.ask_next.casefold()}".encode()).hexdigest()[:12]
        try:
            card = ResearchCard(
                id=f"research_{digest}",
                signal=draft.signal,
                ask_next=draft.ask_next,
                why_now=trigger.text,
                judge_lens=draft.judge_lens,
                source_title=document.title,
                source_url=document.url,
                source_date=document.published,
                confidence=draft.confidence,
                related_evidence_ids=list(trigger.related_evidence_ids),
            )
        except ValueError:
            continue
        cards.append(card)
        seen_urls.add(key)
        seen_semantics.append(tokens)
        if len(cards) == 2:
            break
    return cards


@dataclass
class SessionResearchState:
    latest_revision: int = 0
    last_search_at: float = 0
    seen_queries: set[str] = field(default_factory=set)
    seen_query_semantics: list[set[str]] = field(default_factory=list)
    seen_urls: set[str] = field(default_factory=set)
    seen_semantics: list[set[str]] = field(default_factory=list)
    cache: dict[str, list[ResearchCard]] = field(default_factory=dict)


class ResearchCoordinator:
    """Keep internet research off the transcription and extraction critical path."""

    def __init__(
        self,
        runtime: ResearchRuntime,
        provider: SearchProvider | None = None,
        *,
        cooldown_seconds: float = 12,
    ) -> None:
        self.runtime = runtime
        self.provider = provider or ExaMcpSearchProvider()
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[str, SessionResearchState] = {}
        self._lock = asyncio.Lock()

    async def run(self, request: ResearchRequest) -> ResearchPacket:
        trigger = detect_research_trigger(request)
        async with self._lock:
            state = self._states.setdefault(request.session_id, SessionResearchState())
            if request.revision < state.latest_revision:
                return ResearchPacket(revision=request.revision, stale=True)
            state.latest_revision = request.revision
        if trigger is None:
            return ResearchPacket(revision=request.revision)
        if request.mode == "demo":
            if trigger.kind != "universal_or_absence_claim":
                return ResearchPacket(revision=request.revision)
            return ResearchPacket(
                revision=request.revision,
                cards=[demo_research_card(trigger)],
            )

        query_key = re.sub(r"\s+", " ", trigger.query).strip().casefold()
        query_tokens = semantic_tokens(trigger.query)
        now = time.monotonic()
        async with self._lock:
            state = self._states[request.session_id]
            if query_key in state.cache:
                return ResearchPacket(
                    revision=request.revision,
                    cards=state.cache[query_key],
                    from_cache=True,
                )
            if (
                query_key in state.seen_queries
                or any(semantically_duplicate(query_tokens, prior) for prior in state.seen_query_semantics)
                or now - state.last_search_at < self.cooldown_seconds
            ):
                return ResearchPacket(revision=request.revision)
            state.seen_queries.add(query_key)
            state.seen_query_semantics.append(query_tokens)
            state.last_search_at = now

        if not self.provider.available or not self.runtime.available:
            async with self._lock:
                self._states[request.session_id].cache[query_key] = []
            return ResearchPacket(revision=request.revision)
        try:
            documents = await self.provider.search(trigger.query)
            if not documents or await self._is_stale(request):
                return ResearchPacket(
                    revision=request.revision,
                    stale=await self._is_stale(request),
                )
            drafts = await self.runtime.research(request, trigger, documents)
            cards = validate_drafts(drafts, documents, trigger)
        except Exception:
            logger.debug("Live research returned no result", exc_info=True)
            cards = []

        async with self._lock:
            state = self._states[request.session_id]
            if request.revision != state.latest_revision:
                return ResearchPacket(revision=request.revision, stale=True)
            fresh: list[ResearchCard] = []
            for card in cards:
                url_key = normalize_url(str(card.source_url))
                tokens = semantic_tokens(f"{card.signal} {card.ask_next}")
                if url_key in state.seen_urls:
                    continue
                if any(semantically_duplicate(tokens, prior) for prior in state.seen_semantics):
                    continue
                state.seen_urls.add(url_key)
                state.seen_semantics.append(tokens)
                fresh.append(card)
            state.cache[query_key] = fresh
        return ResearchPacket(revision=request.revision, cards=fresh)

    async def _is_stale(self, request: ResearchRequest) -> bool:
        async with self._lock:
            return request.revision != self._states[request.session_id].latest_revision


def demo_research_card(trigger: ResearchTrigger) -> ResearchCard:
    """Stable hackathon card using the user-supplied, directly linked example source."""

    return ResearchCard(
        id="research_demo_local_nomad_connection",
        signal=(
            "A current Chiang Mai group explicitly advertises events for both local people "
            "and digital nomads, so the gap may be the experience inside events rather than their absence."
        ),
        ask_next="Which events have you tried, and when did they begin to feel like an expat bubble?",
        why_now=trigger.text,
        judge_lens="New",
        source_title="Chiang Mai Professionals, Expats and Digital Nomads",
        source_url=(
            "https://www.meetup.com/th-th/"
            "chiang-mai-professionals-expats-and-digital-nomads/"
        ),
        source_date=None,
        confidence=0.9,
        related_evidence_ids=list(trigger.related_evidence_ids),
    )
