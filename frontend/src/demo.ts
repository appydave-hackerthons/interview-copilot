import type { InterviewTemplate, Speaker } from "./types";

export const DEFAULT_TEMPLATE: InterviewTemplate = {
  name: "Digital nomad frictions",
  objective: "Discover recurring pains, workarounds, and unmet needs in day-to-day nomad life.",
  phases: [
    "Rapport",
    "Current workflow",
    "Frustrations",
    "Workarounds",
    "Cost & frequency",
    "Ideal future",
  ],
  success_metrics: [
    "Learned the current process",
    "Found the biggest pain",
    "Quantified frequency",
    "Estimated cost",
  ],
};

export const DEMO_LINES: Array<{ speaker: Speaker; text: string }> = [
  {
    speaker: "Interviewer",
    text: "Tell me about the last administrative task that disrupted your life as a nomad.",
  },
  {
    speaker: "Participant",
    text: "The visa run is the worst part. I have to leave Thailand every 60 days.",
  },
  {
    speaker: "Interviewer",
    text: "Walk me through what happened the last time.",
  },
  {
    speaker: "Participant",
    text: "I lost six hours, paid an agent 1500 baht, and still worried I had the wrong paperwork.",
  },
  {
    speaker: "Participant",
    text: "I track the date in Google Calendar and message the agent on WhatsApp, but it is still stressful.",
  },
];
