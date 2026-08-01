import {
  AlertTriangle,
  Brain,
  Check,
  ExternalLink,
  Lightbulb,
  ListChecks,
  MessageCircleQuestion,
  Pin,
  Search,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { buildBreadcrumbs, DEPTH_LADDER, GUIDANCE_CARD_LIFETIME_MS } from "../guidance";
import type { AgentName, AgentSuggestion, InterviewTemplate, ResearchCard } from "../types";
import type { CSSProperties } from "react";

interface ActivityPanelProps {
  suggestions: AgentSuggestion[];
  researchCards: ResearchCard[];
  template: InterviewTemplate;
  starterQuestions?: readonly string[];
  isAnalyzing: boolean;
  isResearching: boolean;
  onTogglePin: (suggestion: AgentSuggestion) => void;
  onPromote: (suggestion: AgentSuggestion) => void;
  onDismiss: (id: string) => void;
  onToggleResearchPin: (card: ResearchCard) => void;
  onPromoteResearch: (card: ResearchCard) => void;
  onDismissResearch: (id: string) => void;
}

const agentMeta: Record<AgentName, { icon: typeof Brain; className: string }> = {
  Clarification: { icon: MessageCircleQuestion, className: "clarification" },
  Opportunity: { icon: Lightbulb, className: "opportunity" },
  "Bias guard": { icon: AlertTriangle, className: "bias" },
  Memory: { icon: Brain, className: "memory" },
  Research: { icon: Search, className: "research" },
};

interface ExpiryRingProps {
  createdAt?: number;
  now: number;
  pinned?: boolean;
}

function ExpiryRing({ createdAt, now, pinned }: ExpiryRingProps) {
  if (pinned) {
    return (
      <span className="expiry-ring pinned" aria-label="Pinned — stays on canvas" title="Pinned — stays on canvas">
        <Pin size={10} fill="currentColor" />
      </span>
    );
  }

  const elapsed = Math.max(0, now - (createdAt ?? now));
  const progress = Math.min(1, elapsed / GUIDANCE_CARD_LIFETIME_MS);
  const remaining = Math.max(0, Math.ceil((GUIDANCE_CARD_LIFETIME_MS - elapsed) / 1000));
  return (
    <span
      className="expiry-ring"
      aria-label={`Disappears in ${remaining} seconds`}
      title={`Disappears in ${remaining} seconds`}
      style={{ "--expiry-progress": `${progress * 360}deg` } as CSSProperties}
    >
      <span />
    </span>
  );
}

export function ActivityPanel({
  suggestions,
  researchCards,
  template,
  starterQuestions,
  isAnalyzing,
  isResearching,
  onTogglePin,
  onPromote,
  onDismiss,
  onToggleResearchPin,
  onPromoteResearch,
  onDismissResearch,
}: ActivityPanelProps) {
  const breadcrumbs = useMemo(
    () => buildBreadcrumbs(template, starterQuestions),
    [template, starterQuestions],
  );
  const breadcrumbKey = breadcrumbs.map((item) => item.question).join("|");
  const [asked, setAsked] = useState<Set<number>>(new Set());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => setAsked(new Set()), [breadcrumbKey]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  function toggleAsked(index: number) {
    setAsked((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  const nextQuestion = breadcrumbs.findIndex((_, index) => !asked.has(index));

  return (
    <section className="workspace-panel activity-panel">
      <header className="panel-header">
        <div>
          <p className="panel-index">01</p>
          <h2>Live card canvas</h2>
        </div>
        <div className="canvas-header-meta">
          <span className="canvas-timer-legend"><i /> 60 sec · pin to keep</span>
          <span className={`thinking-status ${isAnalyzing || isResearching ? "active" : ""}`}>
            <i /> {isResearching ? "Researching" : isAnalyzing ? "Thinking" : "Canvas ready"}
          </span>
        </div>
      </header>

      <div className="activity-scroll panel-scroll">
        <section className="breadcrumb-guide" aria-labelledby="breadcrumb-heading">
          <header>
            <span id="breadcrumb-heading"><ListChecks size={14} /> Conversation path</span>
            <small>{asked.size} of {breadcrumbs.length} asked</small>
          </header>
          <p className="breadcrumb-intro">Stay with a useful thread until the gap is clear. Ask one neutral question at a time.</p>
          <p className="depth-ladder" aria-label="Interview depth ladder">{DEPTH_LADDER.join(" → ")}</p>
          <ol>
            {breadcrumbs.map((item, index) => (
              <li className={`${asked.has(index) ? "asked" : ""} ${index === nextQuestion ? "next" : ""}`} key={item.question}>
                <button aria-pressed={asked.has(index)} onClick={() => toggleAsked(index)}>
                  <span className="breadcrumb-marker">{asked.has(index) ? <Check size={12} /> : index + 1}</span>
                  <span className="breadcrumb-copy">
                    <small>{item.stage}</small>
                    <strong>{item.question}</strong>
                    {index === nextQuestion && <em>{item.coach}</em>}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <div className="live-guidance-label"><span>Live guidance · {suggestions.length + researchCards.length} active</span><i /></div>

        <div className="guidance-card-grid">

        {isResearching && researchCards.length === 0 && (
          <div className="research-thinking-card" role="status">
            <Search size={15} />
            <div><strong>Checking one useful claim</strong><span>Only sourced results that change the next question will appear.</span></div>
            <span className="typing-dots"><i /><i /><i /></span>
          </div>
        )}

        {researchCards.map((card) => (
          <article className={`research-card ${card.pinned ? "pinned" : ""}`} key={card.id}>
            <div className="research-topline">
              <span className="agent-label"><Search size={14} /> Live research</span>
              <span className="card-top-meta">
                <span className={`judge-lens lens-${card.judge_lens.toLowerCase()}`}>{card.judge_lens}</span>
                <ExpiryRing createdAt={card.createdAt} now={now} pinned={card.pinned} />
              </span>
            </div>
            <p className="ask-next-label">Ask next</p>
            <p className="research-question">{card.ask_next}</p>
            <p className="research-signal">{card.signal}</p>
            <div className="research-source-meta">
              <span title={card.source_title}>{card.source_title}</span>
              <i />
              <time>{card.source_date ?? "Date not listed"}</time>
              <i />
              <strong>{Math.round(card.confidence * 100)}%</strong>
            </div>
            <div className="suggestion-actions research-actions">
              <a href={card.source_url} target="_blank" rel="noreferrer" title="Open source in a new tab">
                <ExternalLink size={13} /> Open source
              </a>
              <button className={card.pinned ? "active" : ""} onClick={() => onToggleResearchPin(card)} title={card.pinned ? "Let this card expire" : "Keep this card on the canvas"}><Pin size={14} fill={card.pinned ? "currentColor" : "none"} /> {card.pinned ? "Unpin" : "Pin"}</button>
              <button onClick={() => onPromoteResearch(card)} title="Promote sourced finding into evidence"><Star size={14} /> Promote</button>
              <button className="dismiss-action" onClick={() => onDismissResearch(card.id)} title="Dismiss"><X size={15} /></button>
            </div>
          </article>
        ))}

        {isAnalyzing && (
          <div className="agent-thinking-card">
            <Sparkles size={16} />
            <div><strong>Reading the evidence pool</strong><span>Specialist lenses are checking the latest turn.</span></div>
            <span className="typing-dots"><i /><i /><i /></span>
          </div>
        )}

        {suggestions.length === 0 && researchCards.length === 0 && !isAnalyzing && !isResearching ? (
          <div className="guidance-waiting">
            <span className="typing-dots"><i /><i /><i /></span>
            Suggestions will appear here as the conversation develops.
          </div>
        ) : (
          suggestions.map((suggestion) => {
            const meta = agentMeta[suggestion.agent];
            const Icon = meta.icon;
            return (
              <article className={`suggestion-card ${meta.className} ${suggestion.pinned ? "pinned" : ""}`} key={suggestion.id}>
                <div className="suggestion-topline">
                  <span className="agent-label"><Icon size={14} /> {suggestion.agent}</span>
                  <span className="card-top-meta">
                    <span className={`priority-dot ${suggestion.priority}`} title={`${suggestion.priority} priority`} />
                    <ExpiryRing createdAt={suggestion.createdAt} now={now} pinned={suggestion.pinned} />
                  </span>
                </div>
                <p className="suggestion-text">{suggestion.text}</p>
                {suggestion.rationale && <p className="suggestion-rationale">{suggestion.rationale}</p>}
                <div className="suggestion-actions">
                  <button className={suggestion.pinned ? "active" : ""} onClick={() => onTogglePin(suggestion)} title={suggestion.pinned ? "Let this card expire" : "Keep this card on the canvas"}><Pin size={14} fill={suggestion.pinned ? "currentColor" : "none"} /> {suggestion.pinned ? "Unpin" : "Pin"}</button>
                  <button onClick={() => onPromote(suggestion)} title="Promote into evidence for agent attention"><Star size={14} /> Promote</button>
                  <button className="dismiss-action" onClick={() => onDismiss(suggestion.id)} title="Dismiss"><X size={15} /></button>
                </div>
              </article>
            );
          })
        )}
        </div>
      </div>
    </section>
  );
}
