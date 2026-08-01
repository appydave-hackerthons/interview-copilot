# Advanced interview configuration — implementation handoff

**Status:** ready for implementation  
**Scope:** setup screen, request contracts, runtime prompts, configuration persistence  
**Primary goal:** make the interview behavior inspectable and configurable without making the default setup experience feel like a developer console.

## Context

The setup screen currently provides a strong simple path:

1. Enter a topic.
2. Edit the objective.
3. Review the conversation arc.
4. Start the interview.

However, only `name` and `objective` are editable. The phases are displayed but
read-only, success criteria are hidden, and most consequential behavior is
hardcoded across the frontend and backend.

Current hidden or hardcoded behavior includes:

- the live analysis system prompt;
- the report synthesis prompt;
- enabled specialist lenses;
- transcript and evidence context limits;
- suggestion and evidence output limits;
- the response JSON contracts;
- audio segment and overlap timing;
- default speaker;
- OpenAI model selection;
- Whisper language and model path;
- guided-demo transcript;
- deterministic fallback heuristics.

The app is also gaining durable interview storage. Do not overwrite or revert
the existing archive work in `App.tsx`, `api.ts`, `SetupScreen.tsx`, `app.py`,
`tests/test_app.py`, or `interview_copilot/archive.py`. Advanced configuration
must integrate with that work so each interview archive records the exact
configuration used.

## Product decision

Keep the default setup card concise. Add one **Advanced configuration** control
that opens a wide editor with progressive disclosure.

Do not expand every field inline inside the existing card. At desktop width the
card is approximately 490px wide and already about 600px tall. Adding prompts
and YAML inline would push the primary action below the fold and flatten the
visual hierarchy.

### Setup screen

```text
┌──────────────────────────────────────────────────────────────┐
│ Prepare the room                                             │
│                                                              │
│ Topic                                                        │
│ [ Digital nomad frictions                                  ] │
│                                                              │
│ Objective                                                    │
│ [ Discover recurring pains…                                ] │
│                                                              │
│ Conversation arc                                             │
│ 01 Rapport       02 Workflow       03 Frustrations           │
│                                                              │
│ [⚙ Advanced configuration]  Default preset · Valid           │
│                                                              │
│ [ Start interview ] [ Run guided demo ]                      │
└──────────────────────────────────────────────────────────────┘
```

### Advanced editor

Use a centered wide dialog on desktop (`min(920px, calc(100vw - 48px))`) and a
full-screen sheet on mobile. The editor should have a sticky header and footer.

```text
┌────────────────────────────────────────────────────────────────────┐
│ Advanced configuration               Default preset · 3 changes   │
│ [Form] [YAML]               [Import] [Export] [Reset]              │
├────────────────────────────────────────────────────────────────────┤
│ ▼ Interview design                                                │
│   Name, objective, phases, success criteria, interviewer guidance │
│                                                                    │
│ ▼ Live copilot                                                    │
│   Analysis prompt, specialist lenses, limits and context          │
│                                                                    │
│ ▶ End report                                                      │
│ ▶ Audio and runtime                                               │
│ ▶ Developer overrides                                             │
├────────────────────────────────────────────────────────────────────┤
│ ✓ Valid configuration                       [Cancel] [Apply]       │
└────────────────────────────────────────────────────────────────────┘
```

The Form/YAML control is a mode switch over the same configuration object, not
two independent sources of truth.

## Configuration contract

Create one versioned object shared by TypeScript, Pydantic, YAML import/export,
analysis requests, report requests, and the interview archive.

Suggested shape:

