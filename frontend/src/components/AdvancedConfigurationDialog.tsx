import { Download, RotateCcw, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  cloneConfiguration,
  configurationToYaml,
  countConfigurationChanges,
  parseConfigurationYaml,
} from "../config";
import { validateConfiguration } from "../api";
import type { InterviewConfiguration } from "../types";
import { ConfigurationListEditor } from "./ConfigurationListEditor";
import { YamlConfigurationEditor } from "./YamlConfigurationEditor";

type EditorMode = "form" | "yaml";
type ValidationState = "checking" | "valid" | "invalid";

interface AdvancedConfigurationDialogProps {
  configuration: InterviewConfiguration;
  defaultConfiguration: InterviewConfiguration;
  onCancel: () => void;
  onApply: (configuration: InterviewConfiguration) => void;
}

const LENSES = [
  ["clarification", "Clarification", "Advance the depth ladder: outcome, why, current reality, gap, friction, and consequence."],
  ["opportunity", "Opportunity", "Notice repeated work, urgency, and meaningful unmet need."],
  ["bias_guard", "Bias guard", "Catch leading questions and premature solutioning."],
  ["memory", "Memory", "Connect or challenge earlier statements in the evidence pool."],
  ["research", "Research", "Propose specific external checks without inventing sources."],
] as const;

const REPORT_SECTIONS = [
  ["summary", "Summary"],
  ["top_pains", "Top pains"],
  ["key_facts", "Key facts"],
  ["quotes", "Quotes"],
  ["unanswered_questions", "Unanswered questions"],
  ["opportunity", "Opportunity"],
  ["next_step", "Next step"],
  ["coverage", "Coverage"],
] as const;

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Configuration could not be validated.";
}

