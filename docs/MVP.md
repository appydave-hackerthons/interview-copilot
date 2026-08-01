# Interview Copilot MVP contract

## Product promise

Help a human conduct a better interview without interrupting the conversation.
The app listens, structures what it learns, and quietly places useful next moves
beside the interviewer.

The memorable moment is not a chatbot response. It is watching the interview
turn into a living evidence base in real time.

## Primary flow

1. Choose one of four Nimman track templates or edit a custom topic and objective.
2. Review the objective, six conversation phases, behavior-based questions, and
   success signals before anyone speaks.
3. Use the path as a safety rail, then follow the participant's words rather than
   administering it as a survey.
4. Add transcript by microphone or typing.
5. Extract facts, pains, quotes, workflows, tools, questions, and insights.
6. Let specialist lenses read the shared evidence pool and offer suggestions
   below the conversation path.
7. When a claim earns a search, show zero to two sourced research cards whose
   **Ask next** question changes the interview's next useful move.
8. Open a source in a new tab, or pin/promote the card into web evidence without
   interrupting recording.
9. Pin, promote, dismiss, filter, and expand items without leaving the interview.
10. End with an evidence-backed report and a least-effort next step.

## Nimman template library

The built-in library contains:

- **Digital Nomads & Chiang Mai** — meaningful connections between locals and
  remote workers;
- **Chiang Mai Lifestyle** — access to slow-living, wellness, culture, and
  community;
- **Smart & Livable City** — a recurring urban decision affected by missing,
  late, fragmented, or untrusted information;
- **Open Problem Discovery** — a neutral route into any locally relevant
  problem.

Every preset owns its objective, six phases, starter path, success criteria, and
interviewer guidance. Questions favor recent behavior (especially “Tell me about
the last time…”) over opinions or solution hypotheticals. Topic or objective
edits deliberately detach the preset and build a generic path in the browser,
without an LLM or internet connection.

Built-in selection is stored by stable template ID. Restore always combines the
ID with current library defaults; the stale embedded template is ignored. A
legacy saved template is mapped to a current preset when possible, otherwise it
is migrated as a custom template with missing lists filled from safe defaults.

## Specialist lenses

- **Clarification** finds missing frequency, cost, recency, and concrete examples.
- **Opportunity** notices repeated work, paid workarounds, urgency, and unmet need.
- **Bias guard** catches leading questions and premature solutioning.
- **Memory** connects or challenges statements already in the evidence pool.
- **Research** verifies claims, seeks counterexamples and existing initiatives,
  finds local constraints or excluded stakeholders, and connects feasible
  partners/datasets/pilots to a neutral next question. It must not lecture,
  pitch, generate unsourced market size, or surface facts that do not change the
  interviewer's next move.

For the MVP these lenses share one bounded model call per analysis cycle. The
result still has explicit agent attribution, while avoiding the latency and cost
of five independent calls. The contract can later fan out without changing the
frontend or evidence model.

## Evidence rules

- Transcript is the source of truth.
- Agent suggestions are not facts until pinned, and remain labelled as agent
  material after pinning.
- External claims require a direct retrieved URL and an exact supporting source
  excerpt. A missing, weak, invented, or duplicate source produces no card.
- Research cards contain signal, ask-next question, exact trigger, Real/New/Good/
  Feasible lens, source title/URL/date, confidence, and related evidence IDs.
- Pinned research remains `source="web"` and retains URL, title, date, trigger,
  judge lens, and originating transcript/evidence links as provenance.
- Promoted evidence is included first in the next model context.
- Dismissed suggestions disappear from the working interface.
- Confidence communicates extraction certainty, not objective truth.

## Runtime

```text
Browser microphone / typed line
            |
            v
      FastAPI local app
       /      |        |         \
      v       v        v          v
whisper.cpp  research gate   OpenCode sidecar
local ggml   + Exa MCP       OpenAI OAuth + GPT-5.6 Sol
       |        |       durable local archive
      \         |            /
       v            v
       transcript + evidence packet
                    |
                    v
 Transcript | Interview guide + live guidance | Evidence
```

The OpenCode process inherits the existing user home so its OpenAI OAuth login
is reused. No OAuth token is copied into this repository or exposed to the
browser.

Research is an independent asynchronous lane. The browser uses a debounce and
abort controller; the server uses a cooldown, per-interview cache, normalized
query/URL deduplication, semantic card deduplication, and monotonically increasing
revisions. A stale result is discarded. Microphone capture, Whisper requests,
transcript rendering, and ordinary evidence extraction do not await research.

The deterministic trigger gate searches only universal/absence claims, named
organizations/services/venues/tools/policies/initiatives, current or
location-dependent claims, proposed solutions that may exist, missing local
constraints, partner/dataset/API/venue/pilot feasibility, and stakeholder gaps.
Definitions, generic background, mundane chunks, and vague statements that need
a concrete example do not search.

Live retrieval uses OpenCode's supported keyless Exa MCP backend. This avoids
introducing an API key, while exposing triggered queries to Exa and retrieved
public source text to the OpenAI OAuth model. The model cannot browse in this
lane; it receives only retrieved documents. URL membership and exact excerpts
are validated server-side. Provider/network/model failure returns an empty card
list. `INTERVIEW_RESEARCH_ENABLED=0` makes the lane fully offline.

Each microphone segment is written to `data/interviews/<session>/audio/` before
Whisper runs. Successful and failed results are appended immediately to a JSONL
ledger and a readable Markdown transcript in that session directory.

Before the first segment, the app creates the session and writes the complete
validated configuration to `configuration.yaml`. `session.json` records schema
version, mode, effective OpenAI model, and configured/active Whisper settings.
Raw-audio persistence is optional; transcript records remain durable when it is
disabled.

## Advanced configuration contract

`config/presets/digital-nomad-discovery.yaml` is the canonical source for
schema-version-1 defaults. `GET /api/config/default` returns it and
`POST /api/config/validate` applies strict Pydantic validation, including nested
unknown-key rejection and cross-field audio constraints.

The setup screen keeps the normal Start action visible and opens configuration
in a wide dialog (full-screen on mobile). Form and YAML are two views of one
object. Users can edit interview design lists, live/report prompts, specialist
lenses, model context and output limits, report sections, capture timing,
speaker, raw-audio policy, models, archive directory, demo script, and compatible
developer profiles. YAML import/export, reset, validation status, dirty count,
Escape/focus behavior, and responsive layout are part of the contract.

At Start, the browser validates and deep-copies the current configuration, then
registers the archive before requesting microphone access. That frozen object
drives every analysis and report request plus audio rotation. Disabled lenses
and report sections are enforced again after model parsing, and deterministic
fallback honors the same switches and limits.

## Explicit MVP boundaries

- No cross-interview database yet; each interview has a durable filesystem
  archive, while browser local storage keeps the active UI state and selected
  template ID.
- Live research depends on the configured external search endpoint; it is a
  best-effort enhancement and never a dependency of the interview loop.
- Microphone chunks default to the selected speaker; diarisation is out of scope.
- Demo mode uses deterministic sample analysis plus a deterministic sourced
  research card and is visibly labelled.
- If the sidecar fails, local extraction keeps the flow usable and the UI shows
  that it is in local mode.
