"use client";

import type { TranslationKey } from "@/lib/i18n/translations";

type AssessmentIntroProps = {
  onStart: () => void;
  isStarting: boolean;
  isDark: boolean;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
};

export function AssessmentIntro({
  onStart,
  isStarting,
  isDark,
  t,
}: AssessmentIntroProps) {
  const cardClass = isDark
    ? "border-[#2B373B] bg-[#151D20] text-[#F4F7F6]"
    : "border-[var(--app-border)] bg-[var(--app-surface)] text-[#172033]";
  const mutedTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] disabled:opacity-60"
    : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F] disabled:opacity-60";

  return (
    <section className={`rounded-2xl border p-6 shadow-xl ${cardClass}`}>
      <p className="text-sm font-semibold text-[#2F7D73] dark:text-[#63B3A7]">
        {t("assessment.required")}
      </p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
        {t("assessment.title")}
      </h1>
      <p className={`mt-4 text-sm leading-7 ${mutedTextClass}`}>
        {t("assessment.intro")}
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {["assessment.reading", "assessment.typing", "assessment.mcq"].map((key, index) => (
          <div
            key={key}
            className={
              isDark
                ? "rounded-xl border border-[#2B373B] bg-[#202B2F] p-4"
                : "rounded-xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-4"
            }
          >
            <p className="text-sm font-semibold">
              {index + 1}. {t(key as TranslationKey)}
            </p>
          </div>
        ))}
      </div>
      <p className={`mt-5 text-sm leading-6 ${mutedTextClass}`}>
        {t("assessment.introHelp")}
      </p>
      <button
        type="button"
        onClick={onStart}
        disabled={isStarting}
        className={`mt-6 ${buttonClass}`}
      >
        {isStarting ? t("assessment.loading") : t("assessment.start")}
      </button>
    </section>
  );
}
