"use client";

import type { TranslationKey } from "@/lib/i18n/translations";
import type {
  AssessmentAnswerValue,
  AssessmentQuestion,
} from "@/lib/assessment/types";

type AssessmentSectionProps = {
  question: AssessmentQuestion;
  answer?: AssessmentAnswerValue;
  error?: string;
  onChange: (answer: AssessmentAnswerValue) => void;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
};

export function AssessmentSection({
  question,
  answer,
  error,
  onChange,
  t,
  isDark,
}: AssessmentSectionProps) {
  const inputClass = isDark
    ? "mt-3 w-full rounded-xl border border-[#2B373B] bg-[#202B2F] px-4 py-3 text-sm text-[#F4F7F6] outline-none focus:border-[#63B3A7] focus:ring-4 focus:ring-[#63B3A7]/20"
    : "mt-3 w-full rounded-xl border border-[var(--app-border)] bg-white px-4 py-3 text-sm text-[#172033] outline-none focus:border-[#2F7D73] focus:ring-4 focus:ring-[#2F7D73]/15";

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

        {question.passage ? (
          <div className={isDark ? "mb-5 rounded-xl bg-[#202B2F] p-4 text-sm leading-7" : "mb-5 rounded-xl bg-[var(--app-surface-muted)] p-4 text-sm leading-7"}>
            {question.passage}
          </div>
        ) : null}

        <h2 className="text-xl font-semibold tracking-tight">{question.prompt}</h2>

        {question.options?.length ? (
          <fieldset className="mt-5 space-y-3">
            <legend className="sr-only">{t("assessment.selectOneOption")}</legend>
            {question.options.map((option) => (
              <label
                key={option.id}
                className={isDark ? "flex cursor-pointer gap-3 rounded-xl border border-[#2B373B] bg-[#202B2F] p-4 text-sm" : "flex cursor-pointer gap-3 rounded-xl border border-[var(--app-border)] bg-white p-4 text-sm"}
              >
                <input
                  type="radio"
                  name={`question-${question.attempt_question_id}`}
                  checked={answer?.selected_option_id === option.id}
                  onChange={() => onChange({ selected_option_id: option.id })}
                />
                <span>{option.text}</span>
              </label>
            ))}
          </fieldset>
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
              {question.question_type === "copy_typing"
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

        {question.question_type !== "reading_mcq" && question.question_type !== "mcq" ? (
          <p className={isDark ? "mt-4 text-sm text-[#A8B3B0]" : "mt-4 text-sm text-[#667085]"}>
            {t("assessment.keyboardHelp")}
          </p>
        ) : null}
      </div>
    </section>
  );
}
