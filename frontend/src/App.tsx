import { ChevronDown, CircleStop, MoreHorizontal, Radio, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  analyzeInterview,
  buildReport,
  fetchDefaultConfiguration,
  fetchHealth,
  researchInterview,
  startInterviewSession,
  transcribeAudio,
  validateConfiguration,
} from "./api";
import { ActivityPanel } from "./components/ActivityPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { ReportView } from "./components/ReportView";
import { SetupScreen } from "./components/SetupScreen";
import { TranscriptPanel } from "./components/TranscriptPanel";
import { cloneConfiguration, parseDemoScript } from "./config";
import { DEMO_LINES } from "./demo";
import { keepActiveGuidanceCards, mergeGuidanceCards } from "./guidance";
import { researchCardToEvidence } from "./research";
import {
  DEFAULT_TEMPLATE_ID,
  migrateStoredTemplateSelection,
  presetForId,
  TEMPLATE_LIBRARY,
} from "./templates";
import type {
  AgentSuggestion,
  EvidenceItem,
  HealthResponse,
  InterviewConfiguration,
  PersistentInterviewReport,
  ResearchCard,
  Speaker,
  TranscriptTurn,
} from "./types";

type Phase = "setup" | "live" | "report";
type RunMode = "live" | "demo";

const STORAGE_KEY = "interview-copilot-session-v1";

