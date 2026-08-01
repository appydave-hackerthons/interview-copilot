import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { configurationToYaml } from "../config";
import { configurationFixture } from "../test/fixture";
import { AdvancedConfigurationDialog } from "./AdvancedConfigurationDialog";

describe("AdvancedConfigurationDialog", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => new Response(String(init?.body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
  });

  afterEach(() => vi.unstubAllGlobals());

  it("keeps Cancel separate from a validated Apply", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onApply = vi.fn();
    render(<AdvancedConfigurationDialog configuration={configurationFixture} defaultConfiguration={configurationFixture} onCancel={onCancel} onApply={onApply} />);

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onApply).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Interview name"));
    await user.type(screen.getByLabelText("Interview name"), "A changed interview");
    expect(await screen.findByText("Default preset · 1 value changed")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply.mock.calls[0][0].template.name).toBe("A changed interview");
  });

  it("adds, deletes, and reorders list items", async () => {
    const user = userEvent.setup();
    render(<AdvancedConfigurationDialog configuration={configurationFixture} defaultConfiguration={configurationFixture} onCancel={vi.fn()} onApply={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Add phase" }));
    const fourth = screen.getByLabelText("Phases 4");
    await user.type(fourth, "Ideal future");
    await user.click(screen.getByRole("button", { name: "Move Phases 4 up" }));
    expect(screen.getByLabelText("Phases 3")).toHaveValue("Ideal future");
    await user.click(screen.getByRole("button", { name: "Delete Phases 3" }));
    expect(screen.queryByDisplayValue("Ideal future")).not.toBeInTheDocument();
  });

  it("round-trips modes and disables Apply for line-aware invalid YAML", async () => {
    const user = userEvent.setup();
    render(<AdvancedConfigurationDialog configuration={configurationFixture} defaultConfiguration={configurationFixture} onCancel={vi.fn()} onApply={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "YAML" }));
    const editor = screen.getByLabelText("Complete configuration YAML");
    fireEvent.change(editor, { target: { value: "schema_version: [broken" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(/line 1/i);
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Form" })).toBeDisabled();

    fireEvent.change(editor, { target: { value: configurationToYaml({ ...configurationFixture, template: { ...configurationFixture.template, name: "YAML interview" } }) } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Form" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Form" }));
    expect(screen.getByLabelText("Interview name")).toHaveValue("YAML interview");
  });

  it("imports, exports, and resets YAML", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const createUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:configuration");
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const { container } = render(<AdvancedConfigurationDialog configuration={configurationFixture} defaultConfiguration={configurationFixture} onCancel={vi.fn()} onApply={vi.fn()} />);
    const imported = { ...configurationFixture, template: { ...configurationFixture.template, name: "Imported interview" } };
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, new File([configurationToYaml(imported)], "import.yml", { type: "application/yaml" }));
    expect(await screen.findByDisplayValue(/Imported interview/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Export" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Export" }));
    expect(createUrl).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect((screen.getByLabelText("Complete configuration YAML") as HTMLTextAreaElement).value).toContain("Digital nomad frictions");
  });
});
