# interview-copilot

A dashboard where a team of AI agents co-pilot a live interview — surfacing questions the
interviewer should ask and biases they should avoid, so the interviewee opens up.

Built at the **Hacker Fund hackathon**, Chiang Mai 4 Seasons, August 2026.

---

## The problem

People don't know what they want.

A good interviewer can pull a real need out of someone, or get them to notice a problem they'd
never named. That's a skill, and not everyone has it. When the interviewer is average, the
evidence is thin — and everything downstream inherits that thinness.

## What it does

The interviewer talks. The agents listen as a team and put things on a dashboard, live:

- **Questions to ask next** — the follow-up that opens a door the interviewer didn't see
- **Biases to avoid** — leading the witness, accepting the first answer, taking a proposed
  solution as if it were the underlying problem
- **Supporting information** — relevant data surfaced while the topic is still on the table

The interviewer stays in charge. The agents never speak to the interviewee.

## Why a team of agents, not one

Different agents watch for different things — one hunts for the unasked question, another
watches for bias, another goes and finds facts. They're independent on purpose: one model
trying to do all three at once does the easiest one and quietly drops the rest.

## Status

Nothing built yet. This repo exists so work can start.

## Owner

**Ethon** — build lead.

Part of the Chiang Mai 4 Seasons hackathon. The wider system this feeds — interviews become
fact sheets become opportunities become working micro-apps — lives in
`appydave-hackerthons/08-2026-chiangmai-4seas`.
