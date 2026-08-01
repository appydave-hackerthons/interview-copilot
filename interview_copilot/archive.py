"""Durable, local interview audio and transcript storage."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from interview_copilot.configuration import configuration_to_yaml
from interview_copilot.models import InterviewConfiguration


class InterviewArchive:
    """Persist every audio segment and its Whisper result to local disk."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._write_lock = threading.Lock()

    @staticmethod
    def _safe_session_id(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
        return cleaned[:96] or "unassigned"

    @staticmethod
    def _safe_suffix(value: str) -> str:
        return value.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", value.lower()) else ".bin"

    def _session_dir(self, session_id: str) -> Path:
        directory = self.root / self._safe_session_id(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = directory / "session.json"
        if not metadata.exists():
            payload = {
                "session_id": self._safe_session_id(session_id),
                "created_at": datetime.now(UTC).isoformat(),
            }
            metadata.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return directory

    def start_session(
        self,
        session_id: str,
        configuration: InterviewConfiguration,
        *,
        mode: str,
        active_model: str,
        active_whisper_model: str | None,
        active_whisper_language: str,
    ) -> Path:
        """Freeze configuration and runtime metadata before audio capture."""

        directory = self.root / self._safe_session_id(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        configuration_text = configuration_to_yaml(configuration)
        configuration_path = directory / "configuration.yaml"
        metadata_path = directory / "session.json"
        payload = {
            "session_id": self._safe_session_id(session_id),
            "created_at": datetime.now(UTC).isoformat(),
            "mode": mode,
            "schema_version": configuration.schema_version,
            "model": configuration.runtime.model,
            "active_model": active_model,
            "whisper": {
                "language": configuration.audio.whisper_language,
                "model": configuration.audio.whisper_model,
                "active_language": active_whisper_language,
                "active_model": active_whisper_model,
            },
        }

        with self._write_lock:
            if configuration_path.exists():
                if configuration_path.read_text(encoding="utf-8") != configuration_text:
                    raise ValueError("This session id already has a different frozen configuration")
            else:
                self._write_and_sync(configuration_path, configuration_text, exclusive=True)
            if not metadata_path.exists():
                self._write_and_sync(
                    metadata_path,
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    exclusive=True,
                )
        return directory

    def save_audio(self, session_id: str, sequence: int, suffix: str, audio: bytes) -> Path:
        """Write an audio segment before transcription and fsync it."""

        directory = self._session_dir(session_id)
        audio_dir = directory / "audio"
        audio_dir.mkdir(exist_ok=True)
        filename = f"chunk-{max(sequence, 0):06d}-{uuid4().hex[:8]}{self._safe_suffix(suffix)}"
        path = audio_dir / filename
        with path.open("xb") as handle:
            handle.write(audio)
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def append_result(
        self,
        *,
        session_id: str,
        sequence: int,
        speaker: str,
        elapsed_seconds: int,
        audio_path: Path | None,
        text: str | None,
        error: str | None = None,
    ) -> None:
        """Append one durable JSONL record and a human-readable transcript line."""

        directory = self._session_dir(session_id)
        entry = {
            "sequence": sequence,
            "recorded_at": datetime.now(UTC).isoformat(),
            "speaker": speaker,
            "elapsed_seconds": elapsed_seconds,
            "audio_file": str(audio_path.relative_to(directory)) if audio_path else None,
            "status": "transcribed" if error is None else "error",
            "text": text or "",
            "error": error,
        }
        safe_elapsed = max(elapsed_seconds, 0)
        elapsed = f"{safe_elapsed // 60:02d}:{safe_elapsed % 60:02d}"
        readable = text.strip() if text else f"[Transcription failed: {error or 'unknown error'}]"
        markdown = f"- **[{elapsed}] {speaker}:** {readable}\n"

        with self._write_lock:
            self._append_and_sync(directory / "transcript.jsonl", json.dumps(entry, ensure_ascii=False) + "\n")
            self._append_and_sync(directory / "transcript.md", markdown)

    @staticmethod
    def _append_and_sync(path: Path, value: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _write_and_sync(path: Path, value: str, *, exclusive: bool = False) -> None:
        mode = "x" if exclusive else "w"
        with path.open(mode, encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
