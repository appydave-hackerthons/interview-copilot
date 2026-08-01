import json
import subprocess
from pathlib import Path

from interview_copilot.transcription import WhisperTranscriber


def test_wav_upload_is_converted_to_a_distinct_work_file(monkeypatch) -> None:
    transcriber = WhisperTranscriber()
    transcriber.binary = "whisper-cli"
    transcriber.ffmpeg = "ffmpeg"
    transcriber.model = "/tmp/model.bin"
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs):
        calls.append(args)
        if args[0] == "whisper-cli":
            output = Path(args[args.index("-of") + 1]).with_suffix(".json")
            output.write_text(json.dumps({"transcription": [{"text": "Hello world"}]}))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert transcriber.transcribe(b"audio", ".wav") == "Hello world"
    ffmpeg_call = calls[0]
    assert ffmpeg_call[ffmpeg_call.index("-i") + 1] != ffmpeg_call[-1]
