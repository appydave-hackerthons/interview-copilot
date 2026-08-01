# Interview Copilot MVP contract

## Product promise

Help a human conduct a better interview without interrupting the conversation.
The app listens, structures what it learns, and quietly places useful next moves
beside the interviewer.

The memorable moment is not a chatbot response. It is watching the interview
turn into a living evidence base in real time.

## Primary flow

1. Choose or edit a reusable interview template.
2. Start an interview and add transcript by microphone or typing.
3. Extract facts, pains, quotes, workflows, tools, questions, and insights.
4. Let specialist lenses read the shared evidence pool and offer suggestions.
5. Pin, promote, dismiss, filter, and expand items without leaving the interview.
6. End with an evidence-backed report and a least-effort next step.

## Specialist lenses

- **Clarification** finds missing frequency, cost, recency, and concrete examples.
- **Opportunity** notices repeated work, paid workarounds, urgency, and unmet need.
- **Bias guard** catches leading questions and premature solutioning.
- **Memory** connects or challenges statements already in the evidence pool.
- **Research** proposes what needs external validation; it must not invent sources.

For the MVP these lenses share one bounded model call per analysis cycle. The
result still has explicit agent attribution, while avoiding the latency and cost
of five independent calls. The contract can later fan out without changing the
frontend or evidence model.

## Evidence rules

- Transcript is the source of truth.
- Agent suggestions are not facts until pinned, and remain labelled as agent
  material after pinning.
- External claims require a real URL; absent web retrieval, the research lens
  should propose a search rather than fabricate a result.
- Promoted evidence is included first in the next model context.
- Dismissed suggestions disappear from the working interface.
- Confidence communicates extraction certainty, not objective truth.

## Runtime

```text
Browser microphone / typed line
            |
            v
      FastAPI local app
       /            \
      v              v
whisper.cpp      OpenCode sidecar
local ggml       OpenAI OAuth + GPT-5.6 Sol
      \              /
       v            v
       transcript + evidence packet
                    |
                    v
  Transcript | Agent activity | Evidence
```

The OpenCode process inherits the existing user home so its OpenAI OAuth login
is reused. No OAuth token is copied into this repository or exposed to the
browser.

## Explicit MVP boundaries

- No cross-interview database yet; the active interview persists in browser
  local storage.
- No live external search yet; research suggestions identify what to verify.
- Microphone chunks default to the selected speaker; diarisation is out of scope.
- Demo mode uses deterministic sample analysis and is visibly labelled.
- If the sidecar fails, local extraction keeps the flow usable and the UI shows
  that it is in local mode.