```yaml
schema_version: 1

template:
  name: Digital nomad frictions
  objective: >-
    Discover recurring pains, workarounds, and unmet needs in day-to-day
    nomad life.
  phases:
    - Rapport
    - Current workflow
    - Frustrations
    - Workarounds
    - Cost and frequency
    - Ideal future
  success_metrics:
    - Learned the current process
    - Found the biggest pain
    - Quantified frequency
    - Estimated cost
  interviewer_guidance:
    - Prefer recent concrete examples over hypothetical preferences.
    - Separate observed behavior from proposed solutions.

copilot:
  system_prompt: |-
    You are a silent expert research partner beside a human interviewer.
    Improve the interview in real time using only grounded evidence.
  task_prompt: |-
    Analyse the supplied interview state. Extract atomic evidence and offer
    the smallest useful next interventions.
  lenses:
    clarification: true
    opportunity: true
    bias_guard: true
    memory: true
    research: true
  limits:
    transcript_turns: 18
    evidence_context_items: 30
    new_evidence_items: 4
    suggestions: 4
  promoted_evidence_first: true

report:
  system_prompt: |-
    You are an evidence-first customer discovery analyst.
  task_prompt: |-
    Turn the completed interview into a concise, decision-ready report.
    Separate observation from inference and do not invent validation.
  sections:
    summary: true
    top_pains: true
    key_facts: true
    quotes: true
    unanswered_questions: true
    opportunity: true
    next_step: true
    coverage: true
  score_against_success_metrics: true

audio:
  segment_ms: 7000
  overlap_ms: 200
  default_speaker: Participant
  persist_raw_audio: true
  whisper_language: auto
  whisper_model: ~/.cache/whisper/ggml-base.en.bin

runtime:
  model: openai/gpt-5.6-sol
  archive_root: data/interviews

developer:
  analysis_output_contract: default
  report_output_contract: default
  demo_script: default
  fallback_profile: default
```

### TypeScript types

Add an `InterviewConfiguration` interface rather than continuing to grow
`InterviewTemplate`:

```ts
interface InterviewConfiguration {
  schema_version: 1;
  template: {
    name: string;
    objective: string;
    phases: string[];
    success_metrics: string[];
    interviewer_guidance: string[];
  };
  copilot: CopilotConfiguration;
  report: ReportConfiguration;
  audio: AudioConfiguration;
  runtime: RuntimeConfiguration;
  developer: DeveloperConfiguration;
}
```

Mirror the contract with Pydantic models. Keep validation constraints in the
backend authoritative even when the frontend has matching validation.

## Configuration sections

### 1. Interview design

Expose:

- name;
- objective;
- reorderable phases;
- success metrics;
- interviewer guidance;
- add, delete, and reorder controls for every list.

Do not require drag-and-drop for the MVP. Up/down buttons are accessible,
mobile-friendly, and sufficient.

### 2. Live copilot

Expose:

- complete system prompt;
- task-specific prompt;
- on/off switch for each specialist lens;
- maximum transcript turns sent to the model;
- maximum evidence items sent to the model;
- maximum new evidence items;
- maximum suggestions;
- promoted-evidence priority behavior.

Show a short description beside each lens. Preserve the stable backend names
`Clarification`, `Opportunity`, `Bias guard`, `Memory`, and `Research` in model
output even if the UI label is friendlier.

### 3. End report

Expose:

- system prompt;
- synthesis task prompt;
- report section toggles;
- scoring against success criteria;
- least-effort-next-step instruction.

The response parser still requires a stable internal contract. A disabled
section should accept an empty array/string rather than altering the normal
Pydantic response shape.

### 4. Audio and runtime

Expose:

- segment duration;
- overlap duration;
- default speaker;
- raw-audio persistence;
- Whisper language;
- Whisper model path;
- OpenAI model;
- archive directory.

Mark settings according to application behavior:

- **Applies next interview:** segment timing, speaker, prompts, lenses and
  request limits.
- **Requires local service restart:** Whisper model path, sidecar port or binary
  location if those are exposed later.

Do not allow `overlap_ms >= segment_ms`.

### 5. Developer overrides

Keep this section collapsed by default and label it as capable of breaking
model parsing.

Expose:

- analysis output contract;
- report output contract;
- guided-demo script;
- local-fallback profile.

For the first implementation, output contracts may use the value `default`
only. If arbitrary schemas are later supported, validate their compatibility
with `AnalysisPacket` and `InterviewReport` before allowing Apply.

## Presets and YAML

