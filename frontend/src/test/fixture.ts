import type { InterviewConfiguration } from "../types";

export const configurationFixture: InterviewConfiguration = {
  schema_version: 1,
  template: {
    name: "Digital nomad frictions",
    objective: "Discover recurring pains and workarounds.",
    phases: ["Rapport", "Current workflow", "Frustrations"],
    success_metrics: ["Learned the current process", "Found the biggest pain"],
    interviewer_guidance: ["Prefer recent concrete examples."],
  },
  copilot: {
    system_prompt: "System prompt",
    task_prompt: "Task prompt",
    lenses: { clarification: true, opportunity: true, bias_guard: true, memory: true, research: true },
    limits: { transcript_turns: 18, evidence_context_items: 30, new_evidence_items: 4, suggestions: 4 },
    promoted_evidence_first: true,
  },
  report: {
    system_prompt: "Report system",
    task_prompt: "Report task",
    next_step_instruction: "Recommend the least-effort useful test.",
    sections: {
      summary: true,
      top_pains: true,
      key_facts: true,
      quotes: true,
      unanswered_questions: true,
      opportunity: true,
      next_step: true,
      coverage: true,
    },
    score_against_success_metrics: true,
  },
  audio: {
    segment_ms: 7000,
    overlap_ms: 200,
    default_speaker: "Participant",
    persist_raw_audio: true,
    whisper_language: "auto",
    whisper_model: "~/.cache/whisper/ggml-base.en.bin",
  },
  runtime: { model: "openai/gpt-5.6-sol", archive_root: "data/interviews" },
  developer: {
    analysis_output_contract: "default",
    report_output_contract: "default",
    demo_script: "default",
    fallback_profile: "default",
  },
};
