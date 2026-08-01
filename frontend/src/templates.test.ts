import { describe, expect, it } from "vitest";
import {
  DEFAULT_TEMPLATE_ID,
  migrateStoredTemplateSelection,
  TEMPLATE_LIBRARY,
} from "./templates";

describe("template storage migration", () => {
  it("maps the legacy digital-nomad template to current library defaults", () => {
    const migrated = migrateStoredTemplateSelection({
      template: {
        name: "Digital nomad frictions",
        objective: "Stale saved objective",
        phases: ["Stale phase"],
        success_metrics: ["Stale metric"],
      },
    });

    expect(migrated.selectedTemplateId).toBe(DEFAULT_TEMPLATE_ID);
    expect(migrated.template).toEqual(TEMPLATE_LIBRARY[0].template);
    expect(migrated.template.objective).not.toContain("Stale");
  });

  it("fills fields missing from a legacy custom template with safe defaults", () => {
    const migrated = migrateStoredTemplateSelection({
      template: {
        name: "Market errands",
        objective: "Understand difficult weekly errands.",
      },
    });

    expect(migrated.selectedTemplateId).toBeNull();
    expect(migrated.template.name).toBe("Market errands");
    expect(migrated.template.phases).toHaveLength(6);
    expect(migrated.template.success_metrics.length).toBeGreaterThan(0);
    expect(migrated.template.interviewer_guidance.length).toBeGreaterThan(0);
  });
});
