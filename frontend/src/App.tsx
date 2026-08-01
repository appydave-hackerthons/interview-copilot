import { ChevronDown, CircleStop, MoreHorizontal, Radio, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeInterview, buildReport, fetchHealth, transcribeAudio } from "./api";
import { ActivityPanel } from "./components/ActivityPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { ReportView } from "./components/ReportView";
import { SetupScreen } from "./components/SetupScreen";
import { TranscriptPanel } from "./components/TranscriptPanel";
import { DEFAULT_TEMPLATE, DEMO_LINES } from "./demo";
import type {
  AgentSuggestion,
  EvidenceItem,
  HealthResponse,
  InterviewReport,
  InterviewTemplate,
  Speaker,
  TranscriptTurn,
} from "./types";

type Phase = "setup" | "live" | "report";
type RunMode = "live" | "demo";

const STORAGE_KEY = "interview-copilot-session-v1";

function uniqueById<T extends { id: string }>(previous: T[], incoming: T[]) {
  const map = new Map(previous.map((item) => [item.id, item]));
  incoming.forEach((item) => map.set(item.id, item));
  return [...map.values()];
}

function useElapsed(startedAt: number | null) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const update = () => setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    update();
    const id = window.setInterval(update, 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  return seconds;
}

function formatClock(seconds: number) {
  const hours = Math.floor(seconds / 3600).toString().padStart(2, "0");
  const minutes = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return hours === "00" ? `${minutes}:${remainder}` : `${hours}:${minutes}:${remainder}`;
}

