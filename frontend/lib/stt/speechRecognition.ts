"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { resolveSpeechLocale } from "@/lib/tts/language";

export type SpeechRecognitionStatus =
  | "ready"
  | "listening"
  | "processing"
  | "captured"
  | "submitted"
  | "retry_required"
  | "unsupported";

export type SpeechRecognitionErrorCode =
  | "unsupported_browser"
  | "unsupported_language"
  | "permission_denied"
  | "microphone_unavailable"
  | "no_speech_detected"
  | "aborted"
  | "network_failure"
  | "service_failure";

type BrowserSpeechRecognitionAlternative = {
  transcript: string;
  confidence?: number;
};

type BrowserSpeechRecognitionResult = {
  isFinal?: boolean;
  length: number;
  [index: number]: BrowserSpeechRecognitionAlternative;
};

type BrowserSpeechRecognitionResultList = ArrayLike<BrowserSpeechRecognitionResult>;

type BrowserSpeechRecognitionEvent = {
  results: BrowserSpeechRecognitionResultList;
  resultIndex?: number;
};

type BrowserSpeechRecognitionErrorEvent = {
  error: string;
  message?: string;
};

type BrowserSpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: ((event: Event) => void) | null;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onend: ((event: Event) => void) | null;
};

type BrowserSpeechRecognitionConstructor = {
  new (): BrowserSpeechRecognitionInstance;
};

declare global {
  interface Window {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  }
}

type SpeechRecognitionState = {
  status: SpeechRecognitionStatus;
  supported: boolean;
  language: string | null;
  errorCode: SpeechRecognitionErrorCode | null;
  transcript: string;
};

const DEFAULT_STATE: SpeechRecognitionState = {
  status: "unsupported",
  supported: false,
  language: null,
  errorCode: null,
  transcript: "",
};

let activeSessionId = 0;

function getRecognitionConstructor(): BrowserSpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function isSupported() {
  return getRecognitionConstructor() !== null;
}

function isRecognizedLanguageSupported(language?: string | null) {
  const normalized = (language || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  if (normalized.startsWith("en")) {
    return true;
  }
  if (normalized.startsWith("hi")) {
    return true;
  }
  if (normalized.startsWith("ta")) {
    return true;
  }
  if (normalized.startsWith("te")) {
    return true;
  }
  if (normalized.startsWith("kn")) {
    return true;
  }

  switch (normalized) {
    case "english":
    case "hindi":
    case "tamil":
    case "telugu":
    case "kannada":
      return true;
    default:
      return false;
  }
}

function normalizeCapturedText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

function mapRecognitionError(error: string): SpeechRecognitionErrorCode {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "permission_denied";
    case "audio-capture":
    case "not-found":
      return "microphone_unavailable";
    case "no-speech":
      return "no_speech_detected";
    case "aborted":
      return "aborted";
    case "network":
      return "network_failure";
    case "language-not-supported":
      return "unsupported_language";
    default:
      return "service_failure";
  }
}

function extractFinalTranscript(results: BrowserSpeechRecognitionResultList, resultIndex = 0) {
  const parts: string[] = [];
  for (let index = resultIndex; index < results.length; index += 1) {
    const result = results[index];
    if (!result || result.isFinal === false || !result.length) {
      continue;
    }
    const alternative = result[0];
    const transcript = normalizeCapturedText(alternative?.transcript || "");
    if (transcript) {
      parts.push(transcript);
    }
  }
  return normalizeCapturedText(parts.join(" "));
}

