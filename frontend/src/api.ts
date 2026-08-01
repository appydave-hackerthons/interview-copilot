import type {
  AnalysisPacket,
  EvidenceItem,
  HealthResponse,
  InterviewConfiguration,
  PersistentInterviewReport,
  ResearchPacket,
  TranscriptTurn,
} from "./types";
import { isSourcedResearchCard } from "./research";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json() as { detail?: string | Array<{ loc?: Array<string | number>; msg?: string }> };
      if (typeof payload.detail === "string") message = payload.detail;
      if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => `${item.loc?.slice(1).join(".") || "configuration"}: ${item.msg || "Invalid value"}`)
          .join("\n");
      }
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const jsonInit = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function fetchHealth(): Promise<HealthResponse> {
  return jsonRequest("/api/health");
}

export function fetchDefaultConfiguration(): Promise<InterviewConfiguration> {
  return jsonRequest("/api/config/default");
}

export interface ReportIndexItem {
  report_id: number;
  session_id: string;
  created_at: string;
  summary: string;
  score: number;
  html_url: string;
  json_url: string;
}

export function fetchReports(): Promise<ReportIndexItem[]> {
  return jsonRequest("/api/reports");
}

export function fetchReport(reportId: number): Promise<PersistentInterviewReport> {
  return jsonRequest(`/api/reports/${reportId}`);
}

export function validateConfiguration(configuration: unknown): Promise<InterviewConfiguration> {
  return jsonRequest("/api/config/validate", jsonInit(configuration));
}

export function startInterviewSession(input: {
  session_id: string;
  configuration: InterviewConfiguration;
  mode: "live" | "demo";
}): Promise<{ session_id: string }> {
  return jsonRequest("/api/interviews/start", jsonInit(input));
}

export function analyzeInterview(input: {
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  configuration: InterviewConfiguration;
  focus_evidence_ids: string[];
  mode: "live" | "demo";
}): Promise<AnalysisPacket> {
  return jsonRequest("/api/analyze", jsonInit(input));
}

export function buildReport(input: {
  session_id: string;
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  configuration: InterviewConfiguration;
  mode: "live" | "demo";
}): Promise<PersistentInterviewReport> {
  return jsonRequest("/api/report", jsonInit(input));
}

export async function researchInterview(input: {
  session_id: string;
  revision: number;
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  configuration: InterviewConfiguration;
  mode: "live" | "demo";
}, signal?: AbortSignal): Promise<ResearchPacket> {
  const packet = await jsonRequest<ResearchPacket>("/api/research", {
    ...jsonInit(input),
    signal,
  });
  return {
    ...packet,
    cards: packet.cards.filter(isSourcedResearchCard).slice(0, 2),
  };
}

export async function transcribeAudio(blob: Blob, metadata: {
  sessionId: string;
  sequence: number;
  speaker: string;
  elapsedSeconds: number;
}): Promise<string> {
  const extension = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm";
  const form = new FormData();
  form.append("file", blob, `chunk.${extension}`);
  form.append("session_id", metadata.sessionId);
  form.append("sequence", String(metadata.sequence));
  form.append("speaker", metadata.speaker);
  form.append("elapsed_seconds", String(metadata.elapsedSeconds));
  const result = await jsonRequest<{ text: string }>("/api/transcribe", {
    method: "POST",
    body: form,
  });
  return result.text.trim();
}
