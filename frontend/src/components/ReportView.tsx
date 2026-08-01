import { ArrowLeft, Check, Clipboard, Download, ExternalLink, Lightbulb, Quote, Sparkles, Target } from "lucide-react";
import { useState } from "react";
import type { InterviewTemplate, PersistentInterviewReport } from "../types";

interface ReportViewProps {
  report: PersistentInterviewReport;
  template: InterviewTemplate;
  onBack: () => void;
  onNew: () => void;
}

function reportMarkdown(report: PersistentInterviewReport, template: InterviewTemplate) {
  const list = (items: string[]) => items.map((item) => `- ${item}`).join("\n") || "- None captured";
  return `# ${template.name} — interview report

${report.summary}

## Top pain points
${list(report.top_pains)}

## Key facts
${list(report.key_facts)}

## Important quotes
${list(report.quotes.map((quote) => `“${quote}”`))}

## Unanswered questions
${list(report.unanswered_questions)}

## Opportunity hypothesis
${report.opportunity}

## Least-effort next step
${report.next_step}
`;
}

export function ReportView({ report, template, onBack, onNew }: ReportViewProps) {
  const [copied, setCopied] = useState(false);
  const markdown = reportMarkdown(report, template);

  function download() {
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${template.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-report.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copy() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <main className="report-shell">
      <nav className="report-nav">
        <button className="text-button" onClick={onBack}><ArrowLeft size={15} /> Back to interview</button>
        <div className="report-nav-actions">
          <a className="button button-secondary compact" href={report.html_url} target="_blank" rel="noreferrer">
            <ExternalLink size={15} /> Full HTML
          </a>
          <button className="button button-secondary compact" onClick={copy}>
            {copied ? <Check size={15} /> : <Clipboard size={15} />} {copied ? "Copied" : "Copy Markdown"}
          </button>
          <button className="button button-secondary compact" onClick={download}><Download size={15} /> Export</button>
          <button className="button button-primary compact" onClick={onNew}>New interview</button>
        </div>
      </nav>

      <section className="report-hero">
        <div>
          <p className="eyebrow">Interview synthesis · Report {String(report.report_id).padStart(3, "0")} · Saved</p>
          <h1>{template.name}</h1>
          <p>{report.summary}</p>
          <span className={`engine-badge ${report.engine}`}>{report.engine === "openai" ? "OpenAI synthesis" : "Local synthesis"}</span>
        </div>
        <div className="score-card">
          <div className="score-ring" style={{ "--score": `${report.score * 3.6}deg` } as React.CSSProperties}>
            <strong>{report.score}</strong><span>/ 100</span>
          </div>
          <div><strong>Interview completeness</strong><span>{report.coverage.filter((item) => item.complete).length} of {report.coverage.length} criteria covered</span></div>
        </div>
      </section>

      {report.notice && <div className="report-notice">{report.notice}</div>}

      <section className="report-grid">
        <article className="report-section report-pains">
          <header><span><Target size={16} /></span><div><p>What matters</p><h2>Top pain points</h2></div></header>
          <ol>{report.top_pains.map((item) => <li key={item}><span>{String(report.top_pains.indexOf(item) + 1).padStart(2, "0")}</span>{item}</li>)}</ol>
        </article>
        <article className="report-section">
          <header><span><Sparkles size={16} /></span><div><p>What we learned</p><h2>Key facts</h2></div></header>
          <ul className="check-list">{report.key_facts.map((item) => <li key={item}><Check size={14} />{item}</li>)}</ul>
        </article>
        <article className="report-section report-quotes">
          <header><span><Quote size={16} /></span><div><p>In their words</p><h2>Important quotes</h2></div></header>
          <div>{report.quotes.map((item) => <blockquote key={item}>“{item.replace(/^“|”$/g, "")}”</blockquote>)}</div>
        </article>
        <article className="report-section">
          <header><span>?</span><div><p>What is missing</p><h2>Unanswered questions</h2></div></header>
          <ul className="question-list">{report.unanswered_questions.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
      </section>

      <section className="decision-row">
        <article className="decision-card opportunity-decision">
          <p><Lightbulb size={15} /> Opportunity hypothesis</p>
          <h2>{report.opportunity}</h2>
          <span>Inference — validate before treating as fact</span>
        </article>
        <article className="decision-card next-step-decision">
          <p><Target size={15} /> Least-effort next step</p>
          <h2>{report.next_step}</h2>
          <span>One useful test, not a roadmap</span>
        </article>
      </section>

      <section className="coverage-strip">
        <p>Coverage</p>
        {report.coverage.map((item) => (
          <div className={item.complete ? "complete" : ""} key={item.label}>
            <span>{item.complete ? <Check size={12} /> : "—"}</span>{item.label}
          </div>
        ))}
      </section>
    </main>
  );
}
