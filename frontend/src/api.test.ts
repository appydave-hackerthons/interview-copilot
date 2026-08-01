import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeInterview, buildReport, researchInterview, startInterviewSession } from "./api";
import { configurationFixture } from "./test/fixture";

describe("configuration request contracts", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("includes the full configuration in analysis, report, and session start", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/analyze")) return new Response(JSON.stringify({ suggestions: [], evidence: [], engine: "local" }), { status: 200 });
      if (url.endsWith("/report")) return new Response(JSON.stringify({ summary: "", top_pains: [], key_facts: [], quotes: [], unanswered_questions: [], opportunity: "", next_step: "", score: 0, coverage: [], engine: "local" }), { status: 200 });
      if (url.endsWith("/research")) return new Response(JSON.stringify({ cards: [], revision: 1, stale: false, from_cache: false }), { status: 200 });
      return new Response(JSON.stringify({ session_id: "session-1" }), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await analyzeInterview({ transcript: [], evidence: [], configuration: configurationFixture, focus_evidence_ids: [], mode: "live" });
    await buildReport({ session_id: "session-1", transcript: [], evidence: [], configuration: configurationFixture, mode: "live" });
    await researchInterview({ session_id: "session-1", revision: 1, transcript: [], evidence: [], configuration: configurationFixture, mode: "live" });
    await startInterviewSession({ session_id: "session-1", configuration: configurationFixture, mode: "live" });

    for (const [, init] of fetchMock.mock.calls) {
      expect(JSON.parse(String(init?.body)).configuration).toEqual(configurationFixture);
    }
  });
});
