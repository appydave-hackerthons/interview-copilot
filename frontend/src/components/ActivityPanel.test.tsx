import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TEMPLATE_LIBRARY } from "../templates";
import { ActivityPanel } from "./ActivityPanel";

describe("ActivityPanel", () => {
  afterEach(() => vi.useRealTimers());

  it("shows a visible expiry ring and makes pin a keep-on-canvas action", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-01T00:00:00Z"));
    const onTogglePin = vi.fn();
    const suggestion = {
      id: "suggestion-1",
      agent: "Clarification" as const,
      kind: "question" as const,
      text: "What happened next?",
      rationale: "The sequence is incomplete.",
      evidence_ids: [],
      priority: "high" as const,
      createdAt: Date.now(),
      pinned: false,
    };

    render(
      <ActivityPanel
        suggestions={[suggestion]}
        researchCards={[]}
        template={TEMPLATE_LIBRARY[0].template}
        starterQuestions={TEMPLATE_LIBRARY[0].starter_questions}
        isAnalyzing={false}
        isResearching={false}
        onTogglePin={onTogglePin}
        onPromote={vi.fn()}
        onDismiss={vi.fn()}
        onToggleResearchPin={vi.fn()}
        onPromoteResearch={vi.fn()}
        onDismissResearch={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Disappears in 60 seconds")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pin" }));
    expect(onTogglePin).toHaveBeenCalledWith(suggestion);
  });
});