Add a canonical preset directory:

```text
config/
  presets/
    digital-nomad-discovery.yaml
```

The default preset must become the single source of truth. Remove duplicated
defaults from `frontend/src/demo.ts`, `frontend/src/types.ts`, and
`interview_copilot/models.py` once the API can load the preset.

Recommended API:

```text
GET  /api/config/default
POST /api/config/validate
```

The frontend may parse YAML for immediate feedback, but the backend validation
endpoint is authoritative. Use the `yaml` npm package rather than implementing
a parser.

Required YAML behavior:

- import `.yaml` and `.yml`;
- export the complete current configuration;
- preserve multiline prompts as block scalars where practical;
- reject unknown top-level keys unless explicitly supported;
- display line-aware parser errors;
- do not Apply an invalid configuration;
- Reset restores the selected preset, not an invisible hardcoded object.

## Data flow

```text
Canonical YAML preset
        |
        v
GET /api/config/default
        |
        v
Setup form <----> YAML editor
        |
        +---- POST /api/config/validate
        |
        v
Frozen InterviewConfiguration
        |
        +---- analysis request
        +---- report request
        +---- audio capture settings
        +---- interview archive/configuration.yaml
```

Freeze a deep copy when **Start interview** is pressed. Editing a preset in
another tab must not alter an active interview.

## Archive integration

Every new interview directory should contain:

```text
data/interviews/<session-id>/
  session.json
  configuration.yaml
  transcript.jsonl
  transcript.md
  audio/
```

Write `configuration.yaml` when the session starts, before the first audio
segment is recorded. Include at least the configuration schema version and the
effective model and Whisper settings in `session.json`.

This is necessary for reproducibility: a future reader must be able to tell
which prompts, limits, lenses and success criteria produced the evidence and
report.

## Files to add

```text
config/presets/digital-nomad-discovery.yaml
frontend/src/components/AdvancedConfigurationDialog.tsx
frontend/src/components/ConfigurationListEditor.tsx
frontend/src/components/YamlConfigurationEditor.tsx
frontend/src/config.ts
interview_copilot/configuration.py
tests/test_configuration.py
```

## Files to modify

| File | Change |
|---|---|
| `frontend/src/components/SetupScreen.tsx` | Add status summary and Advanced trigger. |
| `frontend/src/App.tsx` | Own draft/effective configuration and freeze it at interview start. Preserve current archive session IDs. |
| `frontend/src/types.ts` | Add full configuration types. |
| `frontend/src/api.ts` | Load and validate configuration; include it in analysis/report requests. |
| `frontend/src/styles.css` | Add dialog, accordion, YAML editor, responsive and validation styles. |
| `frontend/src/demo.ts` | Keep transcript lines only; remove duplicated template defaults. |
| `interview_copilot/models.py` | Add Pydantic configuration models and request fields. |
| `interview_copilot/opencode_runtime.py` | Replace hardcoded system/task prompts and limits with validated configuration. |
| `interview_copilot/app.py` | Add configuration endpoints and save the frozen session configuration. |
| `interview_copilot/archive.py` | Persist `configuration.yaml` beside transcript and audio. |
| `interview_copilot/fallback.py` | Respect enabled lenses, success criteria and fallback profile where applicable. |
| `tests/test_app.py` | Cover API integration without weakening current archive tests. |
| `README.md` and `docs/MVP.md` | Document presets, YAML and per-session configuration snapshots. |

## Implementation order

### Phase 1 — contract and validation

1. Add the canonical YAML preset.
2. Add Pydantic configuration models.
3. Add default/validate endpoints.
4. Add backend tests for defaults, validation and unknown keys.

### Phase 2 — frontend editor

1. Load the canonical default into `App`.
2. Add the Advanced trigger and dialog shell.
3. Implement the structured form sections.
4. Add Form/YAML synchronization.
5. Add import, export, reset, dirty state and validation status.
6. Test desktop and mobile layouts.

### Phase 3 — runtime wiring

