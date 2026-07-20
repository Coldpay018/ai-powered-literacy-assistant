"use client";

import { useEffect } from "react";

import type { TranslationKey } from "@/lib/i18n/translations";
import { useSpeechRecognition, type SpeechRecognitionErrorCode } from "@/lib/stt/speechRecognition";

type AssessmentSpeechRecognitionProps = {
  language?: string | null;
  onSubmitRecognizedText: (recognizedText: string) => Promise<void>;
  isSubmitting: boolean;
  feedback?: string | null;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
};

function MicrophoneIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <rect x="7" y="3.5" width="6" height="9" rx="3" stroke="currentColor" strokeWidth="1.7" />
      <path d="M5 10.5a5 5 0 0 0 10 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M10 15.5v1.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M7.5 17h5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
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

function RetryIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <path d="M5.5 6.5V3.5H2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5.5 3.5a6.5 6.5 0 1 1-1.9 4.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function mapErrorMessage(
  t: AssessmentSpeechRecognitionProps["t"],
  errorCode: SpeechRecognitionErrorCode | null,
) {
  switch (errorCode) {
    case "unsupported_browser":
      return t("assessment.stt.unsupportedBrowser");
    case "unsupported_language":
      return t("assessment.stt.unsupportedLanguage");
    case "permission_denied":
      return t("assessment.stt.permissionDenied");
    case "microphone_unavailable":
      return t("assessment.stt.microphoneUnavailable");
    case "no_speech_detected":
      return t("assessment.stt.noSpeechDetected");
    case "aborted":
      return t("assessment.stt.recognitionAborted");
    case "network_failure":
      return t("assessment.stt.recognitionNetworkError");
    case "service_failure":
      return t("assessment.stt.recognitionServiceError");
    default:
      return "";
  }
}

export function AssessmentSpeechRecognition({
  language,
  onSubmitRecognizedText,
  isSubmitting,
  feedback,
  t,
  isDark,
}: AssessmentSpeechRecognitionProps) {
  const {
    status,
    supported,
    errorCode,
    recognizedText,
    start,
    stop,
    retry,
    reset,
    markSubmitted,
  } = useSpeechRecognition();

  useEffect(() => {
    reset();
  }, [language, reset]);

  const buttonClass = isDark
    ? "inline-flex items-center gap-2 rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-2 text-xs font-semibold text-[#F4F7F6] transition hover:bg-[#243037] focus:outline-none focus:ring-2 focus:ring-[#63B3A7]/30 disabled:cursor-not-allowed disabled:opacity-50"
    : "inline-flex items-center gap-2 rounded-xl border border-[var(--app-border)] bg-white px-3 py-2 text-xs font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] focus:outline-none focus:ring-2 focus:ring-[#2F7D73]/20 disabled:cursor-not-allowed disabled:opacity-50";
  const mutedTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const statusText =
    status === "listening"
      ? t("assessment.stt.listeningState")
      : status === "processing"
        ? t("assessment.stt.processingState")
        : status === "captured"
          ? t("assessment.stt.capturedState")
          : status === "submitted"
            ? t("assessment.stt.submittedState")
            : status === "retry_required"
              ? t("assessment.stt.retryRequiredState")
              : t("assessment.stt.readyState");
  const errorMessage = mapErrorMessage(t, errorCode);
  const canSubmit = status === "captured" && Boolean(recognizedText.trim()) && !isSubmitting;

  const handleToggleListening = () => {
    if (status === "listening" || status === "processing") {
      stop();
      return;
    }
    start(language);
  };

  const handleSubmit = async () => {
    if (!recognizedText.trim()) {
      return;
    }

    await onSubmitRecognizedText(recognizedText);
    markSubmitted();
  };

  if (!supported || errorCode === "unsupported_language") {
    return (
      <div className={isDark ? "rounded-xl border border-[#2B373B] bg-[#202B2F] p-4" : "rounded-xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-4"}>
        <p className={`text-sm font-medium ${mutedTextClass}`}>
          {errorMessage || t("assessment.stt.unsupportedBrowser")}
        </p>
      </div>
    );
  }

  return (
    <div
      lang={language || undefined}
      className={isDark ? "rounded-xl border border-[#2B373B] bg-[#202B2F] p-4" : "rounded-xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-4"}
    >
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={handleToggleListening}
          disabled={isSubmitting || status === "submitted"}
          className={buttonClass}
          aria-label={status === "listening" ? t("assessment.stt.stopListening") : t("assessment.stt.startListening")}
        >
          {status === "listening" ? <StopIcon /> : <MicrophoneIcon />}
          <span>{status === "listening" ? t("assessment.stt.stopListening") : t("assessment.stt.startListening")}</span>
        </button>
        <button
          type="button"
          onClick={retry}
          disabled={isSubmitting || status === "listening" || status === "processing"}
          className={buttonClass}
          aria-label={t("assessment.stt.retryListening")}
        >
          <RetryIcon />
          <span>{t("assessment.stt.retryListening")}</span>
        </button>
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={!canSubmit}
          className={buttonClass}
          aria-label={t("assessment.stt.submitSpokenAnswer")}
        >
          <span>{isSubmitting ? t("assessment.submitting") : t("assessment.stt.submitSpokenAnswer")}</span>
        </button>
      </div>

      <div className={`mt-3 text-xs font-medium ${mutedTextClass}`}>{statusText}</div>
      {feedback ? (
        <div
          className={`mt-2 text-sm font-semibold ${
            feedback === "Correct"
              ? "text-emerald-600"
              : feedback === "Close match"
                ? "text-amber-600"
                : "text-red-600"
          }`}
        >
          {feedback}
        </div>
      ) : null}
      {errorMessage ? <p className="mt-2 text-sm font-medium text-red-500">{errorMessage}</p> : null}
    </div>
  );
}
