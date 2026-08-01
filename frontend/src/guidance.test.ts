import { describe, expect, it } from "vitest";
import {
  buildBreadcrumbs,
  DEPTH_LADDER,
  GUIDANCE_CARD_LIFETIME_MS,
  keepActiveGuidanceCards,
  mergeGuidanceCards,
} from "./guidance";
import { TEMPLATE_LIBRARY } from "./templates";

describe("interview depth guidance", () => {
  it("applies the complete depth ladder to every template path", () => {
    for (const preset of TEMPLATE_LIBRARY) {
      const breadcrumbs = buildBreadcrumbs(preset.template, preset.starter_questions);

      expect(breadcrumbs).toHaveLength(DEPTH_LADDER.length);
      expect(breadcrumbs.map((item) => item.coach).join(" ")).toContain("trying to achieve");
      expect(breadcrumbs.map((item) => item.coach).join(" ")).toContain("expected or imagined");
      expect(breadcrumbs.map((item) => item.coach).join(" ")).toContain("stuck");
    }
  });

  it("keeps prior cards until their timer ends and never expires pinned cards", () => {
    const previous: Array<{ id: string; createdAt?: number; pinned?: boolean }> = [
      { id: "older", createdAt: 0, pinned: false },
      { id: "kept", createdAt: 0, pinned: true },
    ];
    const merged = mergeGuidanceCards(previous, [{ id: "new" }], 1_000);

    expect(merged.map((card) => card.id)).toEqual(["older", "kept", "new"]);
    expect(merged.find((card) => card.id === "new")?.createdAt).toBe(1_000);

    const active = keepActiveGuidanceCards(merged, GUIDANCE_CARD_LIFETIME_MS + 999);
    expect(active.map((card) => card.id)).toEqual(["kept", "new"]);
  });
});
