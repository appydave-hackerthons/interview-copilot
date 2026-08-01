import {
  AlertTriangle,
  Brain,
  Compass,
  Lightbulb,
  MessageCircleQuestion,
  Pin,
  Search,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import type { AgentName, AgentSuggestion } from "../types";

interface ActivityPanelProps {
  suggestions: AgentSuggestion[];
  isAnalyzing: boolean;
  onPin: (suggestion: AgentSuggestion, promote?: boolean) => void;
  onDismiss: (id: string) => void;
}

const agentMeta: Record<AgentName, { icon: typeof Brain; className: string }> = {
  Clarification: { icon: MessageCircleQuestion, className: "clarification" },
  Opportunity: { icon: Lightbulb, className: "opportunity" },
  "Bias guard": { icon: AlertTriangle, className: "bias" },
  Memory: { icon: Brain, className: "memory" },
  Research: { icon: Search, className: "research" },
};

export function ActivityPanel({ suggestions, isAnalyzing, onPin, onDismiss }: ActivityPanelProps) {
  return (
    <section className="workspace-panel activity-panel">
      <header className="panel-header">
        <div>
          <p className="panel-index">02</p>
          <h2>Agent activity</h2>
        </div>
        <span className={`thinking-status ${isAnalyzing ? "active" : ""}`}>
          <i /> {isAnalyzing ? "Thinking" : "Watching"}
        </span>
      </header>

      <div className="activity-scroll panel-scroll">
        {isAnalyzing && (
          <div className="agent-thinking-card">
            <Sparkles size={16} />
            <div><strong>Reading the evidence pool</strong><span>Specialist lenses are checking the latest turn.</span></div>
            <span className="typing-dots"><i /><i /><i /></span>
          </div>
        )}

        {suggestions.length === 0 && !isAnalyzing ? (
          <div className="empty-state activity-empty">
            <Compass size={25} strokeWidth={1.4} />
            <h3>Listening for a thread</h3>
            <p>Useful questions and patterns will appear here as the evidence grows.</p>
          </div>
        ) : (
          suggestions.map((suggestion) => {
            const meta = agentMeta[suggestion.agent];
            const Icon = meta.icon;
            return (
              <article className={`suggestion-card ${meta.className}`} key={suggestion.id}>
                <div className="suggestion-topline">
                  <span className="agent-label"><Icon size={14} /> {suggestion.agent}</span>
                  <span className={`priority-dot ${suggestion.priority}`} title={`${suggestion.priority} priority`} />
                </div>
                <p className="suggestion-text">{suggestion.text}</p>
                {suggestion.rationale && <p className="suggestion-rationale">{suggestion.rationale}</p>}
                <div className="suggestion-actions">
                  <button onClick={() => onPin(suggestion)} title="Pin to evidence"><Pin size={14} /> Pin</button>
                  <button onClick={() => onPin(suggestion, true)} title="Promote for agent attention"><Star size={14} /> Promote</button>
                  <button className="dismiss-action" onClick={() => onDismiss(suggestion.id)} title="Dismiss"><X size={15} /></button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
