"use client";

import { useEffect, useMemo, useState } from "react";

import { resolveSpeechLocaleCandidates, resolveSpeechLocale } from "./language";
import { sanitizeSpeechText } from "./content";

export type SpeechStatus = "idle" | "speaking" | "paused" | "stopped" | "unavailable" | "error";

export type SpeechRequest = {
  text: string;
  language?: string | null;
  rate?: number;
};

export type SpeechSegment = SpeechRequest;

export type SpeechState = {
  status: SpeechStatus;
  supported: boolean;
  rate: number;
  text: string;
  language: string | null;
  voiceName: string | null;
  error: string | null;
};

type Listener = (state: SpeechState) => void;

const DEFAULT_STATE: SpeechState = {
  status: "idle",
  supported: false,
  rate: 1,
  text: "",
  language: null,
  voiceName: null,
  error: null,
};

let state: SpeechState = DEFAULT_STATE;
let activeToken = 0;
const listeners = new Set<Listener>();
let voicesReady: Promise<SpeechSynthesisVoice[]> | null = null;
const STRICT_VOICE_LANGUAGES = new Set(["ta", "te", "kn"]);

function emit(nextState: Partial<SpeechState>) {
  state = { ...state, ...nextState };
  for (const listener of listeners) {
    listener(state);
  }
}

function isSupported() {
  return typeof window !== "undefined" && typeof window.speechSynthesis !== "undefined" && typeof window.SpeechSynthesisUtterance !== "undefined";
}

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (!isSupported()) {
    return null;
  }
  return window.speechSynthesis;
}

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function clampSpeechRate(rate?: number) {
  const candidate = typeof rate === "number" && Number.isFinite(rate) ? rate : 1;
  return Math.min(2, Math.max(0.1, candidate));
}

function speechLanguageName(language?: string | null) {
  const baseLanguage = resolveSpeechLocale(language).split("-")[0];
  if (baseLanguage === "ta") {
    return "Tamil";
  }
  if (baseLanguage === "te") {
    return "Telugu";
  }
  if (baseLanguage === "kn") {
    return "Kannada";
  }
  return "Requested language";
}

async function loadVoices() {
  const synth = getSpeechSynthesis();
  if (!synth) {
    return [];
  }

  const existing = synth.getVoices();
  if (existing.length) {
    return existing;
  }

  if (voicesReady) {
    return voicesReady;
  }

  voicesReady = new Promise<SpeechSynthesisVoice[]>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) {
        return;
      }
      settled = true;
      synth.removeEventListener("voiceschanged", finish);
      const voices = synth.getVoices();
      if (!voices.length) {
        voicesReady = null;
      }
      resolve(voices);
    };

    synth.addEventListener("voiceschanged", finish, { once: true });
    void delay(1000).then(finish);
  });
  return voicesReady;
}

export function pickSpeechVoice(voices: SpeechSynthesisVoice[], language?: string | null) {
  if (!voices.length) {
    return null;
  }

  const [exactLocale] = resolveSpeechLocaleCandidates(language);
  const normalizedExact = exactLocale.toLowerCase();
  const baseLanguage = normalizedExact.split("-")[0];
  const defaultVoice = voices.find((voice) => voice.default) || null;
  const exactVoice = voices.find((voice) => voice.lang.toLowerCase() === normalizedExact);
  if (exactVoice) {
    return exactVoice;
  }

  const baseVoice = voices.find((voice) => voice.lang.toLowerCase().split("-")[0] === baseLanguage);
  if (baseVoice) {
    return baseVoice;
  }

  return STRICT_VOICE_LANGUAGES.has(baseLanguage) ? null : defaultVoice;
}

function updateSupportState() {
  emit({
    supported: isSupported(),
    status: isSupported() ? state.status : "unavailable",
    error: isSupported() ? state.error : null,
  });
}

