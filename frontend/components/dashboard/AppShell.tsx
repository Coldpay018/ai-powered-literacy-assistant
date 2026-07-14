"use client";

import { BrandMark } from "@/components/brand/BrandMark";
import { LiteracyIcon, type LiteracyIconName } from "@/components/ui/LiteracyIllustrations";
import type { ActiveSection, NavItem, Theme, Translate, UserProfile } from "./types";

const navIcons: Record<ActiveSection, LiteracyIconName> = {
  dashboard: "book",
  learningActivities: "write",
  progress: "growth",
  resources: "vocabulary",
  profile: "profile",
};

type AppShellProps = {
  activeSection: ActiveSection;
  navItems: readonly NavItem[];
  theme: Theme;
  email: string;
  profile: UserProfile | null;
  currentLevel: string;
  streakLabel: string;
  t: Translate;
  onSectionChange: (section: ActiveSection) => void;
  onThemeToggle: () => void;
  onLogout: () => void;
  children: React.ReactNode;
};

export function AppShell({
  activeSection,
  navItems,
  theme,
  email,
  profile,
  currentLevel,
  streakLabel,
  t,
  onSectionChange,
  onThemeToggle,
  onLogout,
  children,
}: AppShellProps) {
  const isDark = theme === "dark";
  const activeItem = navItems.find((item) => item.id === activeSection) || navItems[0];
  const initials = (profile?.full_name || email || "U")
    .split(/[ @._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "U";

  return (
    <main className="app-page min-h-screen overflow-x-hidden">
      <div className="mx-auto grid min-h-screen w-full min-w-0 max-w-[1500px] gap-0 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="hidden min-h-full border-r border-[var(--app-border)] app-sidebar shadow-2xl shadow-slate-950/10 lg:block">
          <div className="flex flex-col px-5 py-6">
            <BrandMark light={isDark} className="mb-8" />
            <nav className="space-y-2" aria-label="Primary">
              {navItems.map((item) => {
                const isActive = item.id === activeSection;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={isActive}
                    onClick={() => onSectionChange(item.id)}
                    className={`group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold transition ${
                      isActive
                        ? "bg-gradient-to-r from-[#0F766E] to-[#14B8A6] text-white shadow-lg shadow-teal-950/20"
                        : isDark
                          ? "text-teal-50/72 hover:bg-white/8 hover:text-white"
                          : "text-[#667085] hover:bg-[var(--app-surface-muted)] hover:text-[#172033]"
                    }`}
                  >
                    <span className={isActive ? "grid h-9 w-9 place-items-center rounded-xl bg-white/18" : isDark ? "grid h-9 w-9 place-items-center rounded-xl bg-white/8" : "grid h-9 w-9 place-items-center rounded-xl bg-[var(--app-surface-muted)] shadow-sm"}>
                      <LiteracyIcon name={navIcons[item.id]} className="h-5 w-5" />
                    </span>
                    {t(item.labelKey)}
                  </button>
                );
              })}
            </nav>

            <div className="mt-auto space-y-4">
              <div className={isDark ? "rounded-3xl border border-white/10 bg-white/8 p-4 shadow-xl shadow-black/10" : "rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-4 shadow-lg shadow-slate-900/5"}>
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#D9F6EF] to-[#14B8A6] text-lg font-black text-[#07192F]">
                    {initials}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black">{profile?.full_name || email || "User"}</p>
                    <p className={isDark ? "truncate text-xs font-semibold text-teal-50/62" : "truncate text-xs font-semibold text-[#667085]"}>{currentLevel}</p>
                  </div>
                </div>
              </div>
              <div className={isDark ? "rounded-3xl border border-white/10 bg-[linear-gradient(135deg,rgba(20,184,166,0.2),rgba(7,25,47,0.28))] p-4" : "rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-4"}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-black tracking-normal">6</p>
                    <p className={isDark ? "mt-1 text-sm font-bold text-teal-50/78" : "mt-1 text-sm font-bold text-[#667085]"}>{streakLabel}</p>
                  </div>
                  <span className={isDark ? "grid h-12 w-12 place-items-center rounded-2xl bg-[#F7D774]/20" : "grid h-12 w-12 place-items-center rounded-2xl bg-[var(--app-surface-muted)] shadow-sm"}>
                    <LiteracyIcon name="growth" className="h-7 w-7" />
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={onLogout}
                className={isDark ? "w-full rounded-2xl border border-white/10 px-4 py-3 text-left text-sm font-bold text-teal-50/70 transition hover:bg-white/8 hover:text-white" : "w-full rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface)] px-4 py-3 text-left text-sm font-bold text-[#667085] transition hover:bg-[var(--app-surface-muted)] hover:text-[#172033]"}
              >
                {t("common.logout")}
              </button>
            </div>
          </div>
        </aside>

        <section className="min-w-0 max-w-full">
          <header
            className={
              isDark
                ? "sticky top-0 z-20 border-b border-white/10 bg-[#071426]/90 px-4 py-4 backdrop-blur md:px-7"
                : "sticky top-0 z-20 border-b border-[var(--app-border)] bg-[var(--app-page)] px-4 py-4 backdrop-blur md:px-7"
            }
          >
            <div className="flex flex-col gap-4 lg:hidden">
              <div className="flex items-center justify-between gap-4">
                <BrandMark light={isDark} compact />
                <button
                  type="button"
                  onClick={onThemeToggle}
                  className={isDark ? "rounded-full border border-white/10 px-3 py-2 text-xs font-bold text-white" : "rounded-full border border-[var(--app-border)] bg-[var(--app-surface)] px-3 py-2 text-xs font-bold text-[#172033]"}
                >
                  {theme === "dark" ? t("common.light") : t("common.dark")}
                </button>
              </div>
              <nav className="flex max-w-full gap-2 overflow-x-auto pb-1" aria-label="Mobile primary">
                {navItems.map((item) => {
                  const isActive = item.id === activeSection;
                  return (
                    <button
                      key={item.id}
                    type="button"
                    onClick={() => onSectionChange(item.id)}
                    aria-pressed={isActive}
                    className={`shrink-0 rounded-full px-4 py-2 text-xs font-black transition ${
                      isActive
                        ? "bg-[#0F766E] text-white"
                        : isDark
                          ? "bg-white/8 text-teal-50/72"
                          : "bg-[var(--app-surface-muted)] text-[#667085]"
                    }`}
                  >
                    {t(item.labelKey)}
                  </button>
                );
                })}
              </nav>
            </div>

            <div className="hidden items-center justify-between gap-5 lg:flex">
              <div>
                <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
                  {t(activeItem.labelKey)}
                </p>
                <h1 className="mt-1 text-3xl font-black tracking-normal">
                  {activeSection === "dashboard" ? t("dashboard.title") : t(activeItem.labelKey)}
                </h1>
                <p className={isDark ? "mt-1 text-sm text-teal-50/62" : "mt-1 text-sm text-[#667085]"}>
                  {email ? `${t("dashboard.signedInAs")} ${email}` : t("dashboard.signedInGeneric")}
                </p>
              </div>
              <button
                type="button"
                onClick={onThemeToggle}
                aria-label={theme === "dark" ? t("common.switchToLight") : t("common.switchToDark")}
                className={isDark ? "rounded-full border border-white/10 bg-white/8 px-4 py-2 text-sm font-bold text-white transition hover:bg-white/12" : "rounded-full border border-[var(--app-border)] bg-[var(--app-surface)] px-4 py-2 text-sm font-bold text-[#172033] shadow-sm transition hover:bg-[var(--app-surface-muted)]"}
              >
                {theme === "dark" ? t("common.light") : t("common.dark")}
              </button>
            </div>
          </header>

          <div className="page-enter min-w-0 max-w-full px-4 py-5 md:px-7 md:py-7">{children}</div>
        </section>
      </div>
    </main>
  );
}
