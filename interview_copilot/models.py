"""Typed contracts shared by the API, agent runtime, and local fallback."""

from typing import Literal

from pydantic import BaseModel, Field

Speaker = Literal["Interviewer", "Participant"]
EvidenceType = Literal[
    "fact", "pain", "quote", "question", "source", "insight", "tool", "workflow"
]
AgentName = Literal["Clarification", "Opportunity", "Bias guard", "Memory", "Research"]


class TranscriptTurn(BaseModel):
    """One attributed piece of the interview transcript."""

    id: str
    speaker: Speaker
    text: str = Field(min_length=1, max_length=4_000)
    elapsed_seconds: int = 0


class EvidenceItem(BaseModel):
    """A structured object in the shared evidence pool."""

    id: str
    type: EvidenceType
    text: str = Field(min_length=1, max_length=1_000)
    confidence: float = Field(default=0.75, ge=0, le=1)
    pinned: bool = False
    promoted: bool = False
    source: Literal["transcript", "agent", "web"] = "transcript"
    source_turn_ids: list[str] = Field(default_factory=list)
    related_evidence_ids: list[str] = Field(default_factory=list)
    agents: list[AgentName] = Field(default_factory=list)
    url: str | None = None


class AgentSuggestion(BaseModel):
    """An ephemeral intervention offered by a specialist lens."""

    id: str
    agent: AgentName
    kind: Literal["question", "pattern", "opportunity", "warning", "research"]
    text: str = Field(min_length=1, max_length=600)
    rationale: str = Field(default="", max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = "medium"


class InterviewTemplate(BaseModel):
    """Reusable interview objective and completion criteria."""

    name: str = "Digital nomad frictions"
    objective: str = "Discover recurring pains, workarounds, and unmet needs."
    phases: list[str] = Field(
        default_factory=lambda: [
            "Rapport",
            "Current workflow",
            "Frustrations",
            "Workarounds",
            "Cost and frequency",
            "Ideal future",
        ]
    )
    success_metrics: list[str] = Field(
        default_factory=lambda: [
            "Learned the current process",
            "Found the biggest pain",
            "Quantified frequency",
            "Estimated cost",
        ]
    )


class AnalysisRequest(BaseModel):
    """The bounded shared context sent through one analysis cycle."""

    transcript: list[TranscriptTurn]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    template: InterviewTemplate = Field(default_factory=InterviewTemplate)
    focus_evidence_ids: list[str] = Field(default_factory=list)
    mode: Literal["live", "demo"] = "live"


class AnalysisPacket(BaseModel):
    """Structured response added to the shared pool and activity feed."""

    suggestions: list[AgentSuggestion] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    engine: Literal["openai", "local"] = "local"
    notice: str | None = None


class CoverageItem(BaseModel):
    label: str
    complete: bool


class InterviewReport(BaseModel):
    """Evidence-backed closing synthesis."""

    summary: str
    top_pains: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    opportunity: str
    next_step: str
    score: int = Field(ge=0, le=100)
    coverage: list[CoverageItem] = Field(default_factory=list)
    engine: Literal["openai", "local"] = "local"
    notice: str | None = None


class ReportRequest(BaseModel):
    transcript: list[TranscriptTurn]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    template: InterviewTemplate = Field(default_factory=InterviewTemplate)
    mode: Literal["live", "demo"] = "live"
