"""Typed contracts shared by configuration, API, runtime, and fallback."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator, model_validator

Speaker = Literal["Interviewer", "Participant"]
EvidenceType = Literal[
    "fact", "pain", "quote", "question", "source", "insight", "tool", "workflow"
]
AgentName = Literal["Clarification", "Opportunity", "Bias guard", "Memory", "Research"]
JudgeLens = Literal["Real", "New", "Good", "Feasible"]
NonEmptyItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]
Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]


class StrictModel(BaseModel):
    """Base for contracts where silent unknown fields would create no-op UI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TranscriptTurn(StrictModel):
    """One attributed piece of the interview transcript."""

    id: str
    speaker: Speaker
    text: str = Field(min_length=1, max_length=4_000)
    elapsed_seconds: int = 0


class WebProvenance(StrictModel):
    """The source trail retained when a research card becomes evidence."""

    research_id: str
    source_title: str = Field(min_length=1, max_length=300)
    source_url: HttpUrl
    source_date: str | None = Field(default=None, max_length=100)
    why_now: str = Field(min_length=1, max_length=1_000)
    judge_lens: JudgeLens


class EvidenceItem(StrictModel):
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
    provenance: WebProvenance | None = None


class AgentSuggestion(StrictModel):
    """An ephemeral intervention offered by a specialist lens."""

    id: str
    agent: AgentName
    kind: Literal["question", "pattern", "opportunity", "warning", "research"]
    text: str = Field(min_length=1, max_length=600)
    rationale: str = Field(default="", max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = "medium"


class InterviewTemplate(StrictModel):
    """Editable interview objective and completion criteria."""

    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4_000)
    phases: list[NonEmptyItem] = Field(min_length=1, max_length=50)
    success_metrics: list[NonEmptyItem] = Field(min_length=1, max_length=50)
    interviewer_guidance: list[NonEmptyItem] = Field(default_factory=list, max_length=50)


class SpecialistLenses(StrictModel):
    clarification: bool
    opportunity: bool
    bias_guard: bool
    memory: bool
    research: bool

    @model_validator(mode="after")
    def require_enabled_lens(self) -> Self:
        if not any(self.model_dump().values()):
            raise ValueError("At least one specialist lens must remain enabled")
        return self


class CopilotLimits(StrictModel):
    transcript_turns: int = Field(ge=1, le=100)
    evidence_context_items: int = Field(ge=1, le=200)
    new_evidence_items: int = Field(ge=0, le=20)
    suggestions: int = Field(ge=0, le=20)


class CopilotConfiguration(StrictModel):
    system_prompt: Prompt
    task_prompt: Prompt
    lenses: SpecialistLenses
    limits: CopilotLimits
    promoted_evidence_first: bool


class ReportSections(StrictModel):
    summary: bool
    top_pains: bool
    key_facts: bool
    quotes: bool
    unanswered_questions: bool
    opportunity: bool
    next_step: bool
    coverage: bool


class ReportConfiguration(StrictModel):
    system_prompt: Prompt
    task_prompt: Prompt
    next_step_instruction: Prompt
    sections: ReportSections
    score_against_success_metrics: bool


class AudioConfiguration(StrictModel):
    segment_ms: int = Field(ge=2_000, le=60_000)
    overlap_ms: int = Field(ge=0, le=2_000)
    default_speaker: Speaker
    persist_raw_audio: bool
    whisper_language: str = Field(min_length=1, max_length=40)
    whisper_model: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def overlap_is_shorter_than_segment(self) -> Self:
        if self.overlap_ms >= self.segment_ms:
            raise ValueError("overlap_ms must be less than segment_ms")
        return self


