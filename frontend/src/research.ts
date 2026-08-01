import type { EvidenceItem, ResearchCard } from "./types";

export function isSourcedResearchCard(card: ResearchCard): boolean {
  if (!card.source_title?.trim() || !card.signal?.trim() || !card.ask_next?.endsWith("?")) return false;
  try {
    const url = new URL(card.source_url);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

export function researchCardToEvidence(
  card: ResearchCard,
  promote = false,
  sourceTurnIds: string[] = [],
): EvidenceItem {
  return {
    id: `web-${card.id}`,
    type: "source",
    text: card.signal,
    confidence: card.confidence,
    pinned: true,
    promoted: promote,
    source: "web",
    source_turn_ids: sourceTurnIds,
    related_evidence_ids: card.related_evidence_ids,
    agents: ["Research"],
    url: card.source_url,
    provenance: {
      research_id: card.id,
      source_title: card.source_title,
      source_url: card.source_url,
      source_date: card.source_date,
      why_now: card.why_now,
      judge_lens: card.judge_lens,
    },
  };
}
