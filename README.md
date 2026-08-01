# Interview Copilot

A local-first research partner that helps a human conduct better interviews.
While the conversation is happening, Interview Copilot turns the transcript into
a shared evidence pool and quietly surfaces the next useful question, risk, or
pattern.

Built at the **Hacker Fund hackathon, Chiang Mai, August 2026**.

## The problem

Customer interviews are deceptively difficult. An interviewer has to listen,
notice missing detail, avoid leading the participant, remember earlier claims,
and decide what to ask next—all at the same time. When that work is weak, teams
leave with thin notes and mistake opinions or proposed solutions for evidence.

Interview Copilot reduces that cognitive load without joining the conversation.
The human remains in charge; the software listens, structures, and suggests.

## MVP scope

The current prototype includes:

- a light, beige, text-centred three-column interview workspace
- an always-on microphone from **Start interview** to **End interview**
- local transcription through `whisper.cpp`, plus typed transcript input
- live evidence extraction for facts, pains, quotes, workflows, tools, questions,
  and insights
- specialist clarification, opportunity, bias, memory, and research lenses
- pin, promote, dismiss, filter, confidence, and provenance controls
- an end-of-interview report with Markdown copy/export
- a deterministic guided demo and graceful local fallback
- responsive desktop and mobile layouts

Deliberate MVP boundaries:

- sessions live in browser storage; there is no cross-interview database yet
- the research lens proposes what to validate but does not browse the web
- microphone segments use the selected speaker; diarisation is out of scope
- the lenses share one bounded model call per analysis cycle to control latency
  and cost

## Method

The central design idea is a **shared evidence pool**. Agents do not pass private
messages to one another or independently reinterpret the full conversation.
They read and write the same structured objects.

```text
Microphone / typed line
          |
          v
   Local transcript
          |
          v
 Shared evidence pool
    /    |    |    \
   v     v    v     v
Question  Opportunity  Bias  Research
          |
          v
 Human pins and promotes what matters
          |
          v
 Evidence-backed interview report
```

This keeps the system extensible and makes its reasoning visible in the UI.
Transcript statements remain the source of truth. Suggestions are labelled as
agent material, confidence describes extraction certainty rather than objective
truth, and external claims require a real source.

## Architecture

- **Frontend:** React 19, TypeScript, Vite
- **Local API:** FastAPI and Pydantic
- **Speech-to-text:** `ffmpeg` + local `whisper.cpp`
- **Model runtime:** OpenCode sidecar using the user's existing OpenAI OAuth
  session; the default model is `openai/gpt-5.6-sol`
- **Fallback:** deterministic local extraction and reporting if the model runtime
  is unavailable

Audio is segmented in the browser and transcribed on the local machine. OAuth
credentials are inherited by the local OpenCode process; no token is copied into
this repository or exposed to the browser.

More detail is available in [the MVP contract](docs/MVP.md).

## Run locally

Prerequisites:

- Node.js 20+
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- `ffmpeg`
- [`whisper.cpp`](https://github.com/ggml-org/whisper.cpp) with `whisper-cli`
  and a local GGML model
- [OpenCode](https://opencode.ai/) signed in with OpenAI OAuth for live analysis

Install dependencies and start the development servers:

```bash
make install
make dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend proxies API
requests to the FastAPI server on port `8787`.

For a production-style local build:

```bash
make build
make start
```

Then open [http://localhost:8787](http://localhost:8787).

If Whisper or OpenCode is unavailable, the app remains usable with typed input,
local extraction, and the guided demo.

## Configuration

| Variable | Default | Purpose |
|-|-|-|
| `INTERVIEW_MODEL` | `openai/gpt-5.6-sol` | OpenCode provider/model |
| `OPENCODE_BIN` | auto-discovered | OpenCode executable |
| `OPENCODE_PORT` | `4097` | Local sidecar port |
| `OPENCODE_URL` | unset | Reuse an already-running sidecar |
| `WHISPER_BIN` | auto-discovered | `whisper-cli` executable |
| `WHISPER_MODEL` | auto-discovered | Path to a local GGML model |
| `WHISPER_LANGUAGE` | `auto` | Whisper language |

Model discovery checks `~/.cache/whisper/ggml-small.en.bin`, then
`~/.cache/whisper/ggml-base.en.bin`, then Homebrew's tiny test model. Set
`WHISPER_MODEL` explicitly to use another model.

## Development

```bash
make test          # backend unit and API tests
make build         # frontend typecheck and production build
make check         # tests + frontend build
```

The current suite contains 10 backend/API tests. Generated files, local models,
OAuth state, logs, virtual environments, and frontend dependencies are excluded
from Git.
