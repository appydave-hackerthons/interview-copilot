import type { InterviewTemplate } from "./types";

export const GUIDANCE_CARD_LIFETIME_MS = 60_000;

interface TimedGuidanceCard {
  id: string;
  createdAt?: number;
  pinned?: boolean;
}

export function mergeGuidanceCards<T extends TimedGuidanceCard>(
  previous: T[],
  incoming: T[],
  now = Date.now(),
) {
  const merged = new Map(previous.map((card) => [card.id, card]));
  incoming.forEach((card) => {
    const existing = merged.get(card.id);
    merged.set(card.id, {
      ...card,
      createdAt: existing?.createdAt ?? card.createdAt ?? now,
      pinned: existing?.pinned ?? card.pinned ?? false,
    });
  });
  return [...merged.values()];
}

export function keepActiveGuidanceCards<T extends TimedGuidanceCard>(
  cards: T[],
  now = Date.now(),
  lifetimeMs = GUIDANCE_CARD_LIFETIME_MS,
) {
  return cards.filter((card) => (
    card.pinned
    || card.createdAt === undefined
    || now - card.createdAt < lifetimeMs
  ));
}

export interface InterviewBreadcrumb {
  stage: string;
  question: string;
  coach: string;
}

export const DEPTH_LADDER = [
  "Desired outcome",
  "Underlying why",
  "Current reality",
  "Expectation gap",
  "Friction",
  "Consequence",
] as const;

const COACHING = [
  "Anchor this in one recent event, then ask what they were trying to achieve.",
  "Stay on their answer. Ask why it matters, using their words, until the real meaning appears.",
  "Check how it is going now: are they getting enough of it, reliably and quickly enough?",
  "Contrast what they expected or imagined with what actually happened.",
  "Locate the break: where did it get stuck, slow down, feel difficult, or go nowhere?",
  "Get the consequence and priority. Ask what they did next and why this gap matters now.",
];

export function buildBreadcrumbs(
  template: InterviewTemplate,
  starterQuestions?: readonly string[],
): InterviewBreadcrumb[] {
  const topic = template.name.trim() || "this topic";
  const subject = topic.replace(/\b(frictions?|problems?|interviews?|discovery)\b/gi, "").trim() || topic;
  const generated = [
    `Tell me about the last time ${subject.toLowerCase()} mattered to you. What were you trying to achieve?`,
    "Why did that outcome matter to you? What would it have made possible?",
    "How well are you getting that outcome today—is it enough, reliable enough, and fast enough?",
    "What did you expect would happen, and what actually happened?",
    "Where did it get stuck, slow down, become difficult, or go nowhere?",
    "What did you do next, and what did the gap cost you in time, money, energy, or opportunity?",
  ];
  const questions = starterQuestions?.filter((question) => question.trim()) ?? generated;
  return questions.slice(0, 6).map((question, index) => ({
    stage: template.phases[index] ?? `Step ${index + 1}`,
    question,
    coach: COACHING[index] ?? "Ask, then leave room for the answer.",
  }));
}
