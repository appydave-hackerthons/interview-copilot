"""Durable numbered interview reports and their standalone HTML rendering."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from uuid import uuid4

from interview_copilot.models import (
    EvidenceItem,
    InterviewReport,
    InterviewTemplate,
    PersistentInterviewReport,
    ReportIndexItem,
    TranscriptTurn,
)


def _safe(value: object) -> str:
    return escape(str(value), quote=True)


def _clock(seconds: int) -> str:
    safe_seconds = max(seconds, 0)
    hours, remainder = divmod(safe_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _paragraphs(value: str) -> str:
    values = [part.strip() for part in value.split("\n\n") if part.strip()]
    return "".join(f"<p>{_safe(part)}</p>" for part in values) or '<p class="empty">Not captured.</p>'


def _list(items: list[str], *, ordered: bool = False, quotes: bool = False) -> str:
    if not items:
        return '<p class="empty">None captured.</p>'
    tag = "ol" if ordered else "ul"
    rendered = "".join(
        f'<li>{"<blockquote>“" if quotes else ""}{_safe(item.strip("“”\""))}{"”</blockquote>" if quotes else ""}</li>'
        for item in items
    )
    return f'<{tag} class="report-list">{rendered}</{tag}>'


def _evidence_card(item: EvidenceItem) -> str:
    source_link = ""
    source_url = item.url or (str(item.provenance.source_url) if item.provenance else None)
    if source_url and source_url.startswith(("http://", "https://")):
        source_title = item.provenance.source_title if item.provenance else "Open source"
        source_link = (
            f'<a href="{_safe(source_url)}" target="_blank" rel="noreferrer">'
            f'{_safe(source_title)} ↗</a>'
        )
    promoted = '<span class="tag promoted">Promoted</span>' if item.promoted else ""
    agents = ", ".join(item.agents)
    meta = " · ".join(part for part in (
        item.source.title(),
        f"{round(item.confidence * 100)}% confidence",
        agents,
    ) if part)
    provenance = ""
    if item.provenance:
        provenance = (
            '<div class="provenance">'
            f'<strong>{_safe(item.provenance.judge_lens)} lens</strong>'
            f'<span>Triggered by: {_safe(item.provenance.why_now)}</span>'
            '</div>'
        )
    return (
        '<article class="evidence-card">'
        f'<div class="evidence-top"><span class="tag">{_safe(item.type)}</span>{promoted}</div>'
        f'<p>{_safe(item.text)}</p><small>{_safe(meta)}</small>{source_link}{provenance}'
        '</article>'
    )


def _complete_evidence(
    report_id: int,
    report: InterviewReport,
    retained: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Keep live evidence and make report-only findings explicit in the ledger."""

    values = list(retained)
    seen = {item.text.strip().casefold() for item in values}

    def add(items: list[str], evidence_type: str, confidence: float, source: str) -> None:
        for index, text in enumerate(items, start=1):
            normalized = text.strip().casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(EvidenceItem(
                id=f"report-{report_id}-{evidence_type}-{index:02d}",
                type=evidence_type,  # type: ignore[arg-type]
                text=text,
                confidence=confidence,
                promoted=False,
                pinned=False,
                source=source,  # type: ignore[arg-type]
                agents=["Memory"],
            ))

    add(report.top_pains, "pain", 0.82, "agent")
    add(report.key_facts, "fact", 0.84, "agent")
    add(report.quotes, "quote", 0.94, "transcript")
    if report.opportunity.strip() and report.opportunity.strip().casefold() not in seen:
        values.append(EvidenceItem(
            id=f"report-{report_id}-insight-01",
            type="insight",
            text=report.opportunity,
            confidence=0.66,
            promoted=True,
            pinned=True,
            source="agent",
            agents=["Opportunity"],
        ))
    return values


