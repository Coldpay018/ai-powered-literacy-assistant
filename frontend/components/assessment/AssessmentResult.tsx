"use client";

import type { AssessmentResult as AssessmentResultType } from "@/lib/assessment/types";
import type { TranslationKey } from "@/lib/i18n/translations";

type AssessmentResultProps = {
  result: AssessmentResultType;
  onDashboard: () => void;
  isDark: boolean;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
};

export function AssessmentResult({
  result,
  onDashboard,
  isDark,
  t,
}: AssessmentResultProps) {
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC]"
    : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F]";

  const rows: Array<[TranslationKey, string]> = [
    ["assessment.readingScore", `${result.reading_score}%`],
    ["assessment.typingScore", `${result.typing_score}%`],
    ["assessment.mcqScore", `${result.mcq_score}%`],
    ["assessment.overallScore", `${result.overall_score}%`],
    ["assessment.currentLevel", t(`assessment.level.${result.proficiency_level}` as TranslationKey)],
  ];

  return (
    <section
      className={
        isDark
          ? "rounded-2xl border border-[#2B373B] bg-[#151D20] p-6 shadow-xl"
          : "rounded-2xl border border-[#DDE3E0] bg-white p-6 shadow-xl"
      }
    >
      <h1 className="text-2xl font-semibold tracking-tight">
        {t("assessment.completedTitle")}
      </h1>
      <p className={isDark ? "mt-3 text-sm leading-6 text-[#A8B3B0]" : "mt-3 text-sm leading-6 text-[#667085]"}>
        {t("assessment.resultHelp")}
      </p>
      <div className={isDark ? "mt-5 divide-y divide-[#2B373B]" : "mt-5 divide-y divide-[#DDE3E0]"}>
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-4 py-3">
            <p className="text-sm font-medium">{t(label)}</p>
            <p className="text-sm font-semibold">{value}</p>
          </div>
        ))}
      </div>
      <button type="button" onClick={onDashboard} className={`mt-6 ${buttonClass}`}>
        {t("assessment.goToDashboard")}
      </button>
    </section>
  );
}
