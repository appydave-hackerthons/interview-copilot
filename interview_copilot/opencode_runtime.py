"""OpenCode sidecar supervision and structured OpenAI OAuth model calls."""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

from interview_copilot.models import (
    AnalysisPacket,
    AnalysisRequest,
    InterviewReport,
    ReportRequest,
    ResearchRequest,
)
from interview_copilot.research import ResearchDraft, ResearchTrigger, SearchDocument

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "openai/gpt-5.6-sol"
NO_TOOLS = {
    name: False
    for name in (
        "bash",
        "edit",
        "write",
        "read",
        "grep",
        "glob",
        "list",
        "patch",
        "apply_patch",
        "task",
        "question",
        "skill",
        "webfetch",
        "websearch",
    )
}
LENS_NAMES = {
    "clarification": "Clarification",
    "opportunity": "Opportunity",
    "bias_guard": "Bias guard",
    "memory": "Memory",
    "research": "Research",
}


class OpenCodeRuntime:
    """Lazily run one bounded OpenCode sidecar using the user's OAuth state."""

    def __init__(self) -> None:
        self.binary = os.getenv("OPENCODE_BIN") or shutil.which("opencode")
        self.port = int(os.getenv("OPENCODE_PORT", "4097"))
        self.external_url = os.getenv("OPENCODE_URL")
        self.base_url = self.external_url or f"http://127.0.0.1:{self.port}"
        self.model = os.getenv("INTERVIEW_MODEL", DEFAULT_MODEL)
        self.process: subprocess.Popen[bytes] | None = None
        self._log_handle: Any = None
        self._start_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        """Whether a configured or locally spawnable runtime exists."""

        return bool(self.external_url or self.binary)

    async def _healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/global/health")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def ensure_started(self) -> None:
        """Start the sidecar once and wait for its health endpoint."""

        if await self._healthy():
            return
        if self.external_url:
            raise RuntimeError(f"OpenCode sidecar is unavailable at {self.external_url}")
        if not self.binary:
            raise RuntimeError("OpenCode is not installed")
        async with self._start_lock:
            if await self._healthy():
                return
            log_dir = ROOT / "var"
            log_dir.mkdir(exist_ok=True)
            self._log_handle = (log_dir / "opencode.log").open("ab")
            self.process = subprocess.Popen(
                [
                    self.binary,
                    "serve",
                    "--pure",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(self.port),
                    "--log-level",
                    "WARN",
                ],
                cwd=ROOT,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
            )
            for _ in range(60):
                if self.process.poll() is not None:
                    raise RuntimeError("OpenCode sidecar exited during startup")
                if await self._healthy():
                    return
                await asyncio.sleep(0.25)
            raise RuntimeError("OpenCode sidecar did not become healthy within 15 seconds")

    async def close(self) -> None:
        """Terminate a sidecar owned by this app."""

        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.to_thread(self.process.wait, 8)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    async def _prompt(self, system: str, prompt: str, model_name: str | None = None) -> str:
        await self.ensure_started()
        provider_id, separator, model_id = (model_name or self.model).partition("/")
        model = (
            {"providerID": provider_id, "modelID": model_id}
            if separator
            else (model_name or self.model)
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
            created = await client.post(f"{self.base_url}/session", json={})
            created.raise_for_status()
            session_id = created.json()["id"]
            try:
                response = await client.post(
                    f"{self.base_url}/session/{session_id}/message",
                    json={
                        "system": system,
                        "model": model,
                        # Retrieval is performed separately and validated. The
                        # OAuth model may only reason over supplied material.
                        "tools": NO_TOOLS,
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                texts = [
                    part.get("text", "")
                    for part in payload.get("parts", [])
                    if part.get("type") == "text"
                ]
                if not texts:
                    raise RuntimeError("OpenCode returned no text")
                return "\n".join(texts)
            finally:
                try:
                    await client.delete(f"{self.base_url}/session/{session_id}")
                except httpx.HTTPError:
                    logger.debug("Could not delete OpenCode session %s", session_id)

    @staticmethod
    def _json_object(text: str) -> dict[str, Any]:
        """Parse a JSON object, tolerating a single Markdown code fence."""

        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Model response did not contain a JSON object")
        return json.loads(stripped[start : end + 1])

    async def analyze(self, request: AnalysisRequest) -> AnalysisPacket:
        """Extract evidence and interventions from the shared pool."""

        configuration = request.effective_configuration()
        copilot = configuration.copilot
        enabled_lenses = [
            LENS_NAMES[key]
            for key, enabled in copilot.lenses.model_dump().items()
            if enabled
        ]
        system = f"""{copilot.system_prompt}

Operating rules:
- return only the requested JSON object
- every evidence item must be directly supported by a transcript turn
- suggestions must be short enough to scan while listening
- use the shared evidence pool as working memory
- treat template.interviewer_guidance as active directives, not passive metadata
- do not invent external research, URLs, metrics, or claims
- when external validation would help, propose a specific research action instead

Depth protocol for every interview phase:
- lock onto the participant's most promising active thread; do not change topics merely because an initial answer was obtained
- establish, in order: the desired outcome; why it matters; current satisfaction or sufficiency; expected versus actual result; where progress gets stuck, slow, difficult, or goes nowhere; attempts/workarounds; and the consequence or priority
- use progressive why probes up to five times only while each answer reveals new meaning; vary the wording, reuse the participant's language, and stop before it feels mechanical
- prefer one recent concrete incident over general opinion, then connect that incident to the broader pattern
- ask one neutral question at a time; never bundle the ladder into a multi-part interrogation or imply the answer
- when a meaningful thread has an unresolved rung, include exactly one high-priority Clarification question for the earliest important missing rung; other suggestions must not distract from it
- move to another template phase only when the active thread is clear, no longer relevant, or the participant signals discomfort

Enabled specialist lenses: {", ".join(enabled_lenses)}.
Do not return suggestions or agent attribution from disabled lenses.
Stop after at most {copilot.limits.new_evidence_items} new evidence items and
{copilot.limits.suggestions} suggestions. Omit weak or duplicate items."""
        if copilot.promoted_evidence_first:
            evidence_key = lambda value: (
                value.id in request.focus_evidence_ids,
                value.promoted,
                value.pinned,
            )
        else:
            evidence_key = lambda value: (
                value.id in request.focus_evidence_ids,
                value.pinned,
            )
        context = {
            "template": configuration.template.model_dump(),
            "transcript": [
                turn.model_dump()
                for turn in request.transcript[-copilot.limits.transcript_turns :]
            ],
            "evidence": [
                item.model_dump()
                for item in sorted(
                    request.evidence,
                    key=evidence_key,
                    reverse=True,
                )[: copilot.limits.evidence_context_items]
            ],
        }
        prompt = f"""{copilot.task_prompt}

Interview state:
{json.dumps(context, ensure_ascii=False)}

Return exactly this JSON shape:
{{
  "suggestions": [{{
    "id": "suggestion_<stable short slug>",
    "agent": "Clarification|Opportunity|Bias guard|Memory|Research",
    "kind": "question|pattern|opportunity|warning|research",
    "text": "one concise intervention",
    "rationale": "one short evidence-based reason",
    "evidence_ids": ["existing evidence ids when relevant"],
    "priority": "low|medium|high"
  }}],
  "evidence": [{{
    "id": "<type>_<stable short slug>",
    "type": "fact|pain|quote|question|source|insight|tool|workflow",
    "text": "atomic claim or verbatim quote",
    "confidence": 0.0,
    "pinned": false,
    "promoted": false,
    "source": "transcript",
    "source_turn_ids": ["turn id"],
    "related_evidence_ids": ["ids"],
    "agents": ["Clarification|Opportunity|Bias guard|Memory|Research"],
    "url": null
  }}]
}}"""
        raw = await self._prompt(system, prompt, configuration.runtime.model)
        packet = AnalysisPacket.model_validate(self._json_object(raw))
        allowed_lenses = set(enabled_lenses)
        filtered_suggestions = [
            suggestion for suggestion in packet.suggestions if suggestion.agent in allowed_lenses
        ][: copilot.limits.suggestions]
        filtered_evidence = [
            item
            for item in packet.evidence
            if not item.agents or any(agent in allowed_lenses for agent in item.agents)
        ][: copilot.limits.new_evidence_items]
        return packet.model_copy(
            update={
                "suggestions": filtered_suggestions,
                "evidence": filtered_evidence,
                "engine": "openai",
            }
        )

    async def research(
        self,
        request: ResearchRequest,
        trigger: ResearchTrigger,
        documents: list[SearchDocument],
    ) -> list[ResearchDraft]:
        """Turn already-retrieved source text into zero to two interview moves."""

        configuration = request.effective_configuration()
        source_payload = [
            {
                "title": document.title,
                "url": document.url,
                "published": document.published,
                "content": document.content[:8_000],
            }
            for document in documents[:5]
        ]
        context = {
            "template": configuration.template.model_dump(),
            "trigger": {
                "claim": trigger.text,
                "kind": trigger.kind,
                "turn_id": trigger.turn_id,
                "related_evidence_ids": list(trigger.related_evidence_ids),
            },
            "recent_transcript": [turn.model_dump() for turn in request.transcript[-8:]],
            "relevant_evidence": [
                item.model_dump()
                for item in request.evidence
                if item.id in trigger.related_evidence_ids or item.promoted or item.pinned
            ][:12],
            "retrieved_sources": source_payload,
        }
        system = """You are a silent internet research partner beside a live interviewer.

An internet result earns screen space only if it changes the interviewer's next useful
question. Act as a verifier, counterexample finder, existing-solution detector, local
constraint finder, stakeholder perspective finder, or feasibility connector.

Never lecture, summarize the web generally, pitch a solution, invent market size, or
return an interesting fact without a neutral follow-up. Prefer counterevidence over
confirmation. Use only the retrieved source text below. If support is weak, return no
card. Return JSON only."""
        prompt = f"""Evaluate this live interview state:
{json.dumps(context, ensure_ascii=False)}

Return zero to two cards. Each must use exactly one retrieved URL and contain a short
verbatim excerpt copied from that source proving the signal. The excerpt is internal
validation material and will not be displayed. Community posts must be labelled
anecdotal in the signal. Older sources must be described as background, not current.

Return exactly:
{{
  "cards": [{{
    "signal": "one directly supported finding, at most two sentences",
    "ask_next": "one neutral question that advances this interview?",
    "judge_lens": "Real|New|Good|Feasible",
    "source_url": "an exact URL from retrieved_sources",
    "confidence": 0.0,
    "supporting_excerpt": "an exact short excerpt copied from that source"
  }}]
}}"""
        raw = await self._prompt(system, prompt, configuration.runtime.model)
        payload = self._json_object(raw)
        values = payload.get("cards", [])
        if not isinstance(values, list):
            return []
        drafts: list[ResearchDraft] = []
        for value in values[:2]:
            try:
                drafts.append(ResearchDraft.model_validate(value))
            except ValueError:
                continue
        return drafts

    async def report(self, request: ReportRequest) -> InterviewReport:
        """Create an evidence-bounded end-of-interview synthesis."""

        configuration = request.effective_configuration()
        report_configuration = configuration.report
        disabled_sections = [
            name for name, enabled in report_configuration.sections.model_dump().items() if not enabled
        ]
        system = f"""{report_configuration.system_prompt}

Use only the supplied transcript and evidence. Separate observation from inference.
Do not invent market validation. Return only the requested JSON.
Make the saved report comprehensive rather than terse: retain every distinct,
decision-useful behavior, motivation, expectation gap, workaround, consequence,
and unresolved question that the transcript supports. Prefer specific detail over
generic compression, but remove duplicates and transcription noise.
Next-step instruction: {report_configuration.next_step_instruction}
Disabled sections ({", ".join(disabled_sections) or "none"}) must retain their normal
JSON field but use an empty string or empty array.
{"Score and build coverage against template.success_metrics. Mark a criterion complete only when the transcript directly supports every clause in it; never fill a missing recency, consequence, priority, frequency, or affected-person detail by inference. A missing detail named in unanswered_questions must remain incomplete in coverage." if report_configuration.score_against_success_metrics else "Do not score success metrics; return score 0."}"""
        context = {
            "template": configuration.template.model_dump(),
            "transcript": [turn.model_dump() for turn in request.transcript],
            "evidence": [item.model_dump() for item in request.evidence],
        }
        prompt = f"""{report_configuration.task_prompt}

Completed interview:
{json.dumps(context, ensure_ascii=False)}

Return exactly:
{{
  "summary": "5-8 sentence synthesis of the participant, their context, strongest behavior patterns, and the central decision implication",
  "top_pains": ["every distinct supported pain, friction, cost, trust issue, or unmet outcome; normally 4-10 items for a substantial interview"],
  "key_facts": ["specific behaviors, motivations, workflows, tools, frequency, constraints, workarounds, and adjacent needs; normally 8-18 items for a substantial interview"],
  "quotes": ["6-10 short verbatim transcript quotes when available; do not repair wording or invent clarity"],
  "unanswered_questions": ["important unknowns that would change a product, research, or pilot decision; normally 6-12 items"],
  "opportunity": "2-4 sentence bounded hypothesis connecting the observed behavior, current workaround, and plausible value; not a proven claim",
  "next_step": "2-4 sentence least-effort validation step with who to recruit, what to test, and what observable result would count",
  "score": 0,
  "coverage": [{{"label": "criterion", "complete": true}}]
}}"""
        raw = await self._prompt(system, prompt, configuration.runtime.model)
        report = InterviewReport.model_validate(self._json_object(raw))
        sections = report_configuration.sections
        updates: dict[str, Any] = {"engine": "openai"}
        for name in ("top_pains", "key_facts", "quotes", "unanswered_questions", "coverage"):
            if not getattr(sections, name):
                updates[name] = []
        for name in ("summary", "opportunity", "next_step"):
            if not getattr(sections, name):
                updates[name] = ""
        if not report_configuration.score_against_success_metrics:
            updates["score"] = 0
        return report.model_copy(update=updates)
