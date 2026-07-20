"use client";

import type { TranslationKey } from "@/lib/i18n/translations";
import type { AssessmentSkill } from "@/lib/assessment/types";

type AssessmentProgressProps = {
  answeredQuestions: number;
  totalQuestions: number;
  completedSkills: AssessmentSkill[];
  currentSkill?: AssessmentSkill | null;
  currentDifficulty?: number | null;
  overallPercent: number;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
};

export function AssessmentProgress({
  answeredQuestions,
  totalQuestions,
  completedSkills,
  currentSkill,
  currentDifficulty,
  overallPercent,
  t,
  isDark,
}: AssessmentProgressProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">
            {t("assessment.questionOf", { current: answeredQuestions + 1, total: totalQuestions })}
          </p>
          <p className="text-sm text-[#667085] dark:text-[#A8B3B0]">
            {t("assessment.currentQuestion")}
            {currentSkill ? ` · ${currentSkill}` : ""}
            {currentDifficulty ? ` · ${currentDifficulty}` : ""}
          </p>
        </div>
        <p className="text-sm text-[#667085] dark:text-[#A8B3B0]">
          {t("assessment.completedSkills")}: {completedSkills.length}
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
      <div className="flex flex-wrap gap-2">
        {completedSkills.length ? (
          completedSkills.map((skill) => (
            <span
              key={skill}
              className={
                isDark
                  ? "rounded-full bg-[#202B2F] px-3 py-1 text-xs font-semibold text-[#63B3A7]"
                  : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-xs font-semibold text-[#2F7D73]"
              }
            >
              {skill}
            </span>
          ))
        ) : (
          <span className={isDark ? "text-xs text-[#A8B3B0]" : "text-xs text-[#667085]"}>
            {t("assessment.completedSkills")}: 0
          </span>
        )}
      </div>
    </div>
  );
}
