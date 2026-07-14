"use client";

import type { AssessmentResult, AssessmentStatusResponse } from "@/lib/assessment/types";
import type { TranslationKey } from "@/lib/i18n/translations";

type AssessmentStatusCardProps = {
  status: AssessmentStatusResponse | null;
  result: AssessmentResult | null;
  onStart: () => void;
  onViewResult?: () => void;
  isDark: boolean;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
};

export function AssessmentStatusCard({
  status,
  result,
  onStart,
  onViewResult,
  isDark,
  t,
}: AssessmentStatusCardProps) {
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-4 py-2.5 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC]"
    : "rounded-xl bg-[#2F7D73] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#25675F]";
  const label = result
    ? t("assessment.completed")
    : status?.has_in_progress_attempt
      ? t("assessment.inProgress")
      : t("assessment.notCompleted");

  return (
    <article className={isDark ? "rounded-2xl border border-[#2B373B] bg-[#1B2529] p-5 shadow-xl" : "rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl"}>
      <p className="text-sm font-semibold text-[#2F7D73] dark:text-[#63B3A7]">
        {t("assessment.title")}
      </p>
      <div className="mt-4 space-y-2 text-sm">
        <p>
          <span className={isDark ? "text-[#A8B3B0]" : "text-[#667085]"}>
            {t("assessment.status")}:{" "}
          </span>
          <span className="font-semibold">{label}</span>
        </p>
        {result ? (
          <>
            <p>
              <span className={isDark ? "text-[#A8B3B0]" : "text-[#667085]"}>
                {t("assessment.currentLevel")}:{" "}
              </span>
              <span className="font-semibold">
                {t(`assessment.level.${result.proficiency_level}` as TranslationKey)}
              </span>
            </p>
            <p>
              <span className={isDark ? "text-[#A8B3B0]" : "text-[#667085]"}>
                {t("assessment.overallScore")}:{" "}
              </span>
              <span className="font-semibold">{result.overall_score}%</span>
            </p>
          </>
        ) : null}
      </div>
      {result ? (
        onViewResult ? (
          <button type="button" onClick={onViewResult} className={`mt-5 ${buttonClass}`}>
            {t("assessment.viewResult")}
          </button>
        ) : null
      ) : status?.required || status?.has_in_progress_attempt ? (
        <button type="button" onClick={onStart} className={`mt-5 ${buttonClass}`}>
          {status.has_in_progress_attempt ? t("assessment.resume") : t("assessment.start")}
        </button>
      ) : null}
    </article>
  );
}
