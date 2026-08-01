"""Local audio transcription through whisper.cpp."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class WhisperTranscriber:
    """Convert browser audio to WAV and transcribe it with whisper-cli."""

    def __init__(self) -> None:
        self.binary = os.getenv("WHISPER_BIN") or shutil.which("whisper-cli")
        self.ffmpeg = shutil.which("ffmpeg")
        self.model = self._find_model()
        self.language = os.getenv("WHISPER_LANGUAGE", "auto")

    @staticmethod
    def _find_model() -> str | None:
        configured = os.getenv("WHISPER_MODEL")
        if configured and Path(configured).expanduser().is_file():
            return str(Path(configured).expanduser())
        candidates = [
            Path.home() / ".cache/whisper/ggml-small.en.bin",
            Path.home() / ".cache/whisper/ggml-base.en.bin",
            Path("/opt/homebrew/opt/whisper-cpp/share/whisper-cpp/for-tests-ggml-tiny.bin"),
        ]
        return next((str(path) for path in candidates if path.is_file()), None)

    @property
    def available(self) -> bool:
        return bool(self.binary and self.ffmpeg and self.model)

    @staticmethod
    def _read_text(payload: dict) -> str:
        if isinstance(payload.get("text"), str):
            return payload["text"].strip()
        chunks = payload.get("transcription") or payload.get("segments") or []
        return " ".join(
            str(chunk.get("text", "")).strip()
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("text")
        ).strip()

    def transcribe(self, audio: bytes, suffix: str = ".webm") -> str:
        """Transcribe one self-contained browser recording chunk."""

        if not self.available:
            raise RuntimeError("Local Whisper is not fully configured")
        with tempfile.TemporaryDirectory(prefix="interview-copilot-") as temp:
            work = Path(temp)
            source = work / f"source{suffix}"
            wave = work / "chunk.wav"
            output = work / "result"
            source.write_bytes(audio)
            subprocess.run(
                [
                    self.ffmpeg or "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wave),
                ],
                check=True,
                capture_output=True,
                timeout=45,
            )
            subprocess.run(
                [
                    self.binary or "whisper-cli",
                    "-m",
                    self.model or "",
                    "-f",
                    str(wave),
                    "-l",
                    self.language,
                    "-oj",
                    "-of",
                    str(output),
                    "-np",
                    "-nt",
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            return self._read_text(payload)
