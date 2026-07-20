"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { TranslationKey } from "@/lib/i18n/translations";
import type {
  AssessmentAnswerValue,
  AssessmentQuestion,
  AssessmentTile,
} from "@/lib/assessment/types";
import { TTSControls } from "@/components/tts/TTSControls";
import { buildAssessmentReadAllSegments, buildAssessmentReadAllText } from "@/lib/tts/content";
import { AssessmentSpeechRecognition } from "@/components/assessment/AssessmentSpeechRecognition";

type AssessmentSectionProps = {
  question: AssessmentQuestion;
  answer?: AssessmentAnswerValue;
  error?: string;
  onChange: (answer: AssessmentAnswerValue) => void;
  onSubmit?: () => void;
  onSubmitRecognizedText?: (recognizedText: string) => Promise<void>;
  isSubmitting?: boolean;
  submitLabel: string;
  ttsLanguage?: string | null;
  feedback?: string | null;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
};

export function AssessmentSection({
  question,
  answer,
  error,
  onChange,
  onSubmit,
  onSubmitRecognizedText,
  isSubmitting = false,
  submitLabel,
  ttsLanguage,
  feedback,
  t,
  isDark,
}: AssessmentSectionProps) {
  const [selectedTileIds, setSelectedTileIds] = useState<string[]>([]);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const isLetterTileMode = question.input_mode === "letter_tiles" && Boolean(question.shuffled_tiles?.length);
  const isWordTileMode = question.input_mode === "word_tiles" && Boolean(question.shuffled_tiles?.length);
  const isTileMode = isLetterTileMode || isWordTileMode;
  const isVoiceQuestion =
    Boolean(question.stt_enabled) ||
    question.input_mode === "voice" ||
    ["speaking", "spoken_answer", "spoken_fill_blank", "reading_aloud", "sentence_repetition", "pronunciation"].includes(question.question_type);
  const supportsSpeechRecognition = Boolean(onSubmitRecognizedText && isVoiceQuestion);
  const speechLanguage = question.learning_language || question.speech_language || ttsLanguage || "en";
  const readAllSpeech = buildAssessmentReadAllSegments(question);
  const readAllSegments = readAllSpeech.segments;
  const readAllText = buildAssessmentReadAllText(question);
  const showMeanings = question.experience_level === "Beginner";
  const voiceInstructionText = question.instruction_text?.trim() || question.prompt;
  const voiceTargetText = question.target_text?.trim() || "";
  const voiceTargetTranslation = question.target_translation?.trim() || "";
  const tileById = useMemo(() => {
    return new Map((question.shuffled_tiles || []).map((tile) => [tile.id, tile]));
  }, [question.shuffled_tiles]);

  const selectedTiles = selectedTileIds
    .map((tileId) => tileById.get(tileId))
    .filter((tile): tile is AssessmentTile => Boolean(tile));
  const assembledAnswer = selectedTiles.map((tile) => tile.value).join(isWordTileMode ? " " : "");

  useEffect(() => {
    if (!isTileMode) {
      return;
    }
    onChangeRef.current({ text: assembledAnswer });
  }, [assembledAnswer, isTileMode]);

  const appendTile = (tileId: string) => {
    setSelectedTileIds((previous) => (previous.includes(tileId) ? previous : [...previous, tileId]));
  };

  const undoTile = () => {
    setSelectedTileIds((previous) => previous.slice(0, -1));
  };

  const clearTiles = () => {
    setSelectedTileIds([]);
  };

  const inputClass = isDark
    ? "mt-3 w-full rounded-xl border border-[#2B373B] bg-[#202B2F] px-4 py-3 text-sm text-[#F4F7F6] outline-none focus:border-[#63B3A7] focus:ring-4 focus:ring-[#63B3A7]/20"
    : "mt-3 w-full rounded-xl border border-[var(--app-border)] bg-white px-4 py-3 text-sm text-[#172033] outline-none focus:border-[#2F7D73] focus:ring-4 focus:ring-[#2F7D73]/15";
  const translatedTextClass = isDark
    ? "block text-sm leading-6 text-[#A8B3B0]"
    : "block text-sm leading-6 text-[#667085]";
  const inlineMeaningClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const missingQuestionSpeechMessage = t("assessment.tts.missingQuestionSpeechText");
  const missingOptionSpeechMessage = t("assessment.tts.missingOptionSpeechText");
  const hasReadAllSpeech = readAllSegments.length > 0 && !readAllSpeech.missingQuestionText;
  const hearQuestionTexts = [question.instruction_text, question.tts_text || question.prompt]
    .map((value) => value?.trim() || "")
    .filter((value, index, values) => Boolean(value) && values.indexOf(value) === index);
  const hearQuestionSegments = hearQuestionTexts.map((value) => ({ text: value, language: speechLanguage }));

  const renderTranslatedText = (text?: string | null) =>
    text?.trim() ? <span className={translatedTextClass}>{text}</span> : null;

  return (
    <section>
      <div className={isDark ? "rounded-2xl border border-[#2B373B] bg-[#151D20] p-5" : "rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5"}>
        <div className="mb-4 flex flex-wrap gap-2">
          <span className={isDark ? "rounded-full bg-[#202B2F] px-3 py-1 text-sm text-[#63B3A7]" : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-sm text-[#2F7D73]"}>
            {question.difficulty}
          </span>
          <span className={isDark ? "rounded-full bg-[#202B2F] px-3 py-1 text-sm text-[#A8B3B0]" : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-sm text-[#667085]"}>
            {question.marks} {t("assessment.marks")}
          </span>
        </div>

        <div className="mb-4">
          {hasReadAllSpeech ? (
            <TTSControls
              text={readAllText}
              segments={readAllSegments}
              language={speechLanguage}
              label="assessment.readAll"
              buttonText={t("assessment.readAll")}
              ariaLabel={t("assessment.readAll")}
              t={t}
              isDark={isDark}
              variant="single"
            />
          ) : (
            <p className={isDark ? "text-sm font-medium text-[#A8B3B0]" : "text-sm font-medium text-[#667085]"}>
              {missingQuestionSpeechMessage}
            </p>
          )}
        </div>

        {question.passage ? (
          <div className="mt-2">
            <div className={isDark ? "rounded-xl bg-[#202B2F] p-4 text-sm leading-7" : "rounded-xl bg-[var(--app-surface-muted)] p-4 text-sm leading-7"}>
              {question.passage}
            </div>
            {question.passage_translation?.trim() ? (
              <div className="mt-2">
                {renderTranslatedText(question.passage_translation)}
              </div>
            ) : null}
          </div>
        ) : null}

        {isVoiceQuestion ? (
          <div className="mt-4 space-y-3">
            <h2 className="text-xl font-semibold tracking-tight">
              {voiceInstructionText}
            </h2>
            {question.prompt_translation?.trim() ? (
              <div>
                {renderTranslatedText(question.prompt_translation)}
              </div>
            ) : null}
            {voiceTargetText ? (
              <div className={isDark ? "rounded-xl border border-[#2B373B] bg-[#202B2F] p-4 text-lg font-semibold leading-7 text-[#F4F7F6]" : "rounded-xl border border-[var(--app-border)] bg-white p-4 text-lg font-semibold leading-7 text-[#172033]"}>
                {voiceTargetText}
              </div>
            ) : (
              <p className={isDark ? "text-sm font-medium text-[#A8B3B0]" : "text-sm font-medium text-[#667085]"}>{missingQuestionSpeechMessage}</p>
            )}
            {voiceTargetTranslation ? (
              <div className="ml-1">
                {renderTranslatedText(voiceTargetTranslation)}
              </div>
            ) : null}
            {supportsSpeechRecognition ? (
              <div className="pt-1">
                <AssessmentSpeechRecognition
                  language={speechLanguage}
                  onSubmitRecognizedText={async (recognizedText) => {
                    if (!onSubmitRecognizedText) {
                      return;
                    }
                    await onSubmitRecognizedText(recognizedText);
                  }}
                  isSubmitting={isSubmitting}
                  feedback={feedback}
                  t={t}
                  isDark={isDark}
                />
              </div>
            ) : null}
          </div>
        ) : (
          <>
            <h2 className="mt-4 text-xl font-semibold tracking-tight">
              {question.prompt}
            </h2>
            {question.prompt_translation?.trim() ? (
              <div className="mt-2">
                {renderTranslatedText(question.prompt_translation)}
              </div>
            ) : null}
          </>
        )}

        {question.options?.length ? (
          <fieldset className="mt-5 space-y-3">
            <legend className="sr-only">{t("assessment.selectOneOption")}</legend>
            {question.options.map((option, index) => {
              const optionLabel = index < 26 ? String.fromCharCode(65 + index) : String(index + 1);
              const optionMeaning = showMeanings ? option.translation?.trim() : "";
              return (
                <div
                  key={option.id}
                  className={isDark ? "flex items-center gap-3 rounded-xl border border-[#2B373B] bg-[#202B2F] p-4 text-sm" : "flex items-center gap-3 rounded-xl border border-[var(--app-border)] bg-white p-4 text-sm"}
                >
                  <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                    <input
                      type="radio"
                      name={`question-${question.attempt_question_id}`}
                      checked={answer?.selected_option_id === option.id}
                      onChange={() => onChange({ selected_option_id: option.id })}
                      className="mt-1"
                    />
                    <span className="min-w-0">
                      {option.text}
                      {optionMeaning ? <span className={inlineMeaningClass}> ({optionMeaning})</span> : null}
                    </span>
                  </label>
                  <TTSControls
                    text={option.text}
                    language={speechLanguage}
                    label="assessment.readOption"
                    buttonText={t("assessment.readOption", { option: optionLabel })}
                    ariaLabel={t("assessment.readOption", { option: optionLabel })}
                    t={t}
                    isDark={isDark}
                    variant="single"
                    iconOnly
                    className="shrink-0"
                  />
                  {!option.text?.trim() ? (
                    <span className={isDark ? "text-xs font-medium text-[#A8B3B0]" : "text-xs font-medium text-[#667085]"}>
                      {missingOptionSpeechMessage}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </fieldset>
        ) : isTileMode ? (
          <div className="mt-5 space-y-4">
            <div className={isDark ? "rounded-xl border border-[#2B373B] bg-[#202B2F] p-4 text-sm leading-7" : "rounded-xl border border-[var(--app-border)] bg-white p-4 text-sm leading-7"}>
              <span className="block text-sm font-semibold">{t("assessment.buildAnswer")}</span>
              <div
                aria-live="polite"
                className={isDark ? "mt-3 min-h-12 rounded-xl border border-[#2B373B] bg-[#151D20] px-4 py-3 text-base font-semibold text-[#F4F7F6]" : "mt-3 min-h-12 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] px-4 py-3 text-base font-semibold text-[#172033]"}
              >
                {assembledAnswer || " "}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <TTSControls
                text={hearQuestionSegments.map((segment) => segment.text).join(" ")}
                segments={hearQuestionSegments}
                language={speechLanguage}
                label="assessment.hearQuestion"
                buttonText={t("assessment.hearQuestion")}
                ariaLabel={t("assessment.hearQuestion")}
                t={t}
                isDark={isDark}
                variant="single"
              />
              <TTSControls
                text={assembledAnswer}
                language={speechLanguage}
                label="assessment.hearSelectedSentence"
                buttonText={t("assessment.hearSelectedSentence")}
                ariaLabel={t("assessment.hearSelectedSentence")}
                t={t}
                isDark={isDark}
                variant="single"
              />
              <button
                type="button"
                onClick={undoTile}
                disabled={!selectedTileIds.length}
                className={isDark ? "rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-2 text-xs font-semibold text-[#F4F7F6] transition hover:bg-[#243037] disabled:cursor-not-allowed disabled:opacity-50" : "rounded-xl border border-[var(--app-border)] bg-white px-3 py-2 text-xs font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] disabled:cursor-not-allowed disabled:opacity-50"}
              >
                {t("assessment.undo")}
              </button>
              <button
                type="button"
                onClick={clearTiles}
                disabled={!selectedTileIds.length}
                className={isDark ? "rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-2 text-xs font-semibold text-[#F4F7F6] transition hover:bg-[#243037] disabled:cursor-not-allowed disabled:opacity-50" : "rounded-xl border border-[var(--app-border)] bg-white px-3 py-2 text-xs font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] disabled:cursor-not-allowed disabled:opacity-50"}
              >
                {t("assessment.clear")}
              </button>
              <button
                type="button"
                onClick={onSubmit}
                disabled={isSubmitting || !assembledAnswer.trim()}
                className={isDark ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] disabled:opacity-60" : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F] disabled:opacity-60"}
              >
                {isSubmitting ? t("assessment.submitting") : submitLabel}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
              {question.shuffled_tiles?.map((tile) => {
                const selected = selectedTileIds.includes(tile.id);
                const tileMeaning = showMeanings ? tile.translation?.trim() : "";
                return (
                  <div key={tile.id} className="flex min-w-0 items-stretch gap-2">
                    <button
                      type="button"
                      onClick={() => appendTile(tile.id)}
                      disabled={selected}
                      aria-pressed={selected}
                      className={`min-w-0 flex-1 ${selected
                        ? isDark
                          ? "rounded-xl border border-[#63B3A7] bg-[#0F1517] px-3 py-3 text-sm font-semibold text-[#63D8C8] disabled:cursor-not-allowed"
                          : "rounded-xl border border-[#2F7D73] bg-[var(--app-surface-muted)] px-3 py-3 text-sm font-semibold text-[#2F7D73] disabled:cursor-not-allowed"
                        : isDark
                          ? "rounded-xl border border-[#2B373B] bg-[#151D20] px-3 py-3 text-sm font-semibold text-[#F4F7F6] transition hover:bg-[#243037] focus:outline-none focus:ring-2 focus:ring-[#63B3A7]/30 disabled:cursor-not-allowed disabled:opacity-50"
                          : "rounded-xl border border-[var(--app-border)] bg-white px-3 py-3 text-sm font-semibold text-[#172033] transition hover:bg-[var(--app-surface)] focus:outline-none focus:ring-2 focus:ring-[#2F7D73]/20 disabled:cursor-not-allowed disabled:opacity-50"
                      }`}
                    >
                      {tile.value}
                      {tileMeaning ? <span className={inlineMeaningClass}> ({tileMeaning})</span> : null}
                    </button>
                    <TTSControls
                      text={tile.value}
                      language={speechLanguage}
                      label="assessment.readOption"
                      buttonText={tile.value}
                      ariaLabel={tile.value}
                      t={t}
                      isDark={isDark}
                      variant="single"
                      iconOnly
                      className="h-full shrink-0"
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ) : question.question_type === "short_response" ? (
          <label className="block">
            <span className="mt-5 block text-sm font-medium">
              {t("assessment.writeShortResponse")}
            </span>
            <textarea
              value={answer?.text || ""}
              maxLength={1000}
              onChange={(event) => onChange({ text: event.target.value })}
              className={`${inputClass} min-h-[140px]`}
              placeholder={t("assessment.enterYourAnswer")}
            />
          </label>
        ) : (
          <label className="block">
            <span className="mt-5 block text-sm font-medium">
              {isVoiceQuestion
                ? t("assessment.manualAnswerFallback")
                : question.question_type === "copy_typing"
                  ? t("assessment.typeSentence")
                  : t("assessment.completeSentence")}
            </span>
            <input
              value={answer?.text || ""}
              maxLength={300}
              onChange={(event) => onChange({ text: event.target.value })}
              className={inputClass}
              placeholder={t("assessment.enterYourAnswer")}
            />
          </label>
        )}

        {error ? (
          <p className="mt-4 text-sm font-medium text-red-500">{error}</p>
        ) : null}

        {!question.options?.length && !isTileMode && question.question_type !== "reading_mcq" && question.question_type !== "mcq" ? (
          <p className={isDark ? "mt-4 text-sm text-[#A8B3B0]" : "mt-4 text-sm text-[#667085]"}>
            {t("assessment.keyboardHelp")}
          </p>
        ) : null}
      </div>
    </section>
  );
}
