import { describe, expect, it } from "vitest";
import {
  cloneConfiguration,
  configurationToYaml,
  countConfigurationChanges,
  parseConfigurationYaml,
  parseDemoScript,
} from "./config";
import { configurationFixture } from "./test/fixture";

describe("configuration helpers", () => {
  it("round-trips the complete object through YAML", () => {
    const yaml = configurationToYaml(configurationFixture);
    expect(parseConfigurationYaml(yaml)).toEqual(configurationFixture);
    expect(yaml).toContain("system_prompt:");
  });

  it("counts changed values and freezes with a deep copy", () => {
    const frozen = cloneConfiguration(configurationFixture);
    const draft = cloneConfiguration(configurationFixture);
    draft.template.name = "Edited later";
    draft.copilot.limits.suggestions = 2;

    expect(countConfigurationChanges(draft, frozen)).toBe(2);
    expect(frozen.template.name).toBe("Digital nomad frictions");
    expect(frozen.copilot.limits.suggestions).toBe(4);
  });

  it("parses custom guided-demo lines", () => {
    expect(parseDemoScript("Interviewer: Hello\nParticipant: Hi")).toEqual([
      { speaker: "Interviewer", text: "Hello" },
      { speaker: "Participant", text: "Hi" },
    ]);
    expect(() => parseDemoScript("No speaker here")).toThrow("line 1");
  });
});
