"use client";

import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import type { DashboardPrototypeData, Translate } from "./types";

type ResourcesSectionProps = {
  prototypeData: DashboardPrototypeData;
  isDark: boolean;
  t: Translate;
  onPrototypeAction: (label: string) => void;
};

const resourceIcons = ["book", "vocabulary", "write"] as const;

export function ResourcesSection({
  prototypeData,
  isDark,
  t,
  onPrototypeAction,
}: ResourcesSectionProps) {
  const cardClass = isDark
    ? "odyssey-card rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "odyssey-card rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/6";

  return (
    <div className="space-y-5">
      <section className={isDark ? "rounded-[2rem] border border-white/10 bg-gradient-to-br from-[#0D1D2F] to-[#083A3A] p-5" : "rounded-[2rem] border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/8"}>
        <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
          {t("common.appName")}
        </p>
        <h2 className="mt-2 text-3xl font-black tracking-normal">{t("common.resources")}</h2>
      </section>

      <section className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {prototypeData.resources.map((resource, index) => (
          <article key={resource.titleKey} className={`${cardClass} group flex min-h-[290px] flex-col`}>
            <div className="mb-5 flex items-start justify-between gap-4">
              <span className={isDark ? "grid h-16 w-16 place-items-center rounded-3xl bg-white/8 transition group-hover:-translate-y-1" : "grid h-16 w-16 place-items-center rounded-3xl bg-[var(--app-surface-muted)] transition group-hover:-translate-y-1"}>
                <LiteracyIcon name={resourceIcons[index] || "book"} className="h-10 w-10" />
              </span>
              <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-xs font-black text-[#0F766E]"}>
                {t(resource.typeKey)}
              </span>
            </div>
            <h2 className="text-xl font-black tracking-normal">{t(resource.titleKey)}</h2>
            <p className={isDark ? "mt-3 flex-1 text-sm leading-6 text-teal-50/66" : "mt-3 flex-1 text-sm leading-6 text-[#667085]"}>
              {t(resource.descriptionKey)}
            </p>
            <button
              type="button"
              onClick={() => onPrototypeAction(t(resource.titleKey))}
              className="group mt-6 rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-4 py-3 text-sm font-black text-white transition hover:brightness-105"
            >
              {t("dashboard.viewResource")} <span className="odyssey-button-arrow inline-block">-&gt;</span>
            </button>
          </article>
        ))}
      </section>
    </div>
  );
}
