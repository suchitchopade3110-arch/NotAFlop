"use client";

import { useCallback, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { transcribeAudio } from "@/lib/api/routes";
import { describeError } from "@/lib/utils/error-message";
import { cn } from "@/lib/utils/cn";

const MAX_LENGTH = 5000; // mirrors core.config.TRANSCRIPT_MAX_LENGTH exactly
const MAX_AUDIO_BYTES = 10 * 1024 * 1024; // mirrors core.config.AUDIO_MAX_BYTES

type Mode = "type" | "record" | "upload";

interface PitchFormProps {
  initialValue?: string;
  onSubmit: (transcript: string, inputMode: "text" | "audio" | "video") => void;
  submitting?: boolean;
  submitLabel?: string;
}

export function PitchForm({ initialValue = "", onSubmit, submitting, submitLabel = "Validate my idea" }: PitchFormProps) {
  const [mode, setMode] = useState<Mode>("type");
  const [text, setText] = useState(initialValue);
  const [transcribing, setTranscribing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [lastInputMode, setLastInputMode] = useState<"text" | "audio" | "video">("text");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const trimmed = text.trim();
  const overLimit = text.length > MAX_LENGTH;
  const canSubmit = trimmed.length >= 20 && !overLimit && !submitting && !transcribing && !recording;

  const runTranscription = useCallback(async (file: File, kind: "audio" | "video") => {
    if (file.size > MAX_AUDIO_BYTES) {
      setMediaError("That file is over the 10 MB limit. Trim it down and try again.");
      return;
    }
    setMediaError(null);
    setTranscribing(true);
    try {
      const res = await transcribeAudio(file);
      setText(res.transcript);
      setLastInputMode(kind);
      setMode("type");
    } catch (err) {
      setMediaError(describeError(err).description);
    } finally {
      setTranscribing(false);
    }
  }, []);

  const startRecording = useCallback(async () => {
    setMediaError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        void runTranscription(new File([blob], "pitch.webm", { type: "audio/webm" }), "audio");
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setMediaError("Couldn't access your microphone. Check your browser permissions, or type your pitch instead.");
    }
  }, [runTranscription]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      const kind = file.type.startsWith("video/") ? "video" : "audio";
      void runTranscription(file, kind);
    },
    [runTranscription],
  );

  return (
    <div className="w-full">
      <div className="mb-3 flex gap-1 rounded-lg border border-border bg-charcoal p-1" role="tablist" aria-label="Pitch input method">
        {(
          [
            { id: "type", label: "Type" },
            { id: "record", label: "Record" },
            { id: "upload", label: "Upload" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={mode === tab.id}
            onClick={() => setMode(tab.id)}
            className={cn(
              "flex-1 rounded-md px-3 py-2 text-body font-medium transition-colors",
              mode === tab.id ? "bg-charcoal-raised text-gold-bright" : "text-ink-faint hover:text-ink-muted",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {mode === "record" && (
        <div className="mb-3 flex items-center gap-3 rounded-xl border border-border bg-charcoal px-4 py-4">
          <Button
            type="button"
            variant={recording ? "danger" : "secondary"}
            size="sm"
            onClick={recording ? stopRecording : startRecording}
            disabled={transcribing}
          >
            {recording ? "Stop recording" : "Start recording"}
          </Button>
          <p className="text-body text-ink-muted" aria-live="polite">
            {recording ? "Recording. Speak your pitch, then stop." : transcribing ? "Transcribing..." : "Say your pitch out loud."}
          </p>
        </div>
      )}

      {mode === "upload" && (
        <div className="mb-3 rounded-xl border border-dashed border-border bg-charcoal px-4 py-6 text-center">
          <label className="cursor-pointer">
            <span className="text-body text-gold-bright underline underline-offset-4">Choose an audio or video file</span>
            <input
              type="file"
              accept="audio/*,video/*"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
                e.target.value = "";
              }}
            />
          </label>
          <p className="mt-2 text-body text-ink-faint">Up to 10 MB. {transcribing ? "Transcribing..." : ""}</p>
        </div>
      )}

      {mediaError && <p className="mb-3 text-body text-nogo">{mediaError}</p>}

      <Textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setLastInputMode("text");
        }}
        placeholder="We're building [product] for [who], to help them [job to be done]. Today they [current workaround], which costs them [pain]..."
        rows={7}
        maxLength={MAX_LENGTH}
        showCount
        error={overLimit ? `Keep it under ${MAX_LENGTH.toLocaleString()} characters.` : null}
        aria-label="Your pitch"
        disabled={transcribing || recording}
      />

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-body text-ink-faint">
          {trimmed.length > 0 && trimmed.length < 20 ? "A few more words gives the agents something to work with." : "Free. No account needed."}
        </p>
        <Button
          type="button"
          size="lg"
          disabled={!canSubmit}
          loading={submitting}
          onClick={() => onSubmit(trimmed, lastInputMode)}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}
