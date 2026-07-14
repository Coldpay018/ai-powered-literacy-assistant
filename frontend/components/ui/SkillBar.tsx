"use client";

import { LiteracyIcon, type LiteracyIconName } from "./LiteracyIllustrations";

type SkillBarProps = {
  label: string;
  value: number;
  icon?: LiteracyIconName;
  isDark?: boolean;
};

export function SkillBar({ label, value, icon = "book", isDark = false }: SkillBarProps) {
  const normalizedValue = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div className="group">
      <div className="mb-2 flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className={isDark ? "grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/8" : "grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#E9F8F4]"}>
            <LiteracyIcon name={icon} className="h-6 w-6 transition group-hover:scale-110" />
          </span>
          <p className="truncate text-sm font-bold">{label}</p>
        </div>
        <p className={isDark ? "text-sm font-semibold text-teal-100/70" : "text-sm font-semibold text-[#667085]"}>
          {normalizedValue}%
        </p>
      </div>
      <div className={isDark ? "h-3 overflow-hidden rounded-full bg-white/10" : "h-3 overflow-hidden rounded-full bg-[#E7EFEC]"}>
        <div
          className="progress-fill h-full rounded-full bg-gradient-to-r from-[#0F766E] to-[#14B8A6]"
          style={{ width: `${normalizedValue}%` }}
        />
      </div>
    </div>
  );
}