export default function App() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [mode, setMode] = useState<RunMode>("live");
  const [template, setTemplate] = useState<InterviewTemplate>(DEFAULT_TEMPLATE);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [suggestions, setSuggestions] = useState<AgentSuggestion[]>([]);
  const [speaker, setSpeaker] = useState<Speaker>("Participant");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [engine, setEngine] = useState<"openai" | "local" | "idle">("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const elapsed = useElapsed(startedAt);

  const stateRef = useRef({ transcript, evidence, template, mode, elapsed, speaker });
  const recordingRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRecordersRef = useRef(new Set<MediaRecorder>());
  const rotationTimerRef = useRef<number | null>(null);
  const recordingRequestRef = useRef(0);
  const audioTasksRef = useRef(new Set<Promise<void>>());
  const transcriptionJobsRef = useRef(0);
  const analysisJobsRef = useRef(0);
  useEffect(() => {
    stateRef.current = { transcript, evidence, template, mode, elapsed, speaker };
  }, [transcript, evidence, template, mode, elapsed, speaker]);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    try {
      const saved = JSON.parse(stored) as { template?: InterviewTemplate };
      if (saved.template) setTemplate(saved.template);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ template, transcript, evidence }));
  }, [template, transcript, evidence]);

  const processTurn = useCallback(async (turn: TranscriptTurn, overrideMode?: RunMode) => {
    const current = stateRef.current;
    const nextTranscript = [...current.transcript, turn];
    setTranscript(nextTranscript);
    stateRef.current = { ...current, transcript: nextTranscript };
    analysisJobsRef.current += 1;
    setIsAnalyzing(true);
    setNotice(null);
    try {
      const packet = await analyzeInterview({
        transcript: nextTranscript,
        evidence: current.evidence,
        template: current.template,
        focus_evidence_ids: current.evidence.filter((item) => item.promoted).map((item) => item.id),
        mode: overrideMode ?? current.mode,
      });
      setEngine(packet.engine);
      setNotice(packet.notice ?? null);
      setSuggestions(packet.suggestions.map((item) => ({ ...item, createdAt: Date.now() })));
      setEvidence((previous) => {
        const merged = uniqueById(previous, packet.evidence);
        stateRef.current = { ...stateRef.current, evidence: merged };
        return merged;
      });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis could not run.");
    } finally {
      analysisJobsRef.current -= 1;
      if (analysisJobsRef.current === 0) setIsAnalyzing(false);
    }
  }, []);

  async function startLive() {
    setMode("live");
    setPhase("live");
    setTranscript([]);
    setEvidence([]);
    setSuggestions([]);
    setStartedAt(Date.now());
    setReport(null);
    setEngine("idle");
    setNotice(null);
    stateRef.current = { ...stateRef.current, transcript: [], evidence: [], mode: "live", elapsed: 0 };
    await startRecording();
  }

  async function startDemo() {
    setMode("demo");
    setPhase("live");
    setTranscript([]);
    setEvidence([]);
    setSuggestions([]);
    setStartedAt(Date.now());
    setReport(null);
    setEngine("local");
    stateRef.current = { ...stateRef.current, transcript: [], evidence: [], mode: "demo" };
    for (let index = 0; index < DEMO_LINES.length; index += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, index === 0 ? 600 : 1800));
      const line = DEMO_LINES[index];
      await processTurn(
        {
          id: `demo-turn-${index + 1}`,
          speaker: line.speaker,
          text: line.text,
          elapsed_seconds: index * 12,
        },
        "demo",
      );
    }
  }

  function addTypedTurn(text: string) {
    void processTurn({
      id: `turn-${Date.now()}`,
      speaker,
      text,
      elapsed_seconds: elapsed,
    });
  }

  function queueAudioChunk(chunk: Blob) {
    const task = (async () => {
      transcriptionJobsRef.current += 1;
      setIsTranscribing(true);
      try {
        const text = await transcribeAudio(chunk);
        if (text) {
          const current = stateRef.current;
          await processTurn({
            id: `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            speaker: current.speaker,
            text,
            elapsed_seconds: current.elapsed,
          });
        }
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Audio could not be transcribed.");
      } finally {
        transcriptionJobsRef.current -= 1;
        if (transcriptionJobsRef.current === 0) setIsTranscribing(false);
      }
    })();
    audioTasksRef.current.add(task);
    void task.finally(() => audioTasksRef.current.delete(task));
  }

  function startContinuousCapture(stream: MediaStream) {
    if (!recordingRef.current) return;
    const preferred = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"]
      .find((type) => MediaRecorder.isTypeSupported(type));
    const recorder = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined);
    const chunks: BlobPart[] = [];
    const startedAt = Date.now();
    activeRecordersRef.current.add(recorder);
    recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    recorder.onstop = () => {
      activeRecordersRef.current.delete(recorder);
      if (chunks.length && Date.now() - startedAt >= 700) {
        queueAudioChunk(new Blob(chunks, { type: recorder.mimeType }));
      }
    };
    recorder.start();

    rotationTimerRef.current = window.setTimeout(() => {
      if (!recordingRef.current) return;
      // Start the next complete media segment before closing this one. The
      // overlap keeps capture live and gives Whisper a valid container header.
      startContinuousCapture(stream);
      window.setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 200);
    }, 7000);
  }

  async function startRecording() {
    if (recordingRef.current) return;
    const requestId = ++recordingRequestRef.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (requestId !== recordingRequestRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      recordingRef.current = true;
      setIsRecording(true);
      startContinuousCapture(stream);
    } catch {
      setNotice("Microphone access is needed for always-on capture. Grant access, then use the mic button to retry.");
    }
  }

  async function stopRecording() {
    recordingRequestRef.current += 1;
    recordingRef.current = false;
    setIsRecording(false);
    if (rotationTimerRef.current) window.clearTimeout(rotationTimerRef.current);

    const recorders = [...activeRecordersRef.current];
    await Promise.all(recorders.map((recorder) => {
      if (recorder.state !== "recording") return Promise.resolve();
      const stopped = new Promise<void>((resolve) => recorder.addEventListener("stop", () => resolve(), { once: true }));
      recorder.stop();
      return stopped;
    }));
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    activeRecordersRef.current.clear();

    // Include the final partial chunk before synthesizing the report.
    await Promise.resolve();
    await Promise.all([...audioTasksRef.current]);
  }

  function pinSuggestion(suggestion: AgentSuggestion, promote = false) {
    const item: EvidenceItem = {
      id: `pinned-${suggestion.id}`,
      type: suggestion.kind === "question" ? "question" : "insight",
      text: suggestion.text,
      confidence: 0.72,
      pinned: true,
      promoted: promote,
      source: "agent",
      source_turn_ids: [],
      related_evidence_ids: suggestion.evidence_ids,
      agents: [suggestion.agent],
    };
    setEvidence((previous) => {
      const merged = uniqueById(previous, [item]);
      stateRef.current = { ...stateRef.current, evidence: merged };
      return merged;
    });
    setSuggestions((previous) => previous.filter((value) => value.id !== suggestion.id));
  }

  function updateEvidence(item: EvidenceItem) {
    setEvidence((previous) => {
      const next = previous.map((value) => value.id === item.id ? item : value);
      stateRef.current = { ...stateRef.current, evidence: next };
      return next;
    });
  }

  async function endInterview() {
    setIsReporting(true);
    try {
      await stopRecording();
      const current = stateRef.current;
      const result = await buildReport({
        transcript: current.transcript,
        evidence: current.evidence,
        template: current.template,
        mode: current.mode,
      });
      setReport(result);
      setPhase("report");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Report could not be created.");
    } finally {
      setIsReporting(false);
    }
  }

  if (phase === "setup") {
    return <SetupScreen template={template} health={health} onChange={setTemplate} onStart={() => void startLive()} onDemo={() => void startDemo()} />;
  }

  if (phase === "report" && report) {
    return <ReportView report={report} template={template} onBack={() => {
      setPhase("live");
      if (mode === "live") void startRecording();
    }} onNew={() => setPhase("setup")} />;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup compact-brand">
          <span className="brand-mark"><Sparkles size={15} strokeWidth={1.8} /></span>
          <span>Interview Copilot</span>
        </div>
        <div className="interview-title">
          <p>Interviewing</p>
          <button>{template.name} <ChevronDown size={14} /></button>
        </div>
        <div className="header-spacer" />
        {mode === "demo" && <span className="demo-badge">Guided demo</span>}
        <span className={`engine-pill ${engine}`}>
          <i /> {engine === "openai" ? "OpenAI live" : engine === "local" ? "Local mode" : "Ready"}
        </span>
        <div className={`listening-pill ${isRecording ? "active" : ""}`}>
          <Radio size={14} /> {mode === "demo" ? "Demo playback" : isReporting ? "Mic off" : isRecording ? "Listening" : "Mic needs access"}
        </div>
        <time className="session-clock">{formatClock(elapsed)}</time>
        <button className="more-button" aria-label="More options"><MoreHorizontal size={18} /></button>
        <button className="end-button" onClick={() => void endInterview()} disabled={isReporting}>
          <CircleStop size={15} /> {isReporting ? "Building report…" : "End interview"}
        </button>
      </header>

      {notice && <div className="inline-notice"><span>{notice}</span><button onClick={() => setNotice(null)}>Dismiss</button></div>}

      <div className="workspace-grid">
        <TranscriptPanel
          transcript={transcript}
          speaker={speaker}
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          isEnding={isReporting}
          transcriptionAvailable={health?.transcription.available ?? false}
          onSpeakerChange={setSpeaker}
          onSubmit={addTypedTurn}
          onEnableRecording={() => void startRecording()}
        />
        <ActivityPanel
          suggestions={suggestions}
          isAnalyzing={isAnalyzing}
          onPin={pinSuggestion}
          onDismiss={(id) => setSuggestions((previous) => previous.filter((item) => item.id !== id))}
        />
        <EvidencePanel evidence={evidence} onUpdate={updateEvidence} />
      </div>
    </main>
  );
}
