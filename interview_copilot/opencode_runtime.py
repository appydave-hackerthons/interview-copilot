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
)

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "openai/gpt-5.6-sol"


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

    async def _prompt(self, system: str, prompt: str) -> str:
        await self.ensure_started()
        provider_id, separator, model_id = self.model.partition("/")
        model = (
            {"providerID": provider_id, "modelID": model_id}
            if separator
            else self.model
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

        system = """Role: a silent expert research partner beside a human interviewer.

Goal: improve the interview in real time by extracting grounded evidence and offering the smallest useful next interventions.

Success criteria:
- return only the requested JSON object
- every evidence item is directly supported by a transcript turn
- suggestions are short enough to scan while listening
- use the shared evidence pool as working memory
- do not invent external research, URLs, metrics, or claims
- when external validation would help, propose a specific research action instead

Specialist lenses: Clarification, Opportunity, Bias guard, Memory, Research.

Stop after at most 4 new evidence items and 4 suggestions. Omit weak or duplicate items."""
        context = {
            "template": request.template.model_dump(),
            "transcript": [turn.model_dump() for turn in request.transcript[-18:]],
            "evidence": [
                item.model_dump()
                for item in sorted(
                    request.evidence,
                    key=lambda value: (
                        value.id in request.focus_evidence_ids,
                        value.promoted,
                        value.pinned,
                    ),
                    reverse=True,
                )[:30]
            ],
        }
        prompt = f"""Analyse this interview state:
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
        raw = await self._prompt(system, prompt)
        packet = AnalysisPacket.model_validate(self._json_object(raw))
        return packet.model_copy(update={"engine": "openai"})

    async def report(self, request: ReportRequest) -> InterviewReport:
        """Create an evidence-bounded end-of-interview synthesis."""

        system = """Role: an evidence-first customer discovery analyst.

Goal: turn one finished interview into a concise decision-ready report.

Use only the supplied transcript and evidence. Separate observation from inference. Do not invent market validation. The next step must be the least-effort useful test, not a broad product roadmap. Return only the requested JSON."""
        context = {
            "template": request.template.model_dump(),
            "transcript": [turn.model_dump() for turn in request.transcript],
            "evidence": [item.model_dump() for item in request.evidence],
        }
        prompt = f"""Synthesize this completed interview:
{json.dumps(context, ensure_ascii=False)}

Return exactly:
{{
  "summary": "2-3 sentence synthesis",
  "top_pains": ["..."],
  "key_facts": ["..."],
  "quotes": ["verbatim transcript quote"],
  "unanswered_questions": ["..."],
  "opportunity": "bounded hypothesis, not a proven claim",
  "next_step": "one least-effort validation step",
  "score": 0,
  "coverage": [{{"label": "criterion", "complete": true}}]
}}"""
        raw = await self._prompt(system, prompt)
        report = InterviewReport.model_validate(self._json_object(raw))
        return report.model_copy(update={"engine": "openai"})
