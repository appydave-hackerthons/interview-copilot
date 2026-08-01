import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TranscriptPanel } from "./TranscriptPanel";

describe("TranscriptPanel", () => {
  it("renders every line as one compact stream without speaker differentiation", () => {
    render(
      <TranscriptPanel
        transcript={[
          { id: "one", speaker: "Interviewer", text: "First line", elapsed_seconds: 2 },
          { id: "two", speaker: "Participant", text: "Second line", elapsed_seconds: 9 },
        ]}
        isRecording
        isTranscribing={false}
        isEnding={false}
        transcriptionAvailable
        onSubmit={vi.fn()}
        onEnableRecording={vi.fn()}
      />,
    );

    expect(screen.getByText("First line")).toBeInTheDocument();
    expect(screen.getByText("Second line")).toBeInTheDocument();
    expect(screen.queryByText("Interviewer")).not.toBeInTheDocument();
    expect(screen.queryByText("Participant")).not.toBeInTheDocument();
    expect(screen.getByText("Single live stream")).toBeInTheDocument();
  });
});
