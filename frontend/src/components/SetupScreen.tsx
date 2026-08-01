import { ArrowRight, AudioLines, Check, Play, Sparkles } from "lucide-react";
import type { HealthResponse, InterviewTemplate } from "../types";

interface SetupScreenProps {
  template: InterviewTemplate;
  health: HealthResponse | null;
  onChange: (template: InterviewTemplate) => void;
  onStart: () => void;
  onDemo: () => void;
}

export function SetupScreen({ template, health, onChange, onStart, onDemo }: SetupScreenProps) {
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

          <div className="capability-list" aria-label="Local capabilities">
            <div className="capability-row">
              <span className={`capability-dot ${health?.agent.available ? "ready" : ""}`} />
              <div>
                <strong>OpenAI research partner</strong>
                <span>{health?.agent.available ? "OAuth ready" : "Checking local runtime"}</span>
              </div>
              <span className="capability-meta">{health?.agent.model?.replace("openai/", "") ?? "—"}</span>
            </div>
            <div className="capability-row">
              <span className={`capability-dot ${health?.transcription.available ? "ready" : ""}`} />
              <div>
                <strong>Private transcription</strong>
                <span>{health?.transcription.available ? "Runs on this Mac" : "Typed input available"}</span>
              </div>
              <AudioLines size={17} />
            </div>
          </div>
        </div>

        <div className="setup-card">
          <div className="setup-card-heading">
            <div>
              <p className="card-kicker">Interview template</p>
              <h2>Prepare the room</h2>
            </div>
            <span className="step-count">01</span>
          </div>

          <label className="field-label" htmlFor="template-name">Topic</label>
          <input
            id="template-name"
            className="text-input"
            value={template.name}
            onChange={(event) => onChange({ ...template, name: event.target.value })}
          />

          <label className="field-label" htmlFor="template-objective">Objective</label>
          <textarea
            id="template-objective"
            className="text-area"
            rows={3}
            value={template.objective}
            onChange={(event) => onChange({ ...template, objective: event.target.value })}
          />

          <div className="field-label phases-label">Conversation arc</div>
          <div className="phase-grid">
            {template.phases.map((phase, index) => (
              <div className="phase-item" key={phase}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                {phase}
                <Check size={14} />
              </div>
            ))}
          </div>

          <div className="setup-actions">
            <button className="button button-primary" onClick={onStart}>
              Start interview <ArrowRight size={17} />
            </button>
            <button className="button button-secondary" onClick={onDemo}>
              <Play size={15} fill="currentColor" /> Run guided demo
            </button>
          </div>
          <p className="setup-footnote">The microphone starts with the interview and stays on until you end it. Audio is transcribed locally.</p>
        </div>
      </section>
    </main>
  );
}
