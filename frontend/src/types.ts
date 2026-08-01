export type Speaker = "Interviewer" | "Participant";
export type EvidenceType =
  | "fact"
  | "pain"
  | "quote"
  | "question"
  | "source"
  | "insight"
  | "tool"
  | "workflow";
export type AgentName =
  | "Clarification"
  | "Opportunity"
  | "Bias guard"
  | "Memory"
  | "Research";
export type JudgeLens = "Real" | "New" | "Good" | "Feasible";

export interface TranscriptTurn {
  id: string;
  speaker: Speaker;
  text: string;
  elapsed_seconds: number;
}

export interface EvidenceItem {
  id: string;
  type: EvidenceType;
  text: string;
  confidence: number;
  pinned: boolean;
  promoted: boolean;
  source: "transcript" | "agent" | "web";
  source_turn_ids: string[];
  related_evidence_ids: string[];
  agents: AgentName[];
  url?: string | null;
  provenance?: WebProvenance | null;
}

export interface WebProvenance {
  research_id: string;
  source_title: string;
  source_url: string;
  source_date: string | null;
  why_now: string;
  judge_lens: JudgeLens;
}

export interface AgentSuggestion {
  id: string;
  agent: AgentName;
  kind: "question" | "pattern" | "opportunity" | "warning" | "research";
  text: string;
  rationale: string;
  evidence_ids: string[];
  priority: "low" | "medium" | "high";
  createdAt?: number;
  pinned?: boolean;
}

export interface InterviewTemplate {
  name: string;
  objective: string;
  phases: string[];
  success_metrics: string[];
  interviewer_guidance: string[];
}

export interface InterviewTemplatePreset {
  id: string;
  track: string;
  short_objective: string;
  template: InterviewTemplate;
  starter_questions: string[];
}

export interface CopilotConfiguration {
  system_prompt: string;
  task_prompt: string;
  lenses: {
    clarification: boolean;
    opportunity: boolean;
    bias_guard: boolean;
    memory: boolean;
    research: boolean;
  };
  limits: {
    transcript_turns: number;
    evidence_context_items: number;
    new_evidence_items: number;
    suggestions: number;
  };
  promoted_evidence_first: boolean;
}

export interface ReportConfiguration {
  system_prompt: string;
  task_prompt: string;
  next_step_instruction: string;
  sections: {
    summary: boolean;
    top_pains: boolean;
    key_facts: boolean;
    quotes: boolean;
    unanswered_questions: boolean;
    opportunity: boolean;
    next_step: boolean;
    coverage: boolean;
  };
  score_against_success_metrics: boolean;
}

export interface AudioConfiguration {
  segment_ms: number;
  overlap_ms: number;
  default_speaker: Speaker;
  persist_raw_audio: boolean;
  whisper_language: string;
  whisper_model: string;
}

export interface RuntimeConfiguration {
  model: string;
  archive_root: string;
}

export interface DeveloperConfiguration {
  analysis_output_contract: "default";
  report_output_contract: "default";
  demo_script: string;
  fallback_profile: "default";
}

export interface InterviewConfiguration {
  schema_version: 1;
  template: InterviewTemplate;
  copilot: CopilotConfiguration;
  report: ReportConfiguration;
  audio: AudioConfiguration;
  runtime: RuntimeConfiguration;
  developer: DeveloperConfiguration;
}

export interface AnalysisPacket {
  suggestions: AgentSuggestion[];
  evidence: EvidenceItem[];
  engine: "openai" | "local";
  notice?: string | null;
}

export interface ResearchCard {
  id: string;
  signal: string;
  ask_next: string;
  why_now: string;
  judge_lens: JudgeLens;
  source_title: string;
  source_url: string;
  source_date: string | null;
  confidence: number;
  related_evidence_ids: string[];
  createdAt?: number;
  pinned?: boolean;
}

export interface ResearchPacket {
  cards: ResearchCard[];
  revision: number;
  stale: boolean;
  from_cache: boolean;
}

export interface CoverageItem {
  label: string;
  complete: boolean;
}

export interface InterviewReport {
  summary: string;
  top_pains: string[];
  key_facts: string[];
  quotes: string[];
  unanswered_questions: string[];
  opportunity: string;
  next_step: string;
  score: number;
  coverage: CoverageItem[];
  engine: "openai" | "local";
  notice?: string | null;
}

export interface PersistentInterviewReport extends InterviewReport {
  report_id: number;
  session_id: string;
  created_at: string;
  template: InterviewTemplate;
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  html_url: string;
  json_url: string;
}

export interface HealthResponse {
  status: string;
  agent: { available: boolean; model: string };
  research?: { available: boolean };
  transcription: {
    available: boolean;
    model: string | null;
    model_path: string | null;
    language: string;
  };
}
