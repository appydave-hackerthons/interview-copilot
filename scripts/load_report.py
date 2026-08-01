#!/usr/bin/env python3
"""Rehydrate an exported report JSON back into a running Interview Copilot archive.

An interview produces a report at /reports/N. Export it (the JSON link) and this puts it
back — into this machine's archive, or a teammate's, or a fresh checkout before a demo.

    uv run python scripts/load_report.py path/to/report.json

It deliberately goes through the app's own models and ReportArchive rather than writing
files by hand. If Ethan changes the schema this fails loudly on validation instead of
silently writing a report the app can't read.

    --archive-root PATH   where to write (default: the app's configured root)
    --keep-id             preserve the original report_id instead of allocating a new one
    --dry-run             validate and report, write nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from interview_copilot.archive import InterviewArchive  # noqa: E402
from interview_copilot.configuration import (  # noqa: E402
    get_default_configuration,
    resolve_archive_root,
)
from interview_copilot.models import (  # noqa: E402
    EvidenceItem,
    InterviewReport,
    InterviewTemplate,
    PersistentInterviewReport,
    TranscriptTurn,
)
from interview_copilot.reports import ReportArchive, render_report_html  # noqa: E402


def default_archive_root() -> Path:
    config = get_default_configuration()
    return resolve_archive_root(config.runtime.archive_root)


def load_document(path: Path) -> PersistentInterviewReport:
    """Parse an export. Accepts a full persisted report, or a bare InterviewReport."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    try:
        return PersistentInterviewReport.model_validate(raw)
    except Exception:
        pass

    # A bare InterviewReport export — no transcript, evidence or ids. Still loadable,
    # but say so rather than inventing the missing halves silently.
    report = InterviewReport.model_validate(raw)
    print("  note: bare InterviewReport — no transcript or evidence in this export")
    return PersistentInterviewReport(
        **report.model_dump(),
        report_id=int(raw.get("report_id", 0)) or 0,
        session_id=str(raw.get("session_id", f"imported-{path.stem}")),
        created_at=str(raw.get("created_at", "")),
        template=InterviewTemplate(),
        transcript=[],
        evidence=[],
        html_url="",
        json_url="",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="exported report .json")
    parser.add_argument("--archive-root", type=Path, default=None)
    parser.add_argument("--keep-id", action="store_true", help="preserve the original report_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"error: no such file: {args.source}", file=sys.stderr)
        return 1

    print(f"reading {args.source}")
    try:
        document = load_document(args.source)
    except Exception as exc:
        print(f"error: does not validate against the app's models — {exc}", file=sys.stderr)
        return 1

    print(f"  report  #{document.report_id} · session {document.session_id}")
    print(f"  score   {document.score} · {sum(c.complete for c in document.coverage)}/{len(document.coverage)} criteria")
    print(f"  content {len(document.transcript)} turns · {len(document.evidence)} evidence · "
          f"{len(document.top_pains)} pains · {len(document.quotes)} quotes")

    if args.dry_run:
        print("dry run — nothing written")
        return 0

    root = (args.archive_root.resolve() if args.archive_root else default_archive_root())
    root.mkdir(parents=True, exist_ok=True)
    archive = ReportArchive(InterviewArchive(root).root)

    if args.keep_id:
        # Write in place under the original id, bypassing allocation.
        directory = root / "reports" / str(document.report_id)
        if directory.exists():
            print(f"error: report {document.report_id} already exists at {directory} — "
                  f"drop --keep-id to allocate a new id instead", file=sys.stderr)
            return 1
        directory.mkdir(parents=True)
        (directory / "report.json").write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (directory / "report.html").write_text(render_report_html(document), encoding="utf-8")
        saved_id = document.report_id
    else:
        # The normal path — through the app's own save(), which allocates the next id
        # and regenerates the HTML. Anything the app does on save happens here too.
        saved = archive.save(
            session_id=document.session_id,
            report=InterviewReport.model_validate(
                {k: v for k, v in document.model_dump().items() if k in InterviewReport.model_fields}
            ),
            template=document.template,
            transcript=[TranscriptTurn.model_validate(t.model_dump()) for t in document.transcript],
            evidence=[EvidenceItem.model_validate(e.model_dump()) for e in document.evidence],
        )
        saved_id = saved.report_id

    print(f"\nloaded → {root / 'reports' / str(saved_id)}")
    print(f"  view   http://127.0.0.1:8787/reports/{saved_id}")
    print(f"  json   http://127.0.0.1:8787/api/reports/{saved_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
