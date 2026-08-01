import type {
  AnalysisPacket,
  EvidenceItem,
  HealthResponse,
  InterviewReport,
  InterviewTemplate,
  TranscriptTurn,
} from "./types";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return jsonRequest("/api/health");
}

export function analyzeInterview(input: {
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  template: InterviewTemplate;
  focus_evidence_ids: string[];
  mode: "live" | "demo";
}): Promise<AnalysisPacket> {
  return jsonRequest("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function buildReport(input: {
  transcript: TranscriptTurn[];
  evidence: EvidenceItem[];
  template: InterviewTemplate;
  mode: "live" | "demo";
}): Promise<InterviewReport> {
  return jsonRequest("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  const extension = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm";
  const form = new FormData();
  form.append("file", blob, `chunk.${extension}`);
  const result = await jsonRequest<{ text: string }>("/api/transcribe", {
    method: "POST",
    body: form,
  });
  return result.text.trim();
}
