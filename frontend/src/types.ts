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
}

export interface InterviewTemplate {
  name: string;
  objective: string;
  phases: string[];
  success_metrics: string[];
}

export interface AnalysisPacket {
  suggestions: AgentSuggestion[];
  evidence: EvidenceItem[];
  engine: "openai" | "local";
  notice?: string | null;
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

export interface HealthResponse {
  status: string;
  agent: { available: boolean; model: string };
  transcription: { available: boolean; model: string | null };
}