def render_report_html(document: PersistentInterviewReport) -> str:
    """Render one self-contained, print-friendly HTML report."""

    report_number = f"{document.report_id:03d}"
    completed = sum(item.complete for item in document.coverage)
    evidence_html = "".join(_evidence_card(item) for item in document.evidence)
    if not evidence_html:
        evidence_html = '<p class="empty">No separate evidence cards were retained; findings above come directly from the archived transcript.</p>'
    coverage_html = "".join(
        '<li class="complete">✓ ' + _safe(item.label) + "</li>"
        if item.complete else '<li class="missing">— ' + _safe(item.label) + "</li>"
        for item in document.coverage
    ) or '<li class="missing">— No coverage criteria configured</li>'
    transcript_html = "".join(
        '<article class="turn">'
        f'<time>{_safe(_clock(turn.elapsed_seconds))}</time>'
        f'<div><strong>{_safe(turn.speaker)}</strong><p>{_safe(turn.text)}</p></div>'
        '</article>'
        for turn in document.transcript
    ) or '<p class="empty">No transcript turns were captured.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Report {report_number} · {_safe(document.template.name)}</title>
  <style>
    :root {{ --canvas:#f3eee4; --paper:#fbf8f1; --ink:#292821; --muted:#716a60; --line:#dcd3c5; --soft:#e9e2d7; --olive:#596043; --clay:#a96248; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:var(--canvas); font:14px/1.55 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    a {{ color:var(--olive); }}
    .topbar {{ position:sticky; top:0; z-index:5; min-height:62px; padding:0 max(24px,4vw); display:flex; align-items:center; justify-content:space-between; gap:18px; border-bottom:1px solid var(--line); background:rgba(243,238,228,.94); backdrop-filter:blur(12px); }}
    .topbar a {{ text-decoration:none; font-size:12px; font-weight:700; }}
    .topbar nav {{ display:flex; flex-wrap:wrap; gap:16px; }}
    .shell {{ width:min(1180px,calc(100% - 40px)); margin:0 auto; padding:68px 0 100px; }}
    .eyebrow,.section-label {{ margin:0 0 14px; color:var(--olive); font-size:10px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1fr) 260px; gap:70px; padding-bottom:55px; border-bottom:1px solid var(--line); }}
    h1,h2,h3 {{ font-family:"Iowan Old Style",Baskerville,Georgia,serif; font-weight:400; }}
    h1 {{ max-width:820px; margin:0 0 24px; font-size:clamp(48px,7vw,86px); line-height:.94; letter-spacing:-.045em; }}
    .hero-copy {{ max-width:760px; color:#5f594f; font:19px/1.6 "Iowan Old Style",Baskerville,Georgia,serif; }}
    .hero-copy p {{ margin:0 0 14px; }}
    .score {{ align-self:end; padding:25px; border:1px solid var(--line); background:rgba(251,248,241,.75); }}
    .score strong {{ display:block; font:60px/.9 "Iowan Old Style",Georgia,serif; }}
    .score span {{ display:block; margin-top:12px; color:var(--muted); font-size:11px; }}
    .metadata {{ display:grid; grid-template-columns:repeat(4,1fr); border-left:1px solid var(--line); margin:0 0 62px; }}
    .metadata div {{ min-height:88px; padding:20px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
    .metadata small {{ display:block; margin-bottom:5px; color:#948c7e; font-size:9px; letter-spacing:.12em; text-transform:uppercase; }}
    .metadata strong {{ font-size:12px; overflow-wrap:anywhere; }}
    .notice {{ margin:0 0 36px; padding:13px 15px; border:1px solid #dec9aa; background:#f4e6d0; color:#745d39; font-size:12px; }}
    .summary-grid {{ display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--line); border-left:1px solid var(--line); margin-bottom:56px; }}
    .panel {{ min-height:300px; padding:30px 32px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); background:rgba(251,248,241,.62); }}
    .panel h2,.decision h2,.long-section h2 {{ margin:0 0 22px; font-size:27px; line-height:1.08; }}
    .report-list {{ margin:0; padding-left:20px; }}
    .report-list li {{ padding:10px 0; border-top:1px solid var(--soft); }}
    .report-list blockquote {{ margin:0; color:#565047; font:italic 17px/1.5 "Iowan Old Style",Georgia,serif; }}
    .decision-row {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:56px; }}
    .decision {{ padding:30px; color:#f8f5ec; background:#4c523c; }}
    .decision.next {{ background:#954f39; }}
    .decision p {{ margin:0; font:18px/1.55 "Iowan Old Style",Georgia,serif; white-space:pre-line; }}
    .decision small {{ display:block; margin-top:22px; opacity:.72; text-transform:uppercase; letter-spacing:.1em; font-size:9px; }}
    .long-section {{ padding:48px 0; border-top:1px solid var(--line); }}
    .coverage {{ list-style:none; display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin:0; padding:0; }}
    .coverage li {{ padding:13px 14px; border:1px solid var(--line); background:rgba(251,248,241,.56); }}
    .coverage .complete {{ color:var(--olive); }} .coverage .missing {{ color:#8d7569; }}
    .evidence-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
    .evidence-card {{ min-height:190px; padding:19px; border:1px solid var(--line); background:var(--paper); }}
    .evidence-top {{ display:flex; gap:5px; }} .tag {{ padding:4px 6px; border-radius:999px; background:#e7e8dc; color:var(--olive); font-size:8px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }} .tag.promoted {{ background:#eee0d7; color:var(--clay); }}
    .evidence-card p {{ font:16px/1.45 "Iowan Old Style",Georgia,serif; }} .evidence-card small,.evidence-card a {{ display:block; margin-top:9px; color:var(--muted); font-size:9px; }}
    .provenance {{ margin-top:14px; padding-top:12px; border-top:1px solid var(--soft); }} .provenance strong,.provenance span {{ display:block; font-size:9px; }} .provenance span {{ margin-top:5px; color:var(--muted); }}
    .transcript {{ border-top:1px solid var(--line); }}
    .turn {{ display:grid; grid-template-columns:72px 1fr; gap:20px; padding:14px 0; border-bottom:1px solid var(--soft); }}
    .turn time {{ color:#989083; font:10px ui-monospace,SFMono-Regular,Menlo,monospace; }} .turn strong {{ display:block; color:var(--olive); font-size:9px; letter-spacing:.08em; text-transform:uppercase; }} .turn p {{ margin:4px 0 0; color:#4d4942; }}
    .empty {{ color:#92897c; font-style:italic; }}
    footer {{ padding-top:34px; border-top:1px solid var(--line); color:#8d8578; font-size:10px; }}
    @media (max-width:780px) {{ .topbar {{ align-items:flex-start; padding-top:14px; padding-bottom:14px; }} .topbar nav {{ justify-content:flex-end; }} .hero,.summary-grid,.decision-row {{ grid-template-columns:1fr; }} .hero {{ gap:30px; }} .metadata {{ grid-template-columns:1fr 1fr; }} .evidence-grid {{ grid-template-columns:1fr; }} .coverage {{ grid-template-columns:1fr; }} .panel {{ min-height:0; }} }}
    @media print {{ .topbar {{ display:none; }} body {{ background:white; }} .shell {{ width:100%; padding:20px; }} .panel,.score,.evidence-card,.coverage li {{ background:white; break-inside:avoid; }} .turn {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
  <header class="topbar">
    <a href="/">✦ Interview Copilot</a>
    <nav><a href="/reports">All reports</a><a href="{_safe(document.json_url)}">JSON</a><a href="/reports/{document.report_id}/download">Download HTML</a></nav>
  </header>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Persistent interview report · {report_number}</p>
        <h1>{_safe(document.template.name)}</h1>
        <div class="hero-copy">{_paragraphs(document.summary)}</div>
      </div>
      <aside class="score"><strong>{document.score}</strong><span>Interview completeness · {completed} of {len(document.coverage)} criteria covered</span></aside>
    </section>
    <section class="metadata">
      <div><small>Report</small><strong>#{report_number}</strong></div>
      <div><small>Created</small><strong>{_safe(document.created_at)}</strong></div>
      <div><small>Conversation</small><strong>{len(document.transcript)} transcript turns</strong></div>
      <div><small>Synthesis</small><strong>{_safe(document.engine.title())} engine</strong></div>
    </section>
    {f'<div class="notice">{_safe(document.notice)}</div>' if document.notice else ''}
    <section class="summary-grid">
      <article class="panel"><p class="section-label">What matters</p><h2>Top pain points</h2>{_list(document.top_pains, ordered=True)}</article>
      <article class="panel"><p class="section-label">What we learned</p><h2>Key facts &amp; behaviors</h2>{_list(document.key_facts)}</article>
      <article class="panel"><p class="section-label">In their words</p><h2>Important quotes</h2>{_list(document.quotes, quotes=True)}</article>
      <article class="panel"><p class="section-label">What is missing</p><h2>Unanswered questions</h2>{_list(document.unanswered_questions)}</article>
    </section>
    <section class="decision-row">
      <article class="decision"><p class="section-label">Opportunity hypothesis</p><h2>Where the evidence points</h2>{_paragraphs(document.opportunity)}<small>Inference — validate before treating as fact</small></article>
      <article class="decision next"><p class="section-label">Least-effort next step</p><h2>What to do next</h2>{_paragraphs(document.next_step)}<small>One useful test, not a roadmap</small></article>
    </section>
    <section class="long-section"><p class="section-label">Interview quality</p><h2>Coverage against success signals</h2><ul class="coverage">{coverage_html}</ul></section>
    <section class="long-section"><p class="section-label">Collected material</p><h2>Complete evidence ledger</h2><div class="evidence-grid">{evidence_html}</div></section>
    <section class="long-section"><p class="section-label">Source of truth</p><h2>Full conversation transcript</h2><div class="transcript">{transcript_html}</div></section>
    <footer>Report #{report_number} · Session {_safe(document.session_id)} · Frozen locally by Interview Copilot.</footer>
  </main>
</body>
</html>
"""


def render_report_index(items: list[ReportIndexItem]) -> str:
    cards = "".join(
        '<article><div><span>Report ' + f'{item.report_id:03d}' + '</span>'
        f'<h2>{_safe(item.template_name)}</h2><p>{_safe(item.summary)}</p></div>'
        f'<footer><small>{_safe(item.created_at)} · {item.transcript_turns} turns · {item.evidence_items} evidence items</small>'
        f'<a href="{_safe(item.html_url)}">Open full report →</a></footer></article>'
        for item in items
    ) or '<div class="empty"><h2>No persistent reports yet</h2><p>End an interview to create the first numbered report.</p></div>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Interview reports</title><style>
    :root{{--canvas:#f3eee4;--paper:#fbf8f1;--ink:#292821;--muted:#756e63;--line:#dcd3c5;--olive:#596043}}*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.5 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}nav{{height:72px;padding:0 max(24px,5vw);display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}}a{{color:var(--olive);font-weight:700;text-decoration:none}}main{{width:min(1000px,calc(100% - 40px));margin:0 auto;padding:70px 0 100px}}h1,h2{{font-family:"Iowan Old Style",Georgia,serif;font-weight:400}}h1{{margin:0 0 14px;font-size:clamp(48px,7vw,78px);letter-spacing:-.045em;line-height:1}}.lede{{max-width:650px;margin:0 0 50px;color:var(--muted);font:18px/1.55 "Iowan Old Style",Georgia,serif}}article{{padding:28px 30px;border:1px solid var(--line);border-bottom:0;background:rgba(251,248,241,.68)}}article:last-child{{border-bottom:1px solid var(--line)}}article span{{color:var(--olive);font-size:9px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}}article h2{{margin:5px 0 10px;font-size:28px}}article p{{max-width:780px;margin:0;color:#5f594f}}article footer{{display:flex;justify-content:space-between;gap:20px;margin-top:22px;padding-top:15px;border-top:1px solid #e8e0d4}}article small{{color:#938a7d}}.empty{{padding:50px;border:1px solid var(--line);background:var(--paper)}}@media(max-width:620px){{article footer{{align-items:flex-start;flex-direction:column}}}}
  </style></head><body><nav><a href="/">✦ Interview Copilot</a><span>Persistent archive</span></nav><main><h1>Interview reports</h1><p class="lede">Every completed conversation is frozen as a numbered, self-contained report with its synthesis, evidence, coverage, and full transcript.</p>{cards}</main></body></html>"""


class ReportArchive:
    """Persist reports under one archive root with monotonic numeric ids."""

    def __init__(self, archive_root: Path) -> None:
        self.root = archive_root / "reports"
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()

    def _report_dir(self, report_id: int) -> Path:
        return self.root / f"{report_id:06d}"

    def _next_id(self) -> int:
        ids = [int(path.name) for path in self.root.iterdir() if path.is_dir() and path.name.isdigit()]
        return max(ids, default=0) + 1

    def save(
        self,
        *,
        session_id: str,
        report: InterviewReport,
        template: InterviewTemplate,
        transcript: list[TranscriptTurn],
        evidence: list[EvidenceItem],
    ) -> PersistentInterviewReport:
        with self._write_lock:
            report_id = self._next_id()
            directory = self._report_dir(report_id)
            while directory.exists():
                report_id += 1
                directory = self._report_dir(report_id)
            directory.mkdir(parents=True, exist_ok=False)
            document = PersistentInterviewReport(
                **report.model_dump(),
                report_id=report_id,
                session_id=session_id,
                created_at=datetime.now(UTC).isoformat(),
                template=template,
                transcript=transcript,
                evidence=_complete_evidence(report_id, report, evidence),
                html_url=f"/reports/{report_id}",
                json_url=f"/api/reports/{report_id}",
            )
            self._write_and_sync(
                directory / "report.json",
                json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            )
            self._write_and_sync(directory / "report.html", render_report_html(document))
            return document

    def enrich_legacy_report(self, report_id: int) -> PersistentInterviewReport:
        """Make synthesized findings explicit for a snapshot created by the old writer."""

        with self._write_lock:
            document = self.load(report_id)
            evidence = _complete_evidence(report_id, document, document.evidence)
            if evidence == document.evidence:
                return document
            updated = document.model_copy(update={"evidence": evidence})
            self._replace_and_sync(
                self._report_dir(report_id) / "report.json",
                json.dumps(updated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            )
            self._replace_and_sync(
                self._report_dir(report_id) / "report.html",
                render_report_html(updated),
            )
            return updated

    def load(self, report_id: int) -> PersistentInterviewReport:
        path = self._report_dir(report_id) / "report.json"
        if not path.is_file():
            raise FileNotFoundError(report_id)
        return PersistentInterviewReport.model_validate_json(path.read_text(encoding="utf-8"))

    def html_path(self, report_id: int) -> Path:
        path = self._report_dir(report_id) / "report.html"
        if not path.is_file():
            raise FileNotFoundError(report_id)
        return path

    def list(self) -> list[ReportIndexItem]:
        values: list[ReportIndexItem] = []
        for directory in sorted(self.root.iterdir(), reverse=True):
            if not directory.is_dir() or not directory.name.isdigit():
                continue
            try:
                document = self.load(int(directory.name))
            except (OSError, ValueError):
                continue
            values.append(ReportIndexItem(
                report_id=document.report_id,
                session_id=document.session_id,
                created_at=document.created_at,
                template_name=document.template.name,
                summary=document.summary,
                score=document.score,
                transcript_turns=len(document.transcript),
                evidence_items=len(document.evidence),
                html_url=document.html_url,
                json_url=document.json_url,
            ))
        return values

    @staticmethod
    def _write_and_sync(path: Path, value: str) -> None:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _replace_and_sync(path: Path, value: str) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
