import type {
  InterviewTemplate,
  InterviewTemplatePreset,
} from "./types";

const DEPTH_PHASES = [
  "Recent context & desired outcome",
  "Underlying why",
  "Current reality",
  "Expectation gap",
  "Friction & attempts",
  "Consequence & priority",
];

const DEPTH_GUIDANCE = [
  "When a useful point appears, stay with it instead of jumping to the next topic.",
  "First establish what the participant was trying to achieve or wanted to make possible.",
  "Use progressive why probes—up to five only while each answer reveals new meaning. Vary the wording and never interrogate mechanically.",
  "Ask how well the desired outcome is being achieved now: enough, reliably enough, and fast enough.",
  "Make the gap explicit by comparing what they expected or imagined with what actually happened.",
  "Locate where progress gets stuck, slows down, feels difficult, or goes nowhere, then ask about attempts and workarounds.",
  "Ground every important gap in a recent concrete example and its consequence in time, money, energy, emotion, or missed opportunity.",
  "Ask one neutral question at a time, reuse the participant's words, and move on only when the thread is clear or they do not want to continue.",
];

export const TEMPLATE_LIBRARY: InterviewTemplatePreset[] = [
  {
    id: "digital-nomads-chiang-mai",
    track: "Track 01 · Community & belonging",
    short_objective: "Understand when local–remote worker connections become meaningful.",
    template: {
      name: "Digital Nomads & Chiang Mai",
      objective: "Discover why meaningful connections between locals and remote workers do or do not form.",
      phases: [...DEPTH_PHASES],
      success_metrics: [
        "Captured one recent connection attempt and the outcome the participant wanted",
        "Uncovered why that outcome matters personally or practically",
        "Assessed how much of the desired connection they achieve now",
        "Made the expected-versus-actual gap explicit",
        "Identified where connection attempts stall and what the participant tries next",
        "Captured the consequence and priority of the gap",
      ],
      interviewer_guidance: [
        ...DEPTH_GUIDANCE,
        "Use the participant's own definition of a meaningful relationship.",
        "Do not assume locals and remote workers want the same type of connection.",
      ],
    },
    starter_questions: [
      "Tell me about the last time you tried to meet someone outside your usual circle. What were you hoping would come from it?",
      "Why did that kind of connection matter to you? What would it have made possible?",
      "How much of that connection are you getting now—is it enough and happening often enough?",
      "What did you imagine would happen when you went, and what actually happened?",
      "Where did the connection stall or stay superficial? What did you try next?",
      "What does staying in that bubble cost you, and which part of the gap matters most now?",
    ],
  },
  {
    id: "chiang-mai-lifestyle",
    track: "Track 02 · Lifestyle & access",
    short_objective: "Find where Chiang Mai life is valuable, difficult to access, or exclusionary.",
    template: {
      name: "Chiang Mai Lifestyle",
      objective: "Discover how Chiang Mai’s slow-living, wellness, cultural, and community advantages could become more accessible or valuable.",
      phases: [...DEPTH_PHASES],
      success_metrics: [
        "Captured one recent participation decision and desired outcome",
        "Uncovered why the experience mattered",
        "Assessed how well the participant can access that outcome now",
        "Made the expected-versus-actual participation gap explicit",
        "Identified where access breaks and the current workaround",
        "Captured the consequence, priority, and who else is excluded",
      ],
      interviewer_guidance: [
        ...DEPTH_GUIDANCE,
        "Ask what made participation feel easy or uncomfortable without assuming price was the barrier.",
        "Notice who the participant believes the experience was designed for.",
      ],
    },
    starter_questions: [
      "Tell me about the last Chiang Mai activity you considered joining. What were you hoping to get from it?",
      "Why did that experience matter to you? What would it have added to your life?",
      "How much of that experience are you getting now—is it enough and easy enough to access?",
      "What did you expect participation to be like, and what was it actually like?",
      "Where did access become slow, uncomfortable, expensive, or impossible? What did you do instead?",
      "What did missing out cost you, and which part of the gap would you fix first?",
    ],
  },
  {
    id: "smart-livable-city",
    track: "Track 03 · Urban intelligence",
    short_objective: "Find a recurring city decision that better information or coordination could improve.",
    template: {
      name: "Smart & Livable City",
      objective: "Discover a recurring urban problem where better information, coordination, data, or AI could improve a real decision.",
      phases: [...DEPTH_PHASES],
      success_metrics: [
        "Captured one recent urban incident and the intended outcome",
        "Uncovered why that outcome mattered",
        "Assessed how well the current workflow achieves it",
        "Made the expected-versus-actual result explicit",
        "Identified where information or coordination breaks and the workaround",
        "Captured recurrence, consequence, priority, and a plausible pilot stakeholder",
      ],
      interviewer_guidance: [
        ...DEPTH_GUIDANCE,
        "Start with the incident, not with technology or AI.",
        "Separate missing information from information the participant did not trust or could not act on.",
        "Ask who controls the smallest part of the workflow that could be piloted.",
      ],
    },
    starter_questions: [
      "Tell me about the last difficult city task. What were you trying to get done?",
      "Why did getting that done matter at that moment? What depended on it?",
      "How well does the current city workflow work for you—is it reliable and fast enough?",
      "What did you expect would happen, and what actually happened?",
      "Where did the workflow get stuck or slow down? What information or workaround did you try?",
      "What was the consequence, how often does it recur, and which gap matters most to fix?",
    ],
  },
  {
    id: "open-problem-discovery",
    track: "Open track · Local problem discovery",
    short_objective: "Investigate a locally relevant problem without steering toward a solution.",
    template: {
      name: "Open Problem Discovery",
      objective: "Help a team investigate any locally relevant problem without leading the participant toward a proposed solution.",
      phases: [...DEPTH_PHASES],
      success_metrics: [
        "Captured one recent incident and the outcome the participant wanted",
        "Uncovered why that outcome mattered",
        "Assessed how well the current workflow achieves it",
        "Made the expected-versus-actual gap explicit",
        "Identified the hardest point, attempts, and workarounds",
        "Captured recurrence, consequence, priority, and a testable problem boundary",
      ],
      interviewer_guidance: [
        ...DEPTH_GUIDANCE,
        "Mirror the participant's language instead of naming the problem for them.",
        "Ask what happened before asking what should exist.",
        "Treat proposed solutions as clues and return to the underlying behavior.",
      ],
    },
    starter_questions: [
      "Tell me about the last time part of your week took too much effort. What were you trying to achieve?",
      "Why did that outcome matter? What would success have made possible?",
      "How well are you achieving it now—is the result enough, reliable enough, and fast enough?",
      "What did you expect would happen, and what actually happened?",
      "Where did it get stuck, slow down, or go nowhere? What have you already tried?",
      "What did the gap cost you, how often does it happen, and why is it worth fixing now?",
    ],
  },
];