function newSessionId() {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `interview-${timestamp}-${crypto.randomUUID().slice(0, 8)}`;
}

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
  const [configuration, setConfiguration] = useState<InterviewConfiguration | null>(null);
  const [defaultConfiguration, setDefaultConfiguration] = useState<InterviewConfiguration | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(DEFAULT_TEMPLATE_ID);
  const [configurationValidation, setConfigurationValidation] = useState<{
    state: "checking" | "valid" | "invalid";
    message?: string;
  }>({ state: "checking" });
  const [isStarting, setIsStarting] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [suggestions, setSuggestions] = useState<AgentSuggestion[]>([]);
  const [researchCards, setResearchCards] = useState<ResearchCard[]>([]);
  const [speaker, setSpeaker] = useState<Speaker>("Participant");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [engine, setEngine] = useState<"openai" | "local" | "idle">("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [report, setReport] = useState<PersistentInterviewReport | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const elapsed = useElapsed(startedAt);

  const stateRef = useRef<{
    transcript: TranscriptTurn[];
    evidence: EvidenceItem[];
    configuration: InterviewConfiguration | null;
    mode: RunMode;
    elapsed: number;
    speaker: Speaker;
  }>({ transcript, evidence, configuration: null, mode, elapsed, speaker });
  const activeConfigurationRef = useRef<InterviewConfiguration | null>(null);
  const activeTemplateIdRef = useRef<string | null>(DEFAULT_TEMPLATE_ID);
  const recordingRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRecordersRef = useRef(new Set<MediaRecorder>());
  const rotationTimerRef = useRef<number | null>(null);
  const recordingRequestRef = useRef(0);
  const sessionIdRef = useRef(newSessionId());
  const audioSequenceRef = useRef(0);
  const audioTasksRef = useRef(new Set<Promise<void>>());
  const transcriptionJobsRef = useRef(0);
  const analysisJobsRef = useRef(0);
  const researchRevisionRef = useRef(0);
  const researchAbortRef = useRef<AbortController | null>(null);
  const researchTimerRef = useRef<number | null>(null);
  useEffect(() => {
    stateRef.current = {
      transcript,
      evidence,
      configuration: phase === "setup" ? configuration : activeConfigurationRef.current ?? configuration,
      mode,
      elapsed,
      speaker,
    };
  }, [transcript, evidence, configuration, phase, mode, elapsed, speaker]);

  useEffect(() => () => {
    if (researchTimerRef.current) window.clearTimeout(researchTimerRef.current);
    researchAbortRef.current?.abort();
  }, []);

  useEffect(() => {
    if (phase !== "live") return;
    const removeExpiredCards = () => {
      const now = Date.now();
      setSuggestions((previous) => keepActiveGuidanceCards(previous, now));
      setResearchCards((previous) => keepActiveGuidanceCards(previous, now));
    };
    removeExpiredCards();
    const timer = window.setInterval(removeExpiredCards, 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    void fetchHealth().then(setHealth).catch(() => setHealth(null));
    let savedValue: unknown;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        savedValue = JSON.parse(stored);
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
    const migrated = migrateStoredTemplateSelection(savedValue);
    setSelectedTemplateId(migrated.selectedTemplateId);

    void fetchDefaultConfiguration()
      .then(async (preset) => {
        const canonicalDefault = {
          ...preset,
          template: structuredClone(TEMPLATE_LIBRARY[0].template),
        };
        setDefaultConfiguration(canonicalDefault);
        let candidate: unknown = { ...canonicalDefault, template: migrated.template };
        try {
          if (savedValue && typeof savedValue === "object" && !Array.isArray(savedValue)) {
            const savedConfiguration = (savedValue as Record<string, unknown>).configuration;
            if (savedConfiguration && typeof savedConfiguration === "object" && !Array.isArray(savedConfiguration)) {
              candidate = { ...savedConfiguration, template: migrated.template };
            }
          }
          const restored = await validateConfiguration(candidate);
          setConfiguration(restored);
          setConfigurationValidation({ state: "valid" });
        } catch {
          const restored = await validateConfiguration({ ...canonicalDefault, template: migrated.template });
          setConfiguration(restored);
          setConfigurationValidation({ state: "valid" });
        }
      })
      .catch((error: unknown) => {
        setConfigurationValidation({
          state: "invalid",
          message: error instanceof Error ? error.message : "The default preset could not be loaded.",
        });
      });
  }, []);

  useEffect(() => {
    if (!configuration) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      schema_version: 2,
      selected_template_id: selectedTemplateId,
      custom_template: selectedTemplateId === null ? configuration.template : undefined,
      configuration,
      transcript,
      evidence,
    }));
  }, [configuration, selectedTemplateId, transcript, evidence]);

  useEffect(() => {
    if (!configuration) return;
    let active = true;
    setConfigurationValidation({ state: "checking" });
    const timer = window.setTimeout(() => {
      void validateConfiguration(configuration)
        .then(() => active && setConfigurationValidation({ state: "valid" }))
        .catch((error: unknown) => active && setConfigurationValidation({
          state: "invalid",
          message: error instanceof Error ? error.message.split("\n")[0] : "Invalid configuration",
        }));
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [configuration]);

  function selectTemplate(id: string) {
    const preset = presetForId(id);
    if (!preset) return;
    setSelectedTemplateId(preset.id);
    setConfiguration((current) => current
      ? { ...current, template: structuredClone(preset.template) }
      : current);
  }

  function updateTemplate(template: InterviewConfiguration["template"]) {
    setSelectedTemplateId(null);
    setConfiguration((current) => current ? { ...current, template } : current);
  }

  function updateConfiguration(next: InterviewConfiguration) {
    const selected = presetForId(selectedTemplateId);
    if (selected && JSON.stringify(next.template) !== JSON.stringify(selected.template)) {
      setSelectedTemplateId(null);
    }
    setConfiguration(next);
  }

  const queueResearch = useCallback((
    nextTranscript: TranscriptTurn[],
    nextEvidence: EvidenceItem[],
    nextConfiguration: InterviewConfiguration,
    nextMode: RunMode,
  ) => {
    if (!nextTranscript.length || !nextConfiguration.copilot.lenses.research) {
      researchAbortRef.current?.abort();
      setResearchCards([]);
      setIsResearching(false);
      return;
    }
    const revision = ++researchRevisionRef.current;
    if (researchTimerRef.current) window.clearTimeout(researchTimerRef.current);
    researchAbortRef.current?.abort();
    researchTimerRef.current = window.setTimeout(() => {
      const controller = new AbortController();
      researchAbortRef.current = controller;
      setIsResearching(true);
      void researchInterview({
        session_id: sessionIdRef.current,
        revision,
        transcript: nextTranscript,
        evidence: nextEvidence,
        configuration: nextConfiguration,
        mode: nextMode,
      }, controller.signal)
        .then((packet) => {
          if (packet.revision === researchRevisionRef.current && !packet.stale) {
            setResearchCards((previous) => mergeGuidanceCards(previous, packet.cards));
          }
        })
        .catch(() => {
          // Research is silent and optional by design.
        })
        .finally(() => {
          if (revision === researchRevisionRef.current) setIsResearching(false);
        });
    }, nextMode === "demo" ? 220 : 1100);
  }, []);

  const processTurn = useCallback(async (turn: TranscriptTurn, overrideMode?: RunMode) => {
    const current = stateRef.current;
    if (!current.configuration) return;
    const nextTranscript = [...current.transcript, turn];
    setTranscript(nextTranscript);
    stateRef.current = { ...current, transcript: nextTranscript };
    const requestMode = overrideMode ?? current.mode;
    queueResearch(nextTranscript, current.evidence, current.configuration, requestMode);
    analysisJobsRef.current += 1;
    setIsAnalyzing(true);
    setNotice(null);
    try {
      const packet = await analyzeInterview({
        transcript: nextTranscript,
        evidence: current.evidence,
        configuration: current.configuration,
        focus_evidence_ids: current.evidence.filter((item) => item.promoted).map((item) => item.id),
        mode: requestMode,
      });
      setEngine(packet.engine);
      setNotice(packet.notice ?? null);
      setSuggestions((previous) => mergeGuidanceCards(previous, packet.suggestions));
      setEvidence((previous) => {
        const merged = uniqueById(previous, packet.evidence);
        stateRef.current = { ...stateRef.current, evidence: merged };
        return merged;
      });
      if (stateRef.current.transcript.at(-1)?.id === turn.id) {
        queueResearch(
          nextTranscript,
          uniqueById(stateRef.current.evidence, packet.evidence),
          current.configuration,
          requestMode,
        );
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis could not run.");
    } finally {
      analysisJobsRef.current -= 1;
      if (analysisJobsRef.current === 0) setIsAnalyzing(false);
    }
  }, [queueResearch]);

  async function prepareInterview(nextMode: RunMode) {
    if (!configuration || isStarting) return null;
    setIsStarting(true);
    setNotice(null);
    try {
      const frozen = await validateConfiguration(cloneConfiguration(configuration));
      if (nextMode === "demo") parseDemoScript(frozen.developer.demo_script);
      const sessionId = newSessionId();
      await startInterviewSession({ session_id: sessionId, configuration: frozen, mode: nextMode });
      activeConfigurationRef.current = cloneConfiguration(frozen);
      activeTemplateIdRef.current = selectedTemplateId;
      sessionIdRef.current = sessionId;
      audioSequenceRef.current = 0;
      setSpeaker(frozen.audio.default_speaker);
      setMode(nextMode);
      setPhase("live");
      setTranscript([]);
      setEvidence([]);
      setSuggestions([]);
      setResearchCards([]);
      if (researchTimerRef.current) window.clearTimeout(researchTimerRef.current);
      researchAbortRef.current?.abort();
      researchAbortRef.current = null;
      researchRevisionRef.current = 0;
      setIsResearching(false);
      setStartedAt(Date.now());
      setReport(null);
      setEngine(nextMode === "demo" ? "local" : "idle");
      stateRef.current = {
        transcript: [],
        evidence: [],
        configuration: cloneConfiguration(frozen),
        mode: nextMode,
        elapsed: 0,
        speaker: frozen.audio.default_speaker,
      };
      return frozen;
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The interview archive could not be prepared.");
      return null;
    } finally {
      setIsStarting(false);
    }
  }

  async function startLive() {
    const frozen = await prepareInterview("live");
    if (!frozen) return;
    await startRecording();
  }

  async function startDemo() {
    const frozen = await prepareInterview("demo");
    if (!frozen) return;
    const lines = parseDemoScript(frozen.developer.demo_script) ?? DEMO_LINES;
    for (let index = 0; index < lines.length; index += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, index === 0 ? 600 : 1800));
      const line = lines[index];
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
    const current = stateRef.current;
    const metadata = {
      sessionId: sessionIdRef.current,
      sequence: ++audioSequenceRef.current,
      speaker: current.speaker,
      elapsedSeconds: current.elapsed,
    };
    const task = (async () => {
      transcriptionJobsRef.current += 1;
      setIsTranscribing(true);
      try {
        const text = await transcribeAudio(chunk, metadata);
        if (text) {
          await processTurn({
            id: `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            speaker: metadata.speaker,
            text,
            elapsed_seconds: metadata.elapsedSeconds,
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

    const audio = activeConfigurationRef.current?.audio;
    rotationTimerRef.current = window.setTimeout(() => {
      if (!recordingRef.current) return;
      // Start the next complete media segment before closing this one. The
      // overlap keeps capture live and gives Whisper a valid container header.
      startContinuousCapture(stream);
      window.setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, audio?.overlap_ms ?? 200);
    }, audio?.segment_ms ?? 7000);
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

  function toggleSuggestionPin(suggestion: AgentSuggestion) {
    setSuggestions((previous) => previous.map((item) => (
      item.id === suggestion.id
        ? { ...item, pinned: !item.pinned, createdAt: item.pinned ? Date.now() : item.createdAt }
        : item
    )));
  }

  function promoteSuggestion(suggestion: AgentSuggestion) {
    const item: EvidenceItem = {
      id: `pinned-${suggestion.id}`,
      type: suggestion.kind === "question" ? "question" : "insight",
      text: suggestion.text,
      confidence: 0.72,
      pinned: true,
      promoted: true,
      source: "agent",
      source_turn_ids: [],
      related_evidence_ids: suggestion.evidence_ids,
      agents: [suggestion.agent],
    };
    setEvidence((previous) => {
      const merged = uniqueById(previous, [item]);
      stateRef.current = { ...stateRef.current, evidence: merged };
      if (stateRef.current.configuration) {
        queueResearch(stateRef.current.transcript, merged, stateRef.current.configuration, stateRef.current.mode);
      }
      return merged;
    });
    setSuggestions((previous) => previous.filter((value) => value.id !== suggestion.id));
  }

  function updateEvidence(item: EvidenceItem) {
    setEvidence((previous) => {
      const next = previous.map((value) => value.id === item.id ? item : value);
      stateRef.current = { ...stateRef.current, evidence: next };
      if (stateRef.current.configuration) {
        queueResearch(stateRef.current.transcript, next, stateRef.current.configuration, stateRef.current.mode);
      }
      return next;
    });
  }

  function toggleResearchPin(card: ResearchCard) {
    setResearchCards((previous) => previous.map((item) => (
      item.id === card.id
        ? { ...item, pinned: !item.pinned, createdAt: item.pinned ? Date.now() : item.createdAt }
        : item
    )));
  }

  function promoteResearch(card: ResearchCard) {
    const sourceTurn = [...stateRef.current.transcript]
      .reverse()
      .find((turn) => turn.text.trim() === card.why_now.trim());
    const item = researchCardToEvidence(card, true, sourceTurn ? [sourceTurn.id] : []);
    setEvidence((previous) => {
      const merged = uniqueById(previous, [item]);
      stateRef.current = { ...stateRef.current, evidence: merged };
      return merged;
    });
    setResearchCards((previous) => previous.filter((value) => value.id !== card.id));
  }

  async function endInterview() {
    setIsReporting(true);
    try {
      if (researchTimerRef.current) window.clearTimeout(researchTimerRef.current);
      researchAbortRef.current?.abort();
      setIsResearching(false);
      await stopRecording();
      const current = stateRef.current;
      if (!current.configuration) throw new Error("The active configuration is unavailable.");
      const result = await buildReport({
        session_id: sessionIdRef.current,
        transcript: current.transcript,
        evidence: current.evidence,
        configuration: current.configuration,
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

  if (!configuration || !defaultConfiguration) {
    return <main className="setup-loading"><Sparkles size={18} /><span>{configurationValidation.message ?? "Loading canonical preset…"}</span></main>;
  }

  const effectiveConfiguration = phase === "setup"
    ? configuration
    : activeConfigurationRef.current ?? configuration;
  const template = effectiveConfiguration.template;
  const effectiveTemplateId = phase === "setup" ? selectedTemplateId : activeTemplateIdRef.current;
  const starterQuestions = presetForId(effectiveTemplateId)?.starter_questions;

  if (phase === "setup") {
    return <>
      {notice && <div className="inline-notice setup-notice"><span>{notice}</span><button onClick={() => setNotice(null)}>Dismiss</button></div>}
      <SetupScreen
        configuration={configuration}
        defaultConfiguration={defaultConfiguration}
        presets={TEMPLATE_LIBRARY}
        selectedTemplateId={selectedTemplateId}
        health={health}
        validation={configurationValidation}
        isStarting={isStarting}
        onChange={updateConfiguration}
        onTemplateChange={updateTemplate}
        onSelectTemplate={selectTemplate}
        onStart={() => void startLive()}
        onDemo={() => void startDemo()}
      />
    </>;
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
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          isEnding={isReporting}
          transcriptionAvailable={health?.transcription.available ?? false}
          onSubmit={addTypedTurn}
          onEnableRecording={() => void startRecording()}
        />
        <ActivityPanel
          suggestions={suggestions}
          researchCards={researchCards}
          template={template}
          starterQuestions={starterQuestions}
          isAnalyzing={isAnalyzing}
          isResearching={isResearching}
          onTogglePin={toggleSuggestionPin}
          onPromote={promoteSuggestion}
          onDismiss={(id) => setSuggestions((previous) => previous.filter((item) => item.id !== id))}
          onToggleResearchPin={toggleResearchPin}
          onPromoteResearch={promoteResearch}
          onDismissResearch={(id) => setResearchCards((previous) => previous.filter((item) => item.id !== id))}
        />
        <EvidencePanel evidence={evidence} onUpdate={updateEvidence} />
      </div>
    </main>
  );
}
