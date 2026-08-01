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
DEPTH_CUES = (
    (
        re.compile(r"\b(?:want(?:ed)?|trying|goal|hop(?:e|ed|ing)|looking for|achiev\w*|make possible)\b", re.I),
        "What were you hoping to achieve in that moment?",
        "The participant's desired outcome is not explicit yet.",
    ),
    (
        re.compile(r"\b(?:why|matter(?:ed|s)?|important|because|so that|care about|make possible)\b", re.I),
        "Why did that outcome matter to you—what would it have made possible?",
        "The outcome is visible, but its underlying meaning is not.",
    ),
    (
        re.compile(r"\b(?:right now|currently|today|enough|satisf\w*|happy with|working for you|how well)\b", re.I),
        "How well are you getting that outcome today—is it enough and reliable enough?",
        "Current satisfaction with the desired outcome is still unclear.",
    ),
    (
        re.compile(r"\b(?:expect\w*|imagin\w*|actual\w*|instead|difference|gap|turned out)\b", re.I),
        "What did you expect would happen, and what actually happened?",
        "The expected-versus-actual gap has not been made explicit.",
    ),
    (
        re.compile(r"\b(?:stuck|slow\w*|struggl\w*|barrier|hard(?:er|est)?|difficult|go(?:es|ing)? nowhere|doesn'?t work|fail\w*|workaround)\b", re.I),
        "Where did it get stuck, slow down, become difficult, or go nowhere?",
        "The break point in the participant's progress is not specific yet.",
    ),
    (
        re.compile(r"\b(?:cost|impact|consequence|lost|missed|waste|priority|worth fixing|how often|every\s+\d+|time|money|energy|opportunit\w*)\b", re.I),
        "What did that gap cost you, and why does it matter now?",
        "The consequence and priority of the gap are still unclear.",
    ),
)
LENS_NAMES = {
    "clarification": "Clarification",
    "opportunity": "Opportunity",
    "bias_guard": "Bias guard",
    "memory": "Memory",
    "research": "Research",
}
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


def _suggestion(
    agent: str,
    kind: str,
    text: str,
    rationale: str,
    priority: str = "medium",
) -> AgentSuggestion:
    return AgentSuggestion(
        id=stable_id("suggestion", f"{agent}:{text}"),
        agent=agent,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
        text=text,
        rationale=rationale,
        priority=priority,  # type: ignore[arg-type]
    )


def _next_depth_probe(conversation_text: str) -> AgentSuggestion:
    """Return one question for the earliest missing rung in the depth ladder."""

    for cue, question, rationale in DEPTH_CUES:
        if not cue.search(conversation_text):
            return _suggestion("Clarification", "question", question, rationale, "high")
    return _suggestion(
        "Clarification",
        "question",
        "Tell me about the last specific time that gap showed up. What did you do next?",
        "The depth ladder is covered; a concrete incident can verify the pattern.",
        "high",
    )


def analyse_locally(request: AnalysisRequest) -> AnalysisPacket:
    """Extract useful objects without a model so the interview never stalls."""

    configuration = request.effective_configuration()
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
    conversation_text = " ".join(turn.text.lower() for turn in request.transcript)
    participant_text = " ".join(
        turn.text.lower() for turn in request.transcript if turn.speaker == "Participant"
    )
    suggestions.append(_next_depth_probe(conversation_text))
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
                "Opportunity",
                "opportunity",
                "A repeated, emotional workaround may signal meaningful unmet need.",
                "Pain language and recurring behaviour appear together.",
            )
        )
    if latest.speaker == "Interviewer" and re.search(
        r"\b(?:don't you think|wouldn't you|isn't it|you'd pay)\b", lowered
    ):
        suggestions.insert(
            0,
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

    enabled_lenses = {
        LENS_NAMES[key]
        for key, enabled in configuration.copilot.lenses.model_dump().items()
        if enabled
    }
    suggestions = [item for item in suggestions if item.agent in enabled_lenses]
    return AnalysisPacket(
        suggestions=suggestions[: configuration.copilot.limits.suggestions],
        evidence=found[: configuration.copilot.limits.new_evidence_items],
        engine="local",
    )


def _metric_complete(label: str, evidence: list[EvidenceItem], transcript: str) -> bool:
    """Conservatively score common success criteria without inventing completion."""

    lowered = label.lower()
    depth_metric_cues = (
        (("desired outcome", "outcome the participant wanted", "trying to achieve"), DEPTH_CUES[0][0]),
        (("why that outcome", "why it mattered", "why that outcome matters"), DEPTH_CUES[1][0]),
        (("how well", "current reality", "achieves it", "gets that outcome"), DEPTH_CUES[2][0]),
        (("expected-versus-actual", "expectation gap", "gap explicit"), DEPTH_CUES[3][0]),
        (("stalls", "breaks", "hardest point", "workaround"), DEPTH_CUES[4][0]),
        (("consequence", "priority"), DEPTH_CUES[5][0]),
    )
    for labels, cue in depth_metric_cues:
        if any(label in lowered for label in labels):
            return bool(cue.search(transcript))
    if any(word in lowered for word in ("workflow", "process", "current")):
        return any(item.type == "workflow" for item in evidence)
    if any(word in lowered for word in ("pain", "frustrat", "problem")):
        return any(item.type == "pain" for item in evidence)
    if any(word in lowered for word in ("frequency", "often", "recurr")):
        return bool(QUANTIFIED.search(transcript))
    if any(word in lowered for word in ("cost", "money", "price", "spend")):
        return bool(re.search(r"\b(?:baht|dollars?|usd|cost|pay|paid|spend)\b", transcript))
    meaningful = [word for word in re.findall(r"[a-z0-9]+", lowered) if len(word) >= 5]
    evidence_text = " ".join(item.text.lower() for item in evidence)
    return bool(meaningful) and all(word in evidence_text for word in meaningful[:2])


def build_local_report(request: ReportRequest) -> InterviewReport:
    """Build an honest evidence-only report when live synthesis is unavailable."""

    configuration = request.effective_configuration()
    evidence = sorted(request.evidence, key=lambda item: (item.pinned, item.promoted), reverse=True)
    pains = [item.text for item in evidence if item.type == "pain"][:4]
    facts = [item.text for item in evidence if item.type in ("fact", "workflow", "tool")][:6]
    quotes = [item.text for item in evidence if item.type == "quote"][:3]
    questions = [item.text for item in evidence if item.type == "question"][:5]
    joined = " ".join(turn.text.lower() for turn in request.transcript)
    coverage = [
        CoverageItem(label=metric, complete=_metric_complete(metric, evidence, joined))
        for metric in configuration.template.success_metrics
    ]
    score = (
        round(sum(item.complete for item in coverage) / len(coverage) * 100)
        if configuration.report.score_against_success_metrics
        else 0
    )
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
    report = InterviewReport(
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
    sections = configuration.report.sections
    updates: dict[str, object] = {}
    for name in ("top_pains", "key_facts", "quotes", "unanswered_questions", "coverage"):
        if not getattr(sections, name):
            updates[name] = []
    for name in ("summary", "opportunity", "next_step"):
        if not getattr(sections, name):
            updates[name] = ""
    return report.model_copy(update=updates)