export const DEFAULT_TEMPLATE_ID = TEMPLATE_LIBRARY[0].id;

export interface MigratedTemplateSelection {
  selectedTemplateId: string | null;
  template: InterviewTemplate;
}

function normalize(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function presetByIdentity(id: unknown, name?: unknown) {
  if (typeof id === "string") {
    const match = TEMPLATE_LIBRARY.find((preset) => preset.id === id);
    if (match) return match;
  }
  if (typeof name !== "string") return undefined;
  const normalizedName = normalize(name);
  if (normalizedName === "digital nomad frictions") return TEMPLATE_LIBRARY[0];
  return TEMPLATE_LIBRARY.find((preset) => normalize(preset.template.name) === normalizedName);
}

function stringList(value: unknown, fallback: string[]) {
  if (!Array.isArray(value)) return [...fallback];
  const items = value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()));
  return items.length ? items : [...fallback];
}

function migrateCustomTemplate(value: unknown): InterviewTemplate {
  const fallback = TEMPLATE_LIBRARY[TEMPLATE_LIBRARY.length - 1].template;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return structuredClone(fallback);
  }
  const saved = value as Record<string, unknown>;
  return {
    name: typeof saved.name === "string" && saved.name.trim() ? saved.name : fallback.name,
    objective: typeof saved.objective === "string" && saved.objective.trim()
      ? saved.objective
      : fallback.objective,
    phases: stringList(saved.phases, fallback.phases),
    success_metrics: stringList(saved.success_metrics, fallback.success_metrics),
    interviewer_guidance: stringList(saved.interviewer_guidance, fallback.interviewer_guidance),
  };
}

export function migrateStoredTemplateSelection(value: unknown): MigratedTemplateSelection {
  const defaultSelection = {
    selectedTemplateId: DEFAULT_TEMPLATE_ID,
    template: structuredClone(TEMPLATE_LIBRARY[0].template),
  };
  if (!value || typeof value !== "object" || Array.isArray(value)) return defaultSelection;
  const saved = value as Record<string, unknown>;

  if (saved.schema_version === 2) {
    const selected = presetByIdentity(saved.selected_template_id);
    if (selected) {
      return { selectedTemplateId: selected.id, template: structuredClone(selected.template) };
    }
    if (saved.selected_template_id === null && saved.custom_template) {
      return { selectedTemplateId: null, template: migrateCustomTemplate(saved.custom_template) };
    }
  }

  const savedConfiguration = saved.configuration;
  const legacyTemplate = saved.template ?? (
    savedConfiguration && typeof savedConfiguration === "object" && !Array.isArray(savedConfiguration)
      ? (savedConfiguration as Record<string, unknown>).template
      : undefined
  );
  const legacyName = legacyTemplate && typeof legacyTemplate === "object" && !Array.isArray(legacyTemplate)
    ? (legacyTemplate as Record<string, unknown>).name
    : undefined;
  const selected = presetByIdentity(undefined, legacyName);
  if (selected) {
    return { selectedTemplateId: selected.id, template: structuredClone(selected.template) };
  }
  if (legacyTemplate) {
    return { selectedTemplateId: null, template: migrateCustomTemplate(legacyTemplate) };
  }
  return defaultSelection;
}

export function presetForId(id: string | null) {
  return id ? TEMPLATE_LIBRARY.find((preset) => preset.id === id) : undefined;
}