export function AdvancedConfigurationDialog({
  configuration,
  defaultConfiguration,
  onCancel,
  onApply,
}: AdvancedConfigurationDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const validationSequence = useRef(0);
  const [mode, setMode] = useState<EditorMode>("form");
  const [draft, setDraft] = useState(() => cloneConfiguration(configuration));
  const [yamlSource, setYamlSource] = useState(() => configurationToYaml(configuration));
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [validationState, setValidationState] = useState<ValidationState>("checking");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validatedDraft, setValidatedDraft] = useState<InterviewConfiguration | null>(null);

  const changesFromDefault = useMemo(
    () => countConfigurationChanges(draft, defaultConfiguration),
    [draft, defaultConfiguration],
  );
  const unsavedChanges = useMemo(
    () => countConfigurationChanges(draft, configuration),
    [draft, configuration],
  );
  const yamlHasUnsavedText = mode === "yaml" && yamlSource !== configurationToYaml(configuration);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  useEffect(() => {
    if (yamlError) {
      setValidationState("invalid");
      setValidatedDraft(null);
      return;
    }
    const sequence = ++validationSequence.current;
    setValidationState("checking");
    setValidationError(null);
    const timer = window.setTimeout(() => {
      void validateConfiguration(draft)
        .then((validated) => {
          if (validationSequence.current !== sequence) return;
          setValidatedDraft(validated);
          setValidationState("valid");
        })
        .catch((error: unknown) => {
          if (validationSequence.current !== sequence) return;
          setValidatedDraft(null);
          setValidationState("invalid");
          setValidationError(messageFrom(error));
        });
    }, 220);
    return () => window.clearTimeout(timer);
  }, [draft, yamlError]);

  function updateDraft(next: InterviewConfiguration) {
    setDraft(next);
    setYamlError(null);
  }

  function selectMode(nextMode: EditorMode) {
    if (nextMode === "yaml") {
      setYamlSource(configurationToYaml(validatedDraft ?? draft));
      setMode("yaml");
      return;
    }
    if (!validatedDraft) return;
    setDraft(cloneConfiguration(validatedDraft));
    setMode("form");
  }

  function updateYaml(value: string) {
    setYamlSource(value);
    try {
      const parsed = parseConfigurationYaml(value) as InterviewConfiguration;
      setYamlError(null);
      setDraft(parsed);
    } catch (error) {
      setYamlError(messageFrom(error));
    }
  }

  async function importYaml(file: File | undefined) {
    if (!file) return;
    if (!/\.ya?ml$/i.test(file.name)) {
      setYamlError("Import a .yaml or .yml file.");
      setMode("yaml");
      return;
    }
    updateYaml(await file.text());
    setMode("yaml");
  }

  function exportYaml() {
    if (!validatedDraft) return;
    const blob = new Blob([configurationToYaml(validatedDraft)], { type: "application/yaml" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${validatedDraft.template.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "interview"}.yaml`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function reset() {
    if ((unsavedChanges || yamlHasUnsavedText) && !window.confirm("Discard unsaved changes and restore the default preset?")) return;
    const next = cloneConfiguration(defaultConfiguration);
    setDraft(next);
    setYamlSource(configurationToYaml(next));
    setYamlError(null);
  }

  function apply() {
    if (!validatedDraft) return;
    onApply(cloneConfiguration(validatedDraft));
  }

  const visibleError = yamlError ?? validationError;

  return (
    <dialog
      className="advanced-dialog"
      ref={dialogRef}
      aria-labelledby="advanced-title"
      onCancel={(event) => { event.preventDefault(); onCancel(); }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <div className="advanced-dialog-frame">
        <header className="advanced-header">
          <div>
            <h2 id="advanced-title">Advanced configuration</h2>
            <p>Default preset · {changesFromDefault} {changesFromDefault === 1 ? "value" : "values"} changed</p>
          </div>
          <button className="icon-button" type="button" aria-label="Close advanced configuration" onClick={onCancel}><X size={18} /></button>
          <div className="advanced-toolbar">
            <div className="mode-switch" aria-label="Configuration editor mode">
              <button type="button" className={mode === "form" ? "active" : ""} disabled={mode === "yaml" && !validatedDraft} onClick={() => selectMode("form")}>Form</button>
              <button type="button" className={mode === "yaml" ? "active" : ""} onClick={() => selectMode("yaml")}>YAML</button>
            </div>
            <div className="toolbar-actions">
              <input ref={importRef} type="file" accept=".yaml,.yml,application/yaml,text/yaml" hidden onChange={(event) => void importYaml(event.target.files?.[0])} />
              <button type="button" onClick={() => importRef.current?.click()}><Upload size={14} /> Import</button>
              <button type="button" disabled={!validatedDraft} onClick={exportYaml}><Download size={14} /> Export</button>
              <button type="button" onClick={reset}><RotateCcw size={14} /> Reset</button>
            </div>
          </div>
        </header>

        <div className="advanced-body">
          {mode === "yaml" ? (
            <YamlConfigurationEditor value={yamlSource} error={visibleError} onChange={updateYaml} />
          ) : (
            <div className="configuration-form">
              <details open>
                <summary><span>Interview design</span><small>Name, objective, phases, success criteria and guidance</small></summary>
                <div className="config-section-content">
                  <div className="config-field-grid">
                    <label>Interview name<input value={draft.template.name} onChange={(event) => updateDraft({ ...draft, template: { ...draft.template, name: event.target.value } })} /></label>
                    <label className="wide-field">Objective<textarea rows={3} value={draft.template.objective} onChange={(event) => updateDraft({ ...draft, template: { ...draft.template, objective: event.target.value } })} /></label>
                  </div>
                  <ConfigurationListEditor label="Phases" addLabel="Add phase" items={draft.template.phases} onChange={(phases) => updateDraft({ ...draft, template: { ...draft.template, phases } })} />
                  <ConfigurationListEditor label="Success metrics" addLabel="Add success metric" items={draft.template.success_metrics} onChange={(success_metrics) => updateDraft({ ...draft, template: { ...draft.template, success_metrics } })} />
                  <ConfigurationListEditor label="Interviewer guidance" addLabel="Add guidance" items={draft.template.interviewer_guidance} onChange={(interviewer_guidance) => updateDraft({ ...draft, template: { ...draft.template, interviewer_guidance } })} />
                </div>
              </details>

              <details open>
                <summary><span>Live copilot</span><small>Prompts, specialist lenses, context and output limits</small></summary>
                <div className="config-section-content">
                  <label>Analysis system prompt<textarea rows={5} value={draft.copilot.system_prompt} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, system_prompt: event.target.value } })} /></label>
                  <label>Analysis task prompt<textarea rows={4} value={draft.copilot.task_prompt} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, task_prompt: event.target.value } })} /></label>
                  <fieldset className="toggle-fieldset">
                    <legend>Specialist lenses</legend>
                    {LENSES.map(([key, label, description]) => (
                      <label className="toggle-row" key={key}>
                        <span><strong>{label}</strong><small>{description}</small></span>
                        <input type="checkbox" checked={draft.copilot.lenses[key]} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, lenses: { ...draft.copilot.lenses, [key]: event.target.checked } } })} />
                      </label>
                    ))}
                  </fieldset>
                  <div className="config-number-grid">
                    <label>Transcript turns<input type="number" min={1} max={100} value={draft.copilot.limits.transcript_turns} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, limits: { ...draft.copilot.limits, transcript_turns: Number(event.target.value) } } })} /></label>
                    <label>Evidence context<input type="number" min={1} max={200} value={draft.copilot.limits.evidence_context_items} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, limits: { ...draft.copilot.limits, evidence_context_items: Number(event.target.value) } } })} /></label>
                    <label>New evidence<input type="number" min={0} max={20} value={draft.copilot.limits.new_evidence_items} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, limits: { ...draft.copilot.limits, new_evidence_items: Number(event.target.value) } } })} /></label>
                    <label>Suggestions<input type="number" min={0} max={20} value={draft.copilot.limits.suggestions} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, limits: { ...draft.copilot.limits, suggestions: Number(event.target.value) } } })} /></label>
                  </div>
                  <label className="checkbox-line"><input type="checkbox" checked={draft.copilot.promoted_evidence_first} onChange={(event) => updateDraft({ ...draft, copilot: { ...draft.copilot, promoted_evidence_first: event.target.checked } })} /> Prioritize promoted evidence in model context</label>
                </div>
              </details>

              <details>
                <summary><span>End report</span><small>Synthesis prompts, stable sections and success scoring</small></summary>
                <div className="config-section-content">
                  <label>Report system prompt<textarea rows={4} value={draft.report.system_prompt} onChange={(event) => updateDraft({ ...draft, report: { ...draft.report, system_prompt: event.target.value } })} /></label>
                  <label>Synthesis task prompt<textarea rows={4} value={draft.report.task_prompt} onChange={(event) => updateDraft({ ...draft, report: { ...draft.report, task_prompt: event.target.value } })} /></label>
                  <label>Least-effort next-step instruction<textarea rows={3} value={draft.report.next_step_instruction} onChange={(event) => updateDraft({ ...draft, report: { ...draft.report, next_step_instruction: event.target.value } })} /></label>
                  <fieldset className="toggle-fieldset compact-toggles">
                    <legend>Report sections</legend>
                    {REPORT_SECTIONS.map(([key, label]) => (
                      <label className="toggle-row" key={key}><span><strong>{label}</strong></span><input type="checkbox" checked={draft.report.sections[key]} onChange={(event) => updateDraft({ ...draft, report: { ...draft.report, sections: { ...draft.report.sections, [key]: event.target.checked } } })} /></label>
                    ))}
                  </fieldset>
                  <label className="checkbox-line"><input type="checkbox" checked={draft.report.score_against_success_metrics} onChange={(event) => updateDraft({ ...draft, report: { ...draft.report, score_against_success_metrics: event.target.checked } })} /> Score coverage against success metrics</label>
                </div>
              </details>

              <details>
                <summary><span>Audio and runtime</span><small>Capture timing, speaker, local models and archives</small></summary>
                <div className="config-section-content">
                  <div className="config-number-grid">
                    <label>Segment duration (ms)<input type="number" min={2000} max={60000} value={draft.audio.segment_ms} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, segment_ms: Number(event.target.value) } })} /></label>
                    <label>Overlap (ms)<input type="number" min={0} max={2000} value={draft.audio.overlap_ms} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, overlap_ms: Number(event.target.value) } })} /></label>
                    <label>Default speaker<select value={draft.audio.default_speaker} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, default_speaker: event.target.value as "Interviewer" | "Participant" } })}><option>Participant</option><option>Interviewer</option></select></label>
                  </div>
                  <label className="checkbox-line"><input type="checkbox" checked={draft.audio.persist_raw_audio} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, persist_raw_audio: event.target.checked } })} /> Persist raw audio segments in the session archive</label>
                  <div className="config-field-grid">
                    <label>Whisper language <span className="restart-badge">Requires service restart</span><input value={draft.audio.whisper_language} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, whisper_language: event.target.value } })} /></label>
                    <label className="wide-field">Whisper model path <span className="restart-badge">Requires service restart</span><input value={draft.audio.whisper_model} onChange={(event) => updateDraft({ ...draft, audio: { ...draft.audio, whisper_model: event.target.value } })} /></label>
                    <label>OpenAI model<input value={draft.runtime.model} onChange={(event) => updateDraft({ ...draft, runtime: { ...draft.runtime, model: event.target.value } })} /></label>
                    <label>Archive directory<input value={draft.runtime.archive_root} onChange={(event) => updateDraft({ ...draft, runtime: { ...draft.runtime, archive_root: event.target.value } })} /></label>
                  </div>
                  <p className="config-help">Capture timing, default speaker, model, and archive directory apply to the next interview.</p>
                </div>
              </details>

              <details className="developer-section">
                <summary><span>Developer overrides</span><small>Advanced contracts and deterministic fixtures</small></summary>
                <div className="config-section-content">
                  <div className="developer-warning">These values can break model parsing. Output contracts and the fallback profile are locked to the compatible default in this release.</div>
                  <div className="config-field-grid">
                    <label>Analysis output contract<select value={draft.developer.analysis_output_contract} disabled><option>default</option></select></label>
                    <label>Report output contract<select value={draft.developer.report_output_contract} disabled><option>default</option></select></label>
                    <label>Local fallback profile<select value={draft.developer.fallback_profile} disabled><option>default</option></select></label>
                    <label className="wide-field">Guided-demo script<textarea rows={7} value={draft.developer.demo_script} onChange={(event) => updateDraft({ ...draft, developer: { ...draft.developer, demo_script: event.target.value } })} /><small>Use “default”, or one “Interviewer:” / “Participant:” line per turn.</small></label>
                  </div>
                </div>
              </details>
            </div>
          )}
        </div>

        <footer className="advanced-footer">
          <div className={`validation-summary ${validationState}`}>
            <span aria-hidden>{validationState === "valid" ? "✓" : validationState === "checking" ? "…" : "!"}</span>
            <span>{validationState === "valid" ? "Valid configuration" : validationState === "checking" ? "Checking configuration…" : visibleError?.split("\n")[0] || "Invalid configuration"}</span>
          </div>
          <div>
            <button className="button button-secondary" type="button" onClick={onCancel}>Cancel</button>
            <button className="button button-primary" type="button" disabled={validationState !== "valid" || !validatedDraft} onClick={apply}>Apply</button>
          </div>
        </footer>
      </div>
    </dialog>
  );
}
