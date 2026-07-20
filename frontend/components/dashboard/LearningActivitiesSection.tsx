"use client";

import { useMemo, useState } from "react";
import { LiteracyIcon, type LiteracyIconName } from "@/components/ui/LiteracyIllustrations";
import type { TranslationKey } from "@/lib/i18n/translations";
import type { DashboardPrototypeData, Translate } from "./types";

type Category = "all" | "reading" | "writing" | "vocabulary" | "comprehension";

type LearningActivitiesSectionProps = {
  prototypeData: DashboardPrototypeData;
  isDark: boolean;
  t: Translate;
  onPrototypeAction: (label: string) => void;
  onFlashcards: () => void;
  onPuzzles: () => void;
};

const categories: Array<{ id: Category; labelKey: TranslationKey }> = [
  { id: "all", labelKey: "dashboard.category.all" },
  { id: "reading", labelKey: "dashboard.category.reading" },
  { id: "writing", labelKey: "dashboard.category.writing" },
  { id: "vocabulary", labelKey: "dashboard.category.vocabulary" },
  { id: "comprehension", labelKey: "dashboard.category.comprehension" },
];

const categoryIcons: Record<Exclude<Category, "all">, LiteracyIconName> = {
  reading: "book",
  writing: "write",
  vocabulary: "vocabulary",
  comprehension: "comprehension",
};

export function LearningActivitiesSection({
  prototypeData,
  isDark,
  t,
  onPrototypeAction,
  onFlashcards,
  onPuzzles,
}: LearningActivitiesSectionProps) {
  const [category, setCategory] = useState<Category>("all");
  const filteredActivities = useMemo(
    () =>
      category === "all"
        ? prototypeData.learningActivities
        : prototypeData.learningActivities.filter((activity) => activity.category === category),
    [category, prototypeData.learningActivities],
  );
  const cardClass = isDark
    ? "odyssey-card rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "odyssey-card rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/6";

  return (
    <div className="min-w-0 max-w-full space-y-5">
      <section className={isDark ? "rounded-[2rem] border border-white/10 bg-gradient-to-br from-[#0D1D2F] to-[#083A3A] p-5" : "rounded-[2rem] border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/8"}>
        <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
          {t("common.appName")}
        </p>
        <h2 className="mt-2 text-3xl font-black tracking-normal">{t("dashboard.nav.learningActivities")}</h2>
      </section>

      <div className="flex max-w-full gap-2 overflow-x-auto">
        {categories.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setCategory(item.id)}
            className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-black transition ${
              category === item.id
                ? "bg-gradient-to-r from-[#0F766E] to-[#14B8A6] text-white shadow-lg shadow-teal-950/10"
                : isDark
                  ? "bg-white/8 text-teal-50/72 hover:bg-white/12"
                  : "bg-[var(--app-surface)] text-[#667085] ring-1 ring-[var(--app-border)] hover:text-[#172033]"
            }`}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>

      <section className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {filteredActivities.map((activity) => (
          <article key={activity.titleKey} className={`${cardClass} group flex flex-col`}>
            <div className="mb-5 flex items-start justify-between gap-4">
              <span className={isDark ? "grid h-16 w-16 place-items-center rounded-3xl bg-white/8 transition group-hover:-translate-y-1" : "grid h-16 w-16 place-items-center rounded-3xl bg-[var(--app-surface-muted)] transition group-hover:-translate-y-1"}>
                <LiteracyIcon name={categoryIcons[activity.category]} className="h-10 w-10" />
              </span>
              <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-xs font-black text-[#0F766E]"}>
                {t(`dashboard.category.${activity.category}` as TranslationKey)}
              </span>
            </div>
            <h2 className="text-xl font-black tracking-normal">{t(activity.titleKey)}</h2>
            <p className={isDark ? "mt-3 flex-1 text-sm leading-6 text-teal-50/66" : "mt-3 flex-1 text-sm leading-6 text-[#667085]"}>
              {t(activity.descriptionKey)}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-soft)] px-3 py-1 text-xs font-black text-[#667085]"}>
                {t(activity.difficultyKey)}
              </span>
              <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-soft)] px-3 py-1 text-xs font-black text-[#667085]"}>
                {t("dashboard.durationMinutes", { minutes: activity.durationMinutes })}
              </span>
              {activity.action === "flashcards" || activity.action === "puzzles" ? null : (
                <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-soft)] px-3 py-1 text-xs font-black text-[#667085]"}>
                  {t("common.prototypeData")}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                if (activity.action === "flashcards") {
                  onFlashcards();
                  return;
                }
                if (activity.action === "puzzles") {
                  onPuzzles();
                  return;
                }
                onPrototypeAction(t(activity.titleKey));
              }}
              className="group mt-6 rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-4 py-3 text-sm font-black text-white transition hover:brightness-105"
            >
              {t("dashboard.start")} <span className="odyssey-button-arrow inline-block">-&gt;</span>
            </button>
          </article>
        ))}
      </section>
    </div>
  );
}
