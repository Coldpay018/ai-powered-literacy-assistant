"use client";

import type { TranslationKey } from "@/lib/i18n/translations";

type AssessmentProgressProps = {
  sectionLabel: string;
  sectionIndex: number;
  questionIndex: number;
  sectionTotal: number;
  overallPercent: number;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
};

export function AssessmentProgress({
  sectionLabel,
  sectionIndex,
  questionIndex,
  sectionTotal,
  overallPercent,
  t,
  isDark,
}: AssessmentProgressProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-semibold">
          {t("assessment.sectionOf", { current: sectionIndex + 1, total: 3 })}:{" "}
          {sectionLabel}
        </p>
        <p className="text-sm">
          {t("assessment.questionOf", {
            current: questionIndex + 1,
            total: sectionTotal,
          })}
        </p>
      </div>
      <div>
        <div className="mb-1 text-sm">
          {t("assessment.overallProgress")}: {overallPercent}%
        </div>
        <div className={isDark ? "h-3 rounded-full bg-[#202B2F]" : "h-3 rounded-full bg-[#EEF3F1]"}>
          <div
            className={isDark ? "h-3 rounded-full bg-[#63B3A7]" : "h-3 rounded-full bg-[#2F7D73]"}
            style={{ width: `${overallPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
