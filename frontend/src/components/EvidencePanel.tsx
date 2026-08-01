import {
  Bookmark,
  ChevronDown,
  ExternalLink,
  FileText,
  HelpCircle,
  Lightbulb,
  Link2,
  Pin,
  Quote,
  Route,
  Star,
  Wrench,
  Zap,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { EvidenceItem, EvidenceType } from "../types";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  onUpdate: (item: EvidenceItem) => void;
}

type Filter = "all" | EvidenceType;

const filters: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "fact", label: "Facts" },
  { value: "pain", label: "Pain" },
  { value: "quote", label: "Quotes" },
  { value: "question", label: "Questions" },
  { value: "insight", label: "Insights" },
];

const typeMeta: Record<EvidenceType, { label: string; icon: typeof FileText }> = {
  fact: { label: "Fact", icon: FileText },
  pain: { label: "Pain point", icon: Zap },
  quote: { label: "Quote", icon: Quote },
  question: { label: "Question", icon: HelpCircle },
  source: { label: "External", icon: ExternalLink },
  insight: { label: "Insight", icon: Lightbulb },
  tool: { label: "Tool", icon: Wrench },
  workflow: { label: "Workflow", icon: Route },
};

export function EvidencePanel({ evidence, onUpdate }: EvidencePanelProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const visible = useMemo(
    () => evidence
      .filter((item) => filter === "all" || item.type === filter)
      .sort((a, b) => Number(b.pinned) - Number(a.pinned) || Number(b.promoted) - Number(a.promoted)),
    [evidence, filter],
  );
  const pinnedCount = evidence.filter((item) => item.pinned).length;

  return (
    <section className="workspace-panel evidence-panel">
      <header className="panel-header evidence-header">
        <div>
          <p className="panel-index">03</p>
          <h2>Evidence</h2>
        </div>
        <span className="panel-count"><Bookmark size={13} /> {pinnedCount} pinned</span>
      </header>
      <div className="evidence-filters" role="tablist" aria-label="Evidence filters">
        {filters.map((item) => (
          <button
            role="tab"
            aria-selected={filter === item.value}
            className={filter === item.value ? "active" : ""}
            key={item.value}
            onClick={() => setFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="evidence-scroll panel-scroll">
        {visible.length === 0 ? (
          <div className="empty-state evidence-empty">
            <Link2 size={25} strokeWidth={1.4} />
            <h3>Evidence will collect here</h3>
            <p>Facts are discovered automatically. Pin the items that should shape the interview.</p>
          </div>
        ) : (
          <>
            {pinnedCount > 0 && filter === "all" && <p className="evidence-section-label">Pinned</p>}
            {visible.map((item, index) => {
              const meta = typeMeta[item.type];
              const Icon = meta.icon;
              const expanded = expandedId === item.id;
              const showDiscoveredLabel = filter === "all" && pinnedCount > 0 && !item.pinned && index > 0 && visible[index - 1]?.pinned;
              return (
                <div key={item.id}>
                  {showDiscoveredLabel && <p className="evidence-section-label discovered">Discovered</p>}
                  <article className={`evidence-card type-${item.type} ${item.pinned ? "pinned" : ""} ${expanded ? "expanded" : ""}`}>
                    <button className="evidence-main" onClick={() => setExpandedId(expanded ? null : item.id)}>
                      <span className="evidence-icon"><Icon size={15} /></span>
                      <span className="evidence-copy">
                        <span className="evidence-type">{meta.label}</span>
                        <span className="evidence-text">{item.type === "quote" ? `“${item.text.replace(/^“|”$/g, "") }”` : item.text}</span>
                      </span>
                      <ChevronDown className="expand-icon" size={16} />
                    </button>
                    <div className="evidence-quick-actions">
                      <button
                        className={item.promoted ? "active" : ""}
                        title="Promote for agent attention"
                        onClick={() => onUpdate({ ...item, promoted: !item.promoted })}
                      ><Star size={14} fill={item.promoted ? "currentColor" : "none"} /></button>
                      <button
                        className={item.pinned ? "active" : ""}
                        title={item.pinned ? "Unpin" : "Pin"}
                        onClick={() => onUpdate({ ...item, pinned: !item.pinned })}
                      ><Pin size={14} fill={item.pinned ? "currentColor" : "none"} /></button>
                    </div>
                    {expanded && (
                      <div className="evidence-details">
                        <div className="confidence-row">
                          <span>Confidence</span>
                          <div className="confidence-track"><i style={{ width: `${Math.round(item.confidence * 100)}%` }} /></div>
                          <strong>{Math.round(item.confidence * 100)}%</strong>
                        </div>
                        <div className="detail-grid">
                          <span>Source</span><strong>{item.source}</strong>
                          <span>Referenced by</span><strong>{item.agents.length ? item.agents.join(", ") : "Evidence extractor"}</strong>
                        </div>
                        {item.related_evidence_ids.length > 0 && (
                          <div className="related-row"><Link2 size={13} /> {item.related_evidence_ids.length} related items</div>
                        )}
                        {item.url && <a href={item.url} target="_blank" rel="noreferrer">Open source <ExternalLink size={12} /></a>}
                      </div>
                    )}
                  </article>
                </div>
              );
            })}
          </>
        )}
      </div>
    </section>
  );
}
