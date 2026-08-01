import { ArrowRight, AudioLines, Check, Play, Settings, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { countConfigurationChanges } from "../config";
import { buildBreadcrumbs } from "../guidance";
import type {
  HealthResponse,
  InterviewConfiguration,
  InterviewTemplate,
  InterviewTemplatePreset,
} from "../types";
import { AdvancedConfigurationDialog } from "./AdvancedConfigurationDialog";

interface SetupScreenProps {
  configuration: InterviewConfiguration;
  defaultConfiguration: InterviewConfiguration;
  presets: InterviewTemplatePreset[];
  selectedTemplateId: string | null;
  health: HealthResponse | null;
  validation: { state: "checking" | "valid" | "invalid"; message?: string };
  isStarting: boolean;
  onChange: (configuration: InterviewConfiguration) => void;
  onTemplateChange: (template: InterviewTemplate) => void;
  onSelectTemplate: (id: string) => void;
  onStart: () => void;
  onDemo: () => void;
}

export function SetupScreen({
  configuration,
  defaultConfiguration,
  presets,
  selectedTemplateId,
  health,
  validation,
  isStarting,
  onChange,
  onTemplateChange,
  onSelectTemplate,
  onStart,
  onDemo,
}: SetupScreenProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const advancedTrigger = useRef<HTMLButtonElement>(null);
  const template = configuration.template;
  const selectedPreset = presets.find((preset) => preset.id === selectedTemplateId);
  const starterQuestions = selectedPreset?.starter_questions;
  const breadcrumbs = buildBreadcrumbs(template, starterQuestions);
  const selectedDefault = { ...defaultConfiguration, template: selectedPreset?.template ?? template };
  const dirtyCount = countConfigurationChanges(configuration, selectedDefault);

  function closeAdvanced() {
    setAdvancedOpen(false);
    window.requestAnimationFrame(() => advancedTrigger.current?.focus());
  }

  return (
    <main className="setup-shell">
      <nav className="setup-nav">
        <div className="brand-lockup">
          <span className="brand-mark"><Sparkles size={16} strokeWidth={1.8} /></span>
          <span>Interview Copilot</span>
        </div>
        <span className="prototype-label">Local prototype</span>
      </nav>

      <section className="setup-grid">
        <div className="setup-intro">
          <p className="eyebrow">A live research partner</p>
          <h1>Better questions.<br />Stronger evidence.</h1>
          <p className="setup-lede">
            Conduct the conversation. Your copilot turns it into a shared evidence pool and
            quietly surfaces the next question worth asking.
          </p>

          <figure className="research-radar-visual">
            <div className="research-radar-art">
              <img
                src="/research-radar.webp"
                alt="Five investigative research paths converging on the interviewer's next useful question"
                width="1854"
                height="848"
              />
              <span className="research-radar-count" aria-hidden="true">05</span>
            </div>
            <figcaption>
              <div>
                <small>Silent research radar</small>
                <strong>The next question, not more noise.</strong>
              </div>
              <ul aria-label="Five live research paths">
                <li>Verify policy</li>
                <li>Break absence claims</li>
                <li>Find public data</li>
                <li>Expose access gaps</li>
                <li>Connect a pilot</li>
              </ul>
            </figcaption>
          </figure>

          <div className="capability-list" aria-label="Local capabilities">
            <div className="capability-row">
              <span className={`capability-dot ${health?.agent.available ? "ready" : ""}`} />
              <div><strong>OpenAI research partner</strong><span>{health?.agent.available ? "OAuth ready" : "Checking local runtime"}</span></div>
              <span className="capability-meta">{health?.agent.model?.replace("openai/", "") ?? "—"}</span>
            </div>
            <div className="capability-row">
              <span className={`capability-dot ${health?.transcription.available ? "ready" : ""}`} />
              <div><strong>Private transcription</strong><span>{health?.transcription.available ? "Runs on this Mac" : "Typed input available"}</span></div>
              <AudioLines size={17} />
            </div>
          </div>
        </div>

        <div className="setup-card">
          <div className="setup-card-heading">
            <div><p className="card-kicker">Nimman Mini Hackathon</p><h2>Choose a conversation path</h2></div>
            <span className="step-count">04</span>
          </div>

          <div className="template-selector" role="radiogroup" aria-label="Interview template library">
            {presets.map((preset) => {
              const selected = preset.id === selectedTemplateId;
              return (
                <button
                  className={`template-option ${selected ? "selected" : ""}`}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => onSelectTemplate(preset.id)}
                  key={preset.id}
                >
                  <span className="template-option-topline">
                    <small>{preset.track}</small>
                    <i>{selected ? <Check size={11} /> : null}</i>
                  </span>
                  <strong>{preset.template.name}</strong>
                  <span>{preset.short_objective}</span>
                </button>
              );
            })}
          </div>

          <div className="selected-template-meta">
            <span>{selectedPreset?.track ?? "Custom interview"}</span>
            <small>{selectedPreset ? "Library template" : "Edited path · generic questions active"}</small>
          </div>

          <label className="field-label" htmlFor="template-name">Topic</label>
          <input id="template-name" className="text-input" value={template.name} onChange={(event) => onTemplateChange({ ...template, name: event.target.value })} />

          <label className="field-label" htmlFor="template-objective">Objective</label>
          <textarea id="template-objective" className="text-area" rows={2} value={template.objective} onChange={(event) => onTemplateChange({ ...template, objective: event.target.value })} />

          <div className="field-label phases-label">Conversation arc</div>
          <div className="phase-grid">
            {template.phases.map((phase, index) => (
              <div className="phase-item" key={`${index}-${phase}`}><span>{String(index + 1).padStart(2, "0")}</span>{phase}<Check size={14} /></div>
            ))}
          </div>

          <details className="setup-guide-preview">
            <summary>Conversation safety rail <small>{breadcrumbs.length} prompts · {template.success_metrics.length} success signals</small></summary>
            <p>Use this as a safety rail, then follow the participant's words.</p>
            <ol className="setup-path-preview">
              {breadcrumbs.map((item, index) => (
                <li key={`${item.stage}-${item.question}`}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div><small>{item.stage}</small><strong>{item.question}</strong></div>
                </li>
              ))}
            </ol>
            <div className="success-preview">
              <span className="field-label">Success signals</span>
              <ul>
                {template.success_metrics.map((metric) => (
                  <li key={metric}><Check size={12} /><span>{metric}</span></li>
                ))}
              </ul>
            </div>
          </details>

          <div className="advanced-trigger-row">
            <button ref={advancedTrigger} className="advanced-trigger" type="button" onClick={() => setAdvancedOpen(true)}><Settings size={15} /> Advanced configuration</button>
            <span className={`configuration-status ${validation.state}`}>{dirtyCount ? `${dirtyCount} changed` : "Default preset"} · {validation.state === "valid" ? "Valid" : validation.state === "checking" ? "Checking" : "Invalid"}</span>
          </div>
          {validation.state === "invalid" && <p className="setup-validation-error" role="alert">{validation.message}</p>}

          <div className="setup-actions">
            <button className="button button-primary" onClick={onStart} disabled={validation.state !== "valid" || isStarting}>{isStarting ? "Preparing archive…" : "Start interview"} <ArrowRight size={17} /></button>
            <button className="button button-secondary" onClick={onDemo} disabled={validation.state !== "valid" || isStarting}><Play size={15} fill="currentColor" /> Run guided demo</button>
          </div>
          <p className="setup-footnote">The microphone stays on until you end the interview. Audio, transcript, and the exact configuration are saved locally as they happen.</p>
        </div>
      </section>

      {advancedOpen && (
        <AdvancedConfigurationDialog
          configuration={configuration}
          defaultConfiguration={selectedDefault}
          onCancel={closeAdvanced}
          onApply={(next) => { onChange(next); closeAdvanced(); }}
        />
      )}
    </main>
  );
}
