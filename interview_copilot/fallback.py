"""Fast deterministic extraction used for demos and graceful degradation."""

import hashlib
import re

from interview_copilot.models import (
    AgentSuggestion,
    AnalysisPacket,
    AnalysisRequest,
    CoverageItem,
    EvidenceItem,
    InterviewReport,
    ReportRequest,
)

PAIN_WORDS = (
    "annoying",
    "frustrating",
    "hate",
    "difficult",
    "stress",
    "waste",
    "problem",
    "worst",
)
WORKFLOW_WORDS = ("use ", "leave ", "book ", "pay ", "track ", "renew ", "message ")
KNOWN_TOOLS = ("Wise", "Notion", "Slack", "WhatsApp", "Google Calendar", "Excel")
QUANTIFIED = re.compile(
    r"\b(?:every\s+\d+\s+(?:days?|weeks?|months?)|\d+(?:\.\d+)?\s+(?:hours?|minutes?|days?|baht|dollars?|usd))\b",
    re.IGNORECASE,
)


def stable_id(prefix: str, text: str) -> str:
    """Return a deterministic short id so repeated analysis can deduplicate."""

    digest = hashlib.sha1(text.lower().strip().encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _evidence(kind: str, text: str, turn_id: str, confidence: float) -> EvidenceItem:
    return EvidenceItem(
        id=stable_id(kind, text),
        type=kind,  # type: ignore[arg-type]
        text=text.strip(),
        confidence=confidence,
        source_turn_ids=[turn_id],
    )


def _suggestion(agent: str, kind: str, text: str, rationale: str) -> AgentSuggestion:
    return AgentSuggestion(
        id=stable_id("suggestion", f"{agent}:{text}"),
        agent=agent,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
        text=text,
        rationale=rationale,
    )


def analyse_locally(request: AnalysisRequest) -> AnalysisPacket:
    """Extract useful objects without a model so the interview never stalls."""

    if not request.transcript:
        return AnalysisPacket()
    latest = request.transcript[-1]
    text = latest.text.strip()
    lowered = text.lower()
    existing = {item.text.lower().strip() for item in request.evidence}
    found: list[EvidenceItem] = []

    if latest.speaker == "Participant" and len(text.split()) >= 5:
        found.append(_evidence("quote", text, latest.id, 0.86))
    if any(word in lowered for word in PAIN_WORDS):
        found.append(_evidence("pain", text, latest.id, 0.82))
    for match in QUANTIFIED.findall(text):
        found.append(_evidence("fact", match, latest.id, 0.93))
    if any(word in lowered for word in WORKFLOW_WORDS):
        found.append(_evidence("workflow", text, latest.id, 0.72))
    for tool in KNOWN_TOOLS:
        if tool.lower() in lowered:
            found.append(_evidence("tool", tool, latest.id, 0.96))

    found = [item for item in found if item.text.lower().strip() not in existing]
    evidence_priority = {"pain": 0, "fact": 1, "tool": 2, "quote": 3, "workflow": 4}
    found.sort(key=lambda item: evidence_priority.get(item.type, 9))
    suggestions: list[AgentSuggestion] = []
    participant_text = " ".join(
        turn.text.lower() for turn in request.transcript if turn.speaker == "Participant"
    )
    if not QUANTIFIED.search(participant_text):
        suggestions.append(
            _suggestion(
                "Clarification",
                "question",
                "How often does this happen in a typical month?",
                "Frequency is still unquantified.",
            )
        )
    elif not re.search(r"\b(?:baht|dollars?|usd|cost|pay|paid|spend)\b", participant_text):
        suggestions.append(
            _suggestion(
                "Opportunity",
                "question",
                "What does that cost you each time, including time and money?",
                "A repeated workflow is present but its cost is unclear.",
            )
        )
    if any(word in participant_text for word in PAIN_WORDS):
        suggestions.append(
            _suggestion(
                "Clarification",
                "question",
                "Walk me through the last time this happened.",
                "A concrete recent story will expose the underlying workflow.",
            )
        )
        suggestions.append(
            _suggestion(
                "Opportunity",
                "opportunity",
                "A repeated, emotional workaround may signal meaningful unmet need.",
                "Pain language and recurring behaviour appear together.",
            )
        )
    if latest.speaker == "Interviewer" and re.search(
        r"\b(?:don't you think|wouldn't you|isn't it|you'd pay)\b", lowered
    ):
        suggestions.append(
            _suggestion(
                "Bias guard",
                "warning",
                "This may be leading. Ask them to describe their own ideal outcome instead.",
                "The question contains the answer it is seeking.",
            )
        )
    if any(tool.lower() in participant_text for tool in KNOWN_TOOLS):
        suggestions.append(
            _suggestion(
                "Research",
                "research",
                "Validate whether people describe the same workaround in nomad communities.",
                "A named tool creates a specific external-research query.",
            )
        )

    return AnalysisPacket(suggestions=suggestions[:4], evidence=found[:4], engine="local")


def build_local_report(request: ReportRequest) -> InterviewReport:
    """Build an honest evidence-only report when live synthesis is unavailable."""

    evidence = sorted(request.evidence, key=lambda item: (item.pinned, item.promoted), reverse=True)
    pains = [item.text for item in evidence if item.type == "pain"][:4]
    facts = [item.text for item in evidence if item.type in ("fact", "workflow", "tool")][:6]
    quotes = [item.text for item in evidence if item.type == "quote"][:3]
    questions = [item.text for item in evidence if item.type == "question"][:5]
    joined = " ".join(turn.text.lower() for turn in request.transcript)
    coverage = [
        CoverageItem(label="Current workflow", complete=any(i.type == "workflow" for i in evidence)),
        CoverageItem(label="Pain point", complete=bool(pains)),
        CoverageItem(label="Frequency", complete=bool(QUANTIFIED.search(joined))),
        CoverageItem(
            label="Cost",
            complete=bool(re.search(r"\b(?:baht|dollars?|usd|cost|pay|paid|spend)\b", joined)),
        ),
    ]
    score = round(sum(item.complete for item in coverage) / len(coverage) * 100)
    has_visa_thread = "visa" in joined
    strongest_thread = (
        "repeated disruption around the visa-run workflow"
        if has_visa_thread
        else f"a recurring pain: {pains[0].rstrip('.')}" if pains
        else "a workaround that still needs a concrete pain story"
    )
    opportunity = (
        "Validate whether the same visa-run pain and workaround recur across three more interviews."
        if has_visa_thread
        else "Validate whether the same pain and workaround recur across three more interviews."
    )
    return InterviewReport(
        summary=(
            f"The interview surfaced {len(evidence)} evidence items. "
            f"The clearest pattern is {strongest_thread}."
        ),
        top_pains=pains,
        key_facts=facts,
        quotes=quotes,
        unanswered_questions=questions or ["What would make this problem worth solving now?"],
        opportunity=opportunity,
        next_step="Run a concierge test that removes one step from the current workflow for a single participant.",
        score=score,
        coverage=coverage,
        engine="local",
    )