async function playSpeechRequest(token: number, request: SpeechRequest) {
  const synth = getSpeechSynthesis();
  if (!synth) {
    emit({ supported: false, status: "unavailable", error: null });
    return false;
  }

  const text = sanitizeSpeechText(request.text, request.language);
  if (!text) {
    return true;
  }

  const voices = await loadVoices();
  if (token !== activeToken) {
    return false;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = clampSpeechRate(request.rate);
  utterance.volume = 1;
  utterance.pitch = 1;
  utterance.lang = resolveSpeechLocale(request.language);

  const voice = pickSpeechVoice(voices, request.language);
  if (!voice && STRICT_VOICE_LANGUAGES.has(utterance.lang.split("-")[0])) {
    emit({
      status: "error",
      supported: true,
      rate: utterance.rate,
      text,
      language: utterance.lang,
      voiceName: null,
      error: `${speechLanguageName(request.language)} voice unavailable on this device.`,
    });
    return false;
  }
  if (voice) {
    utterance.voice = voice;
  }

  return await new Promise<boolean>((resolve) => {
    let started = false;
    const silentFailureTimeout = window.setTimeout(() => {
      if (token !== activeToken || started) {
        return;
      }
      synth.cancel();
      emit({
        status: "error",
        supported: true,
        error: "Speech did not start on this device.",
      });
      resolve(false);
    }, 2500);

    utterance.onstart = () => {
      if (token !== activeToken) {
        return;
      }
      started = true;
      window.clearTimeout(silentFailureTimeout);
      emit({
        status: "speaking",
        supported: true,
        rate: utterance.rate,
        text,
        language: utterance.lang,
        voiceName: utterance.voice?.name ?? null,
        error: null,
      });
    };
    utterance.onpause = () => {
      if (token !== activeToken) {
        return;
      }
      emit({ status: "paused" });
    };
    utterance.onresume = () => {
      if (token !== activeToken) {
        return;
      }
      emit({ status: "speaking" });
    };
    utterance.onend = () => {
      window.clearTimeout(silentFailureTimeout);
      if (token !== activeToken) {
        resolve(false);
        return;
      }
      resolve(true);
    };
    utterance.onerror = (event) => {
      window.clearTimeout(silentFailureTimeout);
      if (token !== activeToken) {
        resolve(false);
        return;
      }
      emit({
        status: "error",
        supported: true,
        error: event.error === "canceled" || event.error === "interrupted" ? null : "Speech synthesis error.",
      });
      resolve(false);
    };

    emit({
      status: "idle",
      supported: true,
      rate: utterance.rate,
      text,
      language: utterance.lang,
      voiceName: utterance.voice?.name ?? null,
      error: null,
    });
    try {
      synth.speak(utterance);
    } catch {
      window.clearTimeout(silentFailureTimeout);
      emit({
        status: "error",
        supported: true,
        error: "Speech synthesis error.",
      });
      resolve(false);
    }
  });
}

export function subscribeToSpeechState(listener: Listener) {
  listeners.add(listener);
  listener(state);
  return () => {
    listeners.delete(listener);
  };
}

export function getSpeechStateSnapshot() {
  return state;
}

export function stopSpeech() {
  const synth = getSpeechSynthesis();
  activeToken += 1;
  if (synth) {
    synth.cancel();
  }
  emit({
    status: isSupported() ? "stopped" : "unavailable",
    error: null,
  });
}

export async function speakText(request: SpeechRequest) {
  const text = sanitizeSpeechText(request.text, request.language);
  if (!text) {
    return false;
  }

  const synth = getSpeechSynthesis();
  if (!synth) {
    emit({ supported: false, status: "unavailable", error: null });
    return false;
  }

  const token = activeToken + 1;
  activeToken = token;
  synth.cancel();
  const didSpeak = await playSpeechRequest(token, request);
  if (token !== activeToken) {
    return false;
  }
  if (didSpeak) {
    emit({ status: "idle" });
  } else if (state.status !== "error") {
    emit({ status: "stopped" });
  }
  return didSpeak;
}

export function pauseSpeech() {
  const synth = getSpeechSynthesis();
  if (!synth || !synth.speaking) {
    return false;
  }
  synth.pause();
  emit({ status: "paused" });
  return true;
}

export function resumeSpeech() {
  const synth = getSpeechSynthesis();
  if (!synth || !synth.paused) {
    return false;
  }
  synth.resume();
  emit({ status: "speaking" });
  return true;
}

export function replaySpeech(request: SpeechRequest) {
  stopSpeech();
  return speakText(request);
}

export async function speakSpeechSegments(segments: SpeechSegment[]) {
  const cleanedSegments = segments.filter((segment) => Boolean(segment.text.trim()));
  if (!cleanedSegments.length) {
    return false;
  }

  const synth = getSpeechSynthesis();
  if (!synth) {
    emit({ supported: false, status: "unavailable", error: null });
    return false;
  }

  const token = activeToken + 1;
  activeToken = token;
  synth.cancel();

  for (const segment of cleanedSegments) {
    if (token !== activeToken) {
      return false;
    }
    const didSpeak = await playSpeechRequest(token, segment);
    if (!didSpeak || token !== activeToken) {
      if (!didSpeak && token === activeToken && state.status !== "error") {
        emit({ status: "stopped" });
      }
      return false;
    }
  }

  if (token === activeToken) {
    emit({ status: "idle" });
  }
  return true;
}

export function useSpeechSynthesis() {
  const [speechState, setSpeechState] = useState<SpeechState>(() => ({
    ...getSpeechStateSnapshot(),
    supported: isSupported(),
    status: isSupported() ? getSpeechStateSnapshot().status : "unavailable",
  }));

  useEffect(() => {
    const unsubscribe = subscribeToSpeechState(setSpeechState);
    updateSupportState();
    return () => {
      unsubscribe();
      stopSpeech();
    };
  }, []);

  const controls = useMemo(
    () => ({
      speak: speakText,
      pause: pauseSpeech,
      resume: resumeSpeech,
      stop: stopSpeech,
      replay: replaySpeech,
    }),
    [],
  );

  return {
    ...speechState,
    ...controls,
  };
}
