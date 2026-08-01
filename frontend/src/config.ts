import { parseDocument, stringify } from "yaml";
import type { InterviewConfiguration, Speaker } from "./types";

export function cloneConfiguration(configuration: InterviewConfiguration): InterviewConfiguration {
  return structuredClone(configuration);
}

export function countConfigurationChanges(current: unknown, baseline: unknown): number {
  if (Object.is(current, baseline)) return 0;
  if (Array.isArray(current) && Array.isArray(baseline)) {
    const length = Math.max(current.length, baseline.length);
    return Array.from({ length }, (_, index) => countConfigurationChanges(current[index], baseline[index]))
      .reduce((total, value) => total + value, 0);
  }
  if (
    current && baseline && typeof current === "object" && typeof baseline === "object" &&
    !Array.isArray(current) && !Array.isArray(baseline)
  ) {
    const keys = new Set([...Object.keys(current), ...Object.keys(baseline)]);
    return [...keys].reduce(
      (total, key) => total + countConfigurationChanges(
        (current as Record<string, unknown>)[key],
        (baseline as Record<string, unknown>)[key],
      ),
      0,
    );
  }
  return 1;
}

export function configurationToYaml(configuration: InterviewConfiguration): string {
  return stringify(configuration, { indent: 2, lineWidth: 88 });
}

export function parseConfigurationYaml(source: string): unknown {
  const document = parseDocument(source, { prettyErrors: true, strict: true, uniqueKeys: true });
  if (document.errors.length) throw document.errors[0];
  const value = document.toJS({ maxAliasCount: 0 });
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Configuration YAML must contain one mapping object.");
  }
  return value;
}

export function parseDemoScript(source: string): Array<{ speaker: Speaker; text: string }> | null {
  if (source.trim() === "default") return null;
  const lines = source.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return lines.map((line, index) => {
    const match = /^(Interviewer|Participant)\s*:\s*(.+)$/i.exec(line);
    if (!match) {
      throw new Error(`Demo script line ${index + 1} must start with Interviewer: or Participant:`);
    }
    const speaker = `${match[1][0].toUpperCase()}${match[1].slice(1).toLowerCase()}` as Speaker;
    return { speaker, text: match[2].trim() };
  });
}