class RuntimeConfiguration(StrictModel):
    model: str = Field(min_length=3, max_length=300)
    archive_root: str = Field(min_length=1, max_length=1_000)

    @field_validator("model")
    @classmethod
    def provider_model_format(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._:/-]+", value):
            raise ValueError("Model must use provider/model format")
        return value

    @field_validator("archive_root")
    @classmethod
    def safe_archive_root(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "data":
            raise ValueError("Archive root must be a relative path inside data/")
        return path.as_posix()


class DeveloperConfiguration(StrictModel):
    analysis_output_contract: Literal["default"]
    report_output_contract: Literal["default"]
    demo_script: str = Field(min_length=1, max_length=20_000)
    fallback_profile: Literal["default"]


class InterviewConfiguration(StrictModel):
    """Versioned configuration frozen for one interview session."""

    schema_version: Literal[1]
    template: InterviewTemplate
    copilot: CopilotConfiguration
    report: ReportConfiguration
    audio: AudioConfiguration
    runtime: RuntimeConfiguration
    developer: DeveloperConfiguration


class AnalysisRequest(StrictModel):
    """The bounded shared context sent through one analysis cycle."""

    transcript: list[TranscriptTurn]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    configuration: InterviewConfiguration | None = None
    template: InterviewTemplate | None = None
    focus_evidence_ids: list[str] = Field(default_factory=list)
    mode: Literal["live", "demo"] = "live"

    def effective_configuration(self) -> InterviewConfiguration:
        from interview_copilot.configuration import get_default_configuration

        configuration = self.configuration or get_default_configuration()
        if self.configuration is None and self.template is not None:
            configuration = configuration.model_copy(update={"template": self.template}, deep=True)
        return configuration


class AnalysisPacket(StrictModel):
    """Structured response added to the shared pool and activity feed."""

    suggestions: list[AgentSuggestion] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    engine: Literal["openai", "local"] = "local"
    notice: str | None = None


class ResearchCard(StrictModel):
    """One sourced finding that changes the next useful interview question."""

    id: str = Field(pattern=r"^research_[A-Za-z0-9_-]+$", max_length=120)
    signal: str = Field(min_length=1, max_length=500)
    ask_next: str = Field(min_length=1, max_length=500)
    why_now: str = Field(min_length=1, max_length=1_000)
    judge_lens: JudgeLens
    source_title: str = Field(min_length=1, max_length=300)
    source_url: HttpUrl
    source_date: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0, le=1)
    related_evidence_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("signal")
    @classmethod
    def concise_signal(cls, value: str) -> str:
        sentences = [item for item in re.split(r"(?<=[.!?])\s+", value) if item]
        if len(sentences) > 2:
            raise ValueError("Research signals may contain at most two sentences")
        return value

    @field_validator("ask_next")
    @classmethod
    def neutral_question(cls, value: str) -> str:
        if not value.endswith("?"):
            raise ValueError("ask_next must be a question")
        if re.search(r"\b(?:wouldn't you|don't you think|you should|our solution|buy|subscribe)\b", value, re.I):
            raise ValueError("ask_next must remain neutral")
        return value


class ResearchRequest(StrictModel):
    """A versioned interview snapshot submitted to the silent research lane."""

    session_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    transcript: list[TranscriptTurn]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    configuration: InterviewConfiguration | None = None
    mode: Literal["live", "demo"] = "live"

    def effective_configuration(self) -> InterviewConfiguration:
        from interview_copilot.configuration import get_default_configuration

        return self.configuration or get_default_configuration()


class ResearchPacket(StrictModel):
    """Zero to two research cards for a specific interview revision."""

    cards: list[ResearchCard] = Field(default_factory=list, max_length=2)
    revision: int = Field(ge=1)
    stale: bool = False
    from_cache: bool = False


class CoverageItem(StrictModel):
    label: str
    complete: bool


class InterviewReport(StrictModel):
    """Evidence-backed closing synthesis with a stable response shape."""

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


class PersistentInterviewReport(InterviewReport):
    """A durable report snapshot that can be reopened after the live session ends."""

    report_id: int = Field(ge=1)
    session_id: str = Field(min_length=1, max_length=128)
    created_at: str
    template: InterviewTemplate
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    html_url: str
    json_url: str


class ReportIndexItem(StrictModel):
    """Compact metadata used by the persistent report library."""

    report_id: int = Field(ge=1)
    session_id: str
    created_at: str
    template_name: str
    summary: str
    score: int = Field(ge=0, le=100)
    transcript_turns: int = Field(ge=0)
    evidence_items: int = Field(ge=0)
    html_url: str
    json_url: str


class ReportRequest(StrictModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    transcript: list[TranscriptTurn]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    configuration: InterviewConfiguration | None = None
    template: InterviewTemplate | None = None
    mode: Literal["live", "demo"] = "live"

    def effective_configuration(self) -> InterviewConfiguration:
        from interview_copilot.configuration import get_default_configuration

        configuration = self.configuration or get_default_configuration()
        if self.configuration is None and self.template is not None:
            configuration = configuration.model_copy(update={"template": self.template}, deep=True)
        return configuration


class StartInterviewRequest(StrictModel):
    session_id: str = Field(min_length=1, max_length=128)
    configuration: InterviewConfiguration
    mode: Literal["live", "demo"] = "live"
