import { describe, expect, it } from "vitest";
import { isSourcedResearchCard, researchCardToEvidence } from "./research";
import type { ResearchCard } from "./types";

const card: ResearchCard = {
  id: "research_official_plan",
  signal: "The official plan already includes a city data platform.",
  ask_next: "Is the gap availability, awareness, trust, or implementation?",
  why_now: "Chiang Mai needs one central smart-city data platform.",
  judge_lens: "New",
  source_title: "Official Chiang Mai smart-city plan",
  source_url: "https://example.org/plan.pdf",
  source_date: "2025-02-24",
  confidence: 0.93,
  related_evidence_ids: ["evidence-platform"],
};

describe("research evidence provenance", () => {
  it("preserves the source URL and full provenance when pinned", () => {
    const evidence = researchCardToEvidence(card, true, ["turn-7"]);

    expect(evidence.source).toBe("web");
    expect(evidence.url).toBe(card.source_url);
    expect(evidence.promoted).toBe(true);
    expect(evidence.source_turn_ids).toEqual(["turn-7"]);
    expect(evidence.provenance).toEqual({
      research_id: card.id,
      source_title: card.source_title,
      source_url: card.source_url,
      source_date: card.source_date,
      why_now: card.why_now,
      judge_lens: card.judge_lens,
    });
  });

  it("rejects an unsourced card before it reaches the UI", () => {
    expect(isSourcedResearchCard({ ...card, source_url: "" })).toBe(false);
    expect(isSourcedResearchCard({ ...card, source_url: "javascript:alert(1)" })).toBe(false);
  });
});
