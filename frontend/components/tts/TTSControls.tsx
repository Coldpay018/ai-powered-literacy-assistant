"use client";

import type { TranslationKey } from "@/lib/i18n/translations";
import { speakSpeechSegments, useSpeechSynthesis, type SpeechSegment } from "@/lib/tts/speech";

type TTSControlsProps = {
  text: string;
  segments?: SpeechSegment[];
  language?: string | null;
  label?: TranslationKey;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
  className?: string;
  variant?: "full" | "single";
  buttonText?: string;
  ariaLabel?: string;
  iconOnly?: boolean;
};

function PlayIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
      <path d="M6 4.5v11l9-5.5-9-5.5Z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
      <path d="M5 4.5h3v11H5v-11Zm7 0h3v11h-3v-11Z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
      <rect x="5" y="5" width="10" height="10" rx="2" />
    </svg>
  );
}

function ReplayIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <path d="M5.5 6.5V3.5H2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5.5 3.5a6.5 6.5 0 1 1-1.9 4.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SpeedIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <path d="M4.5 10.5a5.5 5.5 0 1 1 11 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M10 10.5l3-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function SpeakerIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <path d="M4.5 11V9h2.3l3.2-2.6v7.2L6.8 11H4.5Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M12 7.5c1.2 1.1 1.2 3.9 0 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M13.8 5.8c2.4 2.2 2.4 6.2 0 8.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export function TTSControls({
  text,
  segments,
  language,
  label = "tts.title",
  t,
  isDark,
  className,
  variant = "full",
  buttonText,
  ariaLabel,
  iconOnly = false,
}: TTSControlsProps) {
  const {
    status,
    supported,
    rate,
    error,
    speak,
    pause,
    resume,
    stop,
    replay,
  } = useSpeechSynthesis();

  const hasText = Boolean(text.trim());
  const hasSegments = Boolean(segments?.some((segment) => segment.text.trim()));
  const canSpeak = supported && (hasText || hasSegments);
  const isSpeaking = status === "speaking";
  const isPaused = status === "paused";
  const isStopped = status === "stopped";
  const nextRate = rate === 1 ? 0.8 : 1;
  const resolvedLanguage = language || "en";
  const surfaceClass = isDark
    ? "rounded-2xl border border-[#2B373B] bg-[#202B2F] px-3 py-2 text-[#F4F7F6]"
    : "rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] px-3 py-2 text-[#172033]";
  const buttonClass = isDark
    ? "inline-flex items-center gap-2 rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-2 text-xs font-semibold text-[#F4F7F6] transition hover:bg-[#243037] focus:outline-none focus:ring-2 focus:ring-[#63B3A7]/30 disabled:cursor-not-allowed disabled:opacity-50"
    : "inline-flex items-center gap-2 rounded-xl border border-[var(--app-border)] bg-white px-3 py-2 text-xs font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] focus:outline-none focus:ring-2 focus:ring-[#2F7D73]/20 disabled:cursor-not-allowed disabled:opacity-50";
  const singleButtonClass = isDark
    ? "inline-flex items-center justify-center gap-2 rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-2 text-xs font-semibold text-[#F4F7F6] transition hover:bg-[#243037] focus:outline-none focus:ring-2 focus:ring-[#63B3A7]/30 disabled:cursor-not-allowed disabled:opacity-50"
    : "inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--app-border)] bg-white px-3 py-2 text-xs font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] focus:outline-none focus:ring-2 focus:ring-[#2F7D73]/20 disabled:cursor-not-allowed disabled:opacity-50";
  const statusText =
    status === "speaking"
      ? t("tts.state.speaking")
      : status === "paused"
        ? t("tts.state.paused")
      : status === "stopped"
        ? t("tts.state.stopped")
        : status === "error"
          ? t("tts.state.error")
          : !supported || status === "unavailable"
            ? t("tts.state.unavailable")
            : t("tts.state.ready");

  return (
    <>
      {variant === "single" ? (
        <div className="inline-flex flex-col gap-1">
          <button
            type="button"
            onClick={() =>
              void (segments?.length
                ? speakSpeechSegments(segments.map((segment) => ({ ...segment, rate: rate || 1 })))
                : speak({ text, language: resolvedLanguage, rate: rate || 1 }))
            }
            disabled={!canSpeak}
            className={`${singleButtonClass} ${className || ""}`}
            aria-label={ariaLabel || buttonText || t(label)}
            title={error || ariaLabel || buttonText || t(label)}
          >
            <SpeakerIcon />
            {iconOnly ? <span className="sr-only">{buttonText || ariaLabel || t(label)}</span> : <span>{buttonText || ariaLabel || t(label)}</span>}
          </button>
          {!iconOnly ? (
            <span
              className={isDark ? "px-1 text-[11px] font-medium text-[#A8B3B0]" : "px-1 text-[11px] font-medium text-[#667085]"}
            >
              {statusText}
            </span>
          ) : null}
          {error && !iconOnly ? (
            <span className="px-1 text-[11px] font-medium text-red-500">{error}</span>
          ) : null}
          {!supported ? (
            <span className="px-1 text-[11px] font-medium text-[#667085]">{t("tts.unsupportedMessage")}</span>
          ) : null}
        </div>
      ) : (
        <div className={`${surfaceClass} ${className || ""}`}>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-[#0F766E] dark:text-[#63D8C8]">
              {t(label)}
            </span>
            <span className={isDark ? "rounded-full bg-white/10 px-2 py-1 text-[11px] font-bold text-[#CDEAE6]" : "rounded-full bg-white px-2 py-1 text-[11px] font-bold text-[#667085]"}>
              {statusText}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() =>
                void (segments?.length
                  ? speakSpeechSegments(segments.map((segment) => ({ ...segment, rate: rate || 1 })))
                  : speak({ text, language: resolvedLanguage, rate: rate || 1 }))
              }
              disabled={!canSpeak}
              className={buttonClass}
              aria-label={t("tts.play")}
              title={t("tts.play")}
            >
              <PlayIcon />
              <span>{t("tts.play")}</span>
            </button>
            <button
              type="button"
              onClick={() => void pause()}
              disabled={!isSpeaking}
              className={buttonClass}
              aria-label={t("tts.pause")}
              title={t("tts.pause")}
            >
              <PauseIcon />
              <span>{t("tts.pause")}</span>
            </button>
            <button
              type="button"
              onClick={() => void resume()}
              disabled={!isPaused}
              className={buttonClass}
              aria-label={t("tts.resume")}
              title={t("tts.resume")}
            >
              <PlayIcon />
              <span>{t("tts.resume")}</span>
            </button>
            <button
              type="button"
              onClick={() =>
                void (segments?.length
                  ? speakSpeechSegments(segments.map((segment) => ({ ...segment, rate: rate || 1 })))
                  : replay({ text, language: resolvedLanguage, rate: rate || 1 }))
              }
              disabled={!canSpeak}
              className={buttonClass}
              aria-label={t("tts.replay")}
              title={t("tts.replay")}
            >
              <ReplayIcon />
              <span>{t("tts.replay")}</span>
            </button>
            <button
              type="button"
              onClick={() => void stop()}
              disabled={!isSpeaking && !isPaused && !isStopped}
              className={buttonClass}
              aria-label={t("tts.stop")}
              title={t("tts.stop")}
            >
              <StopIcon />
              <span>{t("tts.stop")}</span>
            </button>
            <button
              type="button"
              onClick={() =>
                void (segments?.length
                  ? speakSpeechSegments(segments.map((segment) => ({ ...segment, rate: nextRate })))
                  : speak({ text, language: resolvedLanguage, rate: nextRate }))
              }
              disabled={!canSpeak}
              className={buttonClass}
              aria-label={rate === 1 ? t("tts.slow") : t("tts.normal")}
              title={rate === 1 ? t("tts.slow") : t("tts.normal")}
            >
              <SpeedIcon />
              <span>{rate === 1 ? t("tts.slow") : t("tts.normal")}</span>
            </button>
          </div>
        </div>
        {error ? <p className="mt-2 text-xs font-medium text-red-500">{error}</p> : null}
        {!supported ? <p className="mt-2 text-xs font-medium text-[#667085]">{t("tts.unsupportedMessage")}</p> : null}
        </div>
      )}
    </>
  );
}
