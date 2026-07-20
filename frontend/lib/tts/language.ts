import { normalizeLanguage, type LanguageCode } from "@/lib/i18n/types";

export type SpeechLanguageCode = LanguageCode;

const SPEECH_LOCALE_CANDIDATES: Record<SpeechLanguageCode, string[]> = {
  en: ["en-IN", "en-US", "en-GB", "en-AU"],
  hi: ["hi-IN", "hi"],
  ta: ["ta-IN", "ta"],
  te: ["te-IN", "te"],
  kn: ["kn-IN", "kn"],
};

export function normalizeSpeechLanguage(value?: string | null): SpeechLanguageCode {
  return normalizeLanguage(value);
}

export function resolveSpeechLocaleCandidates(value?: string | null): string[] {
  const language = normalizeSpeechLanguage(value);
  return SPEECH_LOCALE_CANDIDATES[language] || SPEECH_LOCALE_CANDIDATES.en;
}

export function resolveSpeechLocale(value?: string | null): string {
  return resolveSpeechLocaleCandidates(value)[0] || "en-IN";
}