export function useSpeechRecognition() {
  const recognitionRef = useRef<BrowserSpeechRecognitionInstance | null>(null);
  const stopReasonRef = useRef<"manual" | "retry" | "submit" | "reset" | "unmount" | null>(null);

  const [state, setState] = useState<SpeechRecognitionState>(() => ({
    ...DEFAULT_STATE,
    supported: isSupported(),
    status: isSupported() ? "ready" : "unsupported",
  }));

  const clearRecognition = useCallback((reason: "manual" | "retry" | "submit" | "reset" | "unmount") => {
    stopReasonRef.current = reason;
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      try {
        recognition.onstart = null;
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        recognition.abort();
      } catch {
        // Ignore cleanup errors.
      }
    }
    if (reason !== "submit") {
      activeSessionId += 1;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearRecognition("unmount");
    };
  }, [clearRecognition]);

  const retry = useCallback(() => {
    clearRecognition("retry");
    setState((current) => ({
      ...current,
      status: current.supported ? "ready" : "unsupported",
      errorCode: null,
      transcript: "",
      language: null,
    }));
  }, [clearRecognition]);

  const markSubmitted = useCallback(() => {
    setState((current) => ({
      ...current,
      status: "submitted",
      errorCode: null,
    }));
    clearRecognition("submit");
  }, [clearRecognition]);

  const stop = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) {
      return false;
    }

    stopReasonRef.current = "manual";
    setState((current) => ({
      ...current,
      status: "processing",
    }));

    try {
      recognition.stop();
      return true;
    } catch {
      setState((current) => ({
        ...current,
        status: "retry_required",
        errorCode: "service_failure",
      }));
      return false;
    }
  }, []);

  const start = useCallback(
    (language?: string | null) => {
      const Recognition = getRecognitionConstructor();
      if (!Recognition) {
        setState({
          status: "unsupported",
          supported: false,
          language: null,
          errorCode: "unsupported_browser",
          transcript: "",
        });
        return false;
      }

      if (!isRecognizedLanguageSupported(language)) {
        setState({
          status: "retry_required",
          supported: true,
          language: resolveSpeechLocale(language),
          errorCode: "unsupported_language",
          transcript: "",
        });
        return false;
      }

      clearRecognition("manual");
      const recognition = new Recognition();
      const sessionId = activeSessionId + 1;
      activeSessionId = sessionId;
      recognitionRef.current = recognition;

      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.lang = resolveSpeechLocale(language);

      setState({
        status: "ready",
        supported: true,
        language: recognition.lang,
        errorCode: null,
        transcript: "",
      });

      recognition.onstart = () => {
        if (sessionId !== activeSessionId) {
          return;
        }
        setState((current) => ({
          ...current,
          status: "listening",
          errorCode: null,
          language: recognition.lang,
          transcript: "",
        }));
      };

      recognition.onresult = (event) => {
        if (sessionId !== activeSessionId) {
          return;
        }
        const transcript = extractFinalTranscript(event.results, event.resultIndex || 0);
        if (!transcript) {
          setState((current) => ({
            ...current,
            status: "retry_required",
            errorCode: "no_speech_detected",
            transcript: "",
          }));
          return;
        }
        setState((current) => ({
          ...current,
          status: "captured",
          errorCode: null,
          transcript,
        }));
      };

      recognition.onerror = (event) => {
        if (sessionId !== activeSessionId) {
          return;
        }
        setState((current) => ({
          ...current,
          status: "retry_required",
          errorCode: mapRecognitionError(event.error),
        }));
      };

      recognition.onend = () => {
        if (sessionId !== activeSessionId) {
          return;
        }
        recognitionRef.current = null;
        if (stopReasonRef.current === "submit") {
          return;
        }
        if (stopReasonRef.current === "retry" || stopReasonRef.current === "reset" || stopReasonRef.current === "unmount") {
          return;
        }
        setState((current) => ({
          ...current,
          status: current.transcript ? "captured" : "retry_required",
          errorCode: current.transcript ? null : current.errorCode || "no_speech_detected",
        }));
      };

      try {
        recognition.start();
        return true;
      } catch {
        setState({
          status: "retry_required",
          supported: true,
          language: recognition.lang,
          errorCode: "service_failure",
          transcript: "",
        });
        return false;
      }
    },
    [clearRecognition],
  );

  const reset = useCallback(() => {
    clearRecognition("reset");
    setState((current) => ({
      ...current,
      status: current.supported ? "ready" : "unsupported",
      errorCode: null,
      transcript: "",
      language: current.language,
    }));
  }, [clearRecognition]);

  const recognizedText = useMemo(() => state.transcript, [state.transcript]);

  return {
    status: state.status,
    supported: state.supported,
    language: state.language,
    errorCode: state.errorCode,
    recognizedText,
    start,
    stop,
    retry,
    reset,
    markSubmitted,
  };
}
