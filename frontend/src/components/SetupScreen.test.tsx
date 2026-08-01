import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { configurationFixture } from "../test/fixture";
import { DEFAULT_TEMPLATE_ID, TEMPLATE_LIBRARY } from "../templates";
import { SetupScreen } from "./SetupScreen";

afterEach(() => vi.unstubAllGlobals());

it("shows the five research paths as a front-page visual", () => {
  render(
    <SetupScreen
      configuration={configurationFixture}
      defaultConfiguration={configurationFixture}
      presets={TEMPLATE_LIBRARY}
      selectedTemplateId={DEFAULT_TEMPLATE_ID}
      health={null}
      validation={{ state: "valid" }}
      isStarting={false}
      onChange={vi.fn()}
      onTemplateChange={vi.fn()}
      onSelectTemplate={vi.fn()}
      onStart={vi.fn()}
      onDemo={vi.fn()}
    />,
  );

  expect(screen.getByRole("img", { name: /five investigative research paths/i })).toHaveAttribute(
    "src",
    "/research-radar.webp",
  );
  expect(screen.getByText("Verify policy")).toBeInTheDocument();
  expect(screen.getByText("Connect a pilot")).toBeInTheDocument();
});

it("opens and closes Advanced and restores focus to its trigger", async () => {
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => new Response(String(init?.body), { status: 200 })));
  const user = userEvent.setup();
  render(
    <SetupScreen
      configuration={configurationFixture}
      defaultConfiguration={configurationFixture}
      presets={TEMPLATE_LIBRARY}
      selectedTemplateId={DEFAULT_TEMPLATE_ID}
      health={null}
      validation={{ state: "valid" }}
      isStarting={false}
      onChange={vi.fn()}
      onTemplateChange={vi.fn()}
      onSelectTemplate={vi.fn()}
      onStart={vi.fn()}
      onDemo={vi.fn()}
    />,
  );

  const trigger = screen.getByRole("button", { name: "Advanced configuration" });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog");
  expect(dialog).toBeInTheDocument();
  fireEvent(dialog, new Event("cancel", { bubbles: false, cancelable: true }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
