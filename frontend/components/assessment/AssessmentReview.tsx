"use client";

import type { AssessmentAnswers, AssessmentSection } from "@/lib/assessment/types";
import { isQuestionAnswered } from "@/lib/assessment/validation";
import type { TranslationKey } from "@/lib/i18n/translations";

type AssessmentReviewProps = {
  sections: AssessmentSection[];
  answers: AssessmentAnswers;
  onGoToSection: (sectionIndex: number) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  isDark: boolean;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
};

export function AssessmentReview({
  sections,
  answers,
  onGoToSection,
  onSubmit,
  isSubmitting,
  isDark,
  t,
}: AssessmentReviewProps) {
  const total = sections.reduce((count, section) => count + section.questions.length, 0);
  const answered = sections.reduce(
    (count, section) =>
      count +
      section.questions.filter((question) =>
        isQuestionAnswered(question, answers[question.attempt_question_id]),
      ).length,
    0,
  );
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] disabled:opacity-60"
    : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F] disabled:opacity-60";

  return (
    <section
      className={
        isDark
          ? "rounded-2xl border border-[#2B373B] bg-[#151D20] p-6 shadow-xl"
          : "rounded-2xl border border-[#DDE3E0] bg-white p-6 shadow-xl"
      }
    >
      <h1 className="text-2xl font-semibold tracking-tight">{t("assessment.review")}</h1>
      <p className={isDark ? "mt-2 text-sm text-[#A8B3B0]" : "mt-2 text-sm text-[#667085]"}>
        {t("assessment.reviewHelp")}
      </p>

      <div className="mt-5 space-y-3">
        {sections.map((section, index) => {
          const sectionAnswered = section.questions.filter((question) =>
            isQuestionAnswered(question, answers[question.attempt_question_id]),
          ).length;
          return (
            <button
              key={section.section}
              type="button"
              onClick={() => onGoToSection(index)}
              className={
                isDark
                  ? "flex w-full items-center justify-between rounded-xl border border-[#2B373B] bg-[#202B2F] p-4 text-left"
                  : "flex w-full items-center justify-between rounded-xl border border-[#DDE3E0] bg-[#F5F7F6] p-4 text-left"
              }
            >
              <span className="font-semibold">{t(`assessment.${section.section}` as TranslationKey)}</span>
              <span className="text-sm">
                {sectionAnswered}/{section.questions.length} {t("assessment.answered")}
              </span>
            </button>
          );
        })}
      </div>

      <p className="mt-5 text-sm font-semibold">
        {answered}/{total} {t("assessment.answered")}
      </p>
      <button
        type="button"
        onClick={onSubmit}
        disabled={isSubmitting || answered !== total}
        className={`mt-6 ${buttonClass}`}
      >
        {isSubmitting ? t("assessment.submitting") : t("assessment.submit")}
      </button>
    </section>
  );
}
