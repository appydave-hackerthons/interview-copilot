import { AudioLines, CornerDownLeft, Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Speaker, TranscriptTurn } from "../types";

interface TranscriptPanelProps {
  transcript: TranscriptTurn[];
  speaker: Speaker;
  isRecording: boolean;
  isTranscribing: boolean;
  isEnding: boolean;
  transcriptionAvailable: boolean;
  onSpeakerChange: (speaker: Speaker) => void;
  onSubmit: (text: string) => void;
  onEnableRecording: () => void;
}

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export function TranscriptPanel(props: TranscriptPanelProps) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [props.transcript]);

  function submit() {
    if (!draft.trim()) return;
    props.onSubmit(draft.trim());
    setDraft("");
  }

  return (
    <section className="workspace-panel transcript-panel">
      <header className="panel-header">
        <div>
          <p className="panel-index">01</p>
          <h2>Transcript</h2>
        </div>
        <span className="panel-count">{props.transcript.length} turns</span>
      </header>

      <div className="transcript-scroll panel-scroll">
        {props.transcript.length === 0 ? (
          <div className="empty-state transcript-empty">
            <AudioLines size={25} strokeWidth={1.4} />
            <h3>The room is quiet</h3>
            <p>{props.isRecording ? "The microphone is on. Start speaking to build evidence." : "Enable the microphone or type the first line to begin building evidence."}</p>
          </div>
        ) : (
          props.transcript.map((turn) => (
            <article className={`transcript-turn ${turn.speaker.toLowerCase()}`} key={turn.id}>
              <div className="turn-meta">
                <span>{turn.speaker}</span>
                <time>{formatElapsed(turn.elapsed_seconds)}</time>
              </div>
              <p>{turn.text}</p>
            </article>
          ))
        )}
        {props.isTranscribing && (
          <div className="transcribing-row"><span className="typing-dots"><i /><i /><i /></span> Transcribing locally</div>
        )}
        <div ref={endRef} />
      </div>

      <footer className="transcript-composer">
        <div className="speaker-toggle" aria-label="Current speaker">
          {(["Interviewer", "Participant"] as Speaker[]).map((value) => (
            <button
              className={props.speaker === value ? "active" : ""}
              key={value}
              onClick={() => props.onSpeakerChange(value)}
            >
              {value}
            </button>
          ))}
          <span className={`mic-status ${props.isRecording ? "active" : ""}`}>
            <i /> {props.isRecording ? "Mic always on" : props.isEnding ? "Mic off" : "Mic needs access"}
          </span>
        </div>
        <div className="composer-row">
          <textarea
            aria-label="Add transcript line"
            placeholder={`Add what the ${props.speaker.toLowerCase()} said…`}
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <button className="composer-submit" aria-label="Add transcript line" onClick={submit}>
            <CornerDownLeft size={17} />
          </button>
          <button
            className={`mic-button ${props.isRecording ? "recording" : ""}`}
            aria-label={props.isRecording ? "Microphone always on" : props.isEnding ? "Microphone off" : "Enable microphone"}
            onClick={props.isRecording || props.isEnding ? undefined : props.onEnableRecording}
            disabled={props.isRecording || props.isEnding || !props.transcriptionAvailable}
            title={props.isRecording ? "Microphone stays on until the interview ends" : props.isEnding ? "Interview ended" : props.transcriptionAvailable ? "Enable always-on microphone" : "Local Whisper unavailable"}
          >
            <Mic size={18} />
          </button>
        </div>
      </footer>
    </section>
  );
}