1. Add configuration to analysis and report requests.
2. Replace hardcoded prompts and limits in `OpenCodeRuntime`.
3. Wire segment duration and overlap into microphone rotation.
4. Respect report section and lens switches.
5. Confirm local fallback remains usable with missing OpenAI runtime.

### Phase 4 — archive snapshot

1. Freeze the effective configuration at Start interview.
2. Save it before recording begins.
3. Ensure audio, transcript and configuration share one session ID.
4. Add a test proving later draft edits do not mutate an archived session.

## Validation rules

- `schema_version` must equal a supported integer version.
- Name and objective must be non-empty.
- At least one phase and one success metric are required.
- Every list item must be non-empty after trimming.
- At least one specialist lens must remain enabled.
- `transcript_turns`: 1–100.
- `evidence_context_items`: 1–200.
- `new_evidence_items`: 0–20.
- `suggestions`: 0–20.
- `segment_ms`: 2,000–60,000.
- `overlap_ms`: 0–2,000 and less than `segment_ms`.
- Model must use `provider/model` format.
- Archive root must resolve inside an approved local directory.
- Prompts should have generous but finite length limits.
- Unknown configuration keys should fail validation rather than silently doing
  nothing.

## UX behavior

- Advanced configuration requires one click from setup.
- The primary Start interview action remains visible on the default setup view.
- Opening Advanced does not modify the effective configuration.
- Apply is disabled while YAML or form validation fails.
- Cancel discards changes made since the dialog opened.
- Reset asks for confirmation only when there are unsaved changes.
- Dirty state is persistent and visible: `3 values changed from default`.
- Restart-required values display a badge before Apply.
- Keyboard: `Escape` cancels, focus remains trapped inside the dialog, and focus
  returns to the Advanced trigger on close.
- Mobile: use a full-screen editor; do not squeeze prompt fields into the setup
  card.

## Testing requirements

### Backend

- canonical preset validates;
- invalid YAML is rejected with useful detail;
- unknown keys are rejected;
- invalid numerical relationships are rejected;
- request-scoped prompts reach the runtime;
- lens and limit settings alter the generated prompt/context;
- archive stores the frozen configuration;
- defaults do not regress existing analysis, report or transcription tests.

### Frontend

There is no frontend test runner yet. Add Vitest and Testing Library if component
tests are introduced. At minimum cover:

- opening and closing Advanced;
- Cancel versus Apply;
- add/delete/reorder list items;
- Form/YAML round trip;
- invalid YAML and disabled Apply;
- import, export and reset;
- dirty-count status;
- current configuration included in requests;
- active interview uses a frozen copy.

### Browser verification

- desktop setup remains scannable at 1280px and 1440px;
- Advanced dialog fits without horizontal overflow;
- prompt areas are usable at 768px;
- mobile editor works at 390px;
- keyboard focus order and Escape behavior work;
- Start interview still requests microphone access once;
- configuration changes affect live suggestions and the final report;
- archived `configuration.yaml` matches the applied UI state.

## Acceptance criteria

- A non-technical user can start with the default preset without opening
  Advanced.
- A power user can inspect and edit every meaningful prompt and interview rule.
- Phases and success criteria are editable.
- Configuration can be imported from and exported to YAML.
- The same object drives the UI, analysis, report and audio behavior.
- Invalid settings cannot start an interview.
- Each interview saves the exact effective configuration beside its transcript
  and audio.
- Reset reliably returns to the canonical preset.
- Existing guided demo, local fallback, OAuth model path and durable transcript
  storage continue to work.

## Non-goals for the first pass

- A cloud preset marketplace.
- Collaborative editing.
- Database-backed preset sharing.
- Arbitrary user-defined response shapes that bypass Pydantic validation.
- Drag-and-drop list editing.
- Hot-swapping the Whisper binary during an active interview.

## Main implementation risk

The largest risk is creating configuration controls that appear to work but are
not wired to runtime behavior. Every visible field must have one of these clear
states:

1. applies to the next interview;
2. requires restart;
3. read-only diagnostic information.

Do not ship silent no-op settings.
