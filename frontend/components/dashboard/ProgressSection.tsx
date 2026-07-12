"use client";

import { useState } from "react";
import { AssessmentStatusCard } from "@/components/assessment/AssessmentStatusCard";
import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { SkillBar } from "@/components/ui/SkillBar";
import type { TranslationKey } from "@/lib/i18n/translations";
import type {
  AssessmentState,
  DashboardPrototypeData,
  LearningPlanState,
  ProgressState,
  Translate,
} from "./types";

type Tab = "overview" | "skills" | "activity" | "achievements";

type ProgressSectionProps = AssessmentState &
  LearningPlanState & {
    prototypeData: DashboardPrototypeData;
    progressState: ProgressState;
    isDark: boolean;
    t: Translate;
  };

const tabs: Array<{ id: Tab; labelKey: TranslationKey }> = [
  { id: "overview", labelKey: "dashboard.tab.overview" },
  { id: "skills", labelKey: "dashboard.tab.skills" },
  { id: "activity", labelKey: "dashboard.tab.activity" },
  { id: "achievements", labelKey: "dashboard.tab.achievements" },
];

const achievements: Array<{
  icon: "trophy" | "growth" | "book";
  titleKey: TranslationKey;
  detailKey: TranslationKey;
}> = [
  {
    icon: "trophy",
    titleKey: "dashboard.achievement.consistentLearner",
    detailKey: "dashboard.achievement.consistentLearnerDetail",
  },
  {
    icon: "growth",
    titleKey: "dashboard.achievement.skillBuilder",
    detailKey: "dashboard.achievement.skillBuilderDetail",
  },
  {
    icon: "book",
    titleKey: "dashboard.achievement.readingReady",
    detailKey: "dashboard.achievement.readingReadyDetail",
  },
];

function MiniTrend({ value, isDark }: { value: number; isDark: boolean }) {
  const points = "0,92 50,76 100,61 150,48 200,48 250,36 300,28 350,22";
  return (
    <svg viewBox="0 0 350 110" className="h-52 w-full" role="img" aria-label="Progress over time">
      <defs>
        <linearGradient id="progressArea" x1="0" x2="0" y1="0" y2="110">
          <stop stopColor="#14B8A6" stopOpacity="0.32" />
          <stop offset="1" stopColor="#14B8A6" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 25, 50, 75, 100].map((tick) => (
        <g key={tick}>
          <line x1="0" x2="350" y1={100 - tick} y2={100 - tick} stroke={isDark ? "rgba(255,255,255,0.08)" : "#E3ECE8"} />
          <text x="0" y={98 - tick} fill={isDark ? "rgba(255,255,255,0.5)" : "#60746F"} fontSize="8">
            {tick}%
          </text>
        </g>
      ))}
      <path d={`M${points} L350,110 L0,110 Z`} fill="url(#progressArea)" />
      <polyline points={points} fill="none" stroke="#0F766E" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="300" cy="28" r="6" fill="#14B8A6" stroke={isDark ? "#071426" : "#FFFFFF"} strokeWidth="3" />
      <text x="274" y="12" fill={isDark ? "#D9F6EF" : "#07192F"} fontSize="10" fontWeight="700">
        {value}%
      </text>
    </svg>
  );
}

export function ProgressSection({
  prototypeData,
  assessmentStatus,
  assessmentResult,
  assessmentError,
  onStartAssessment,
  learningPlan,
  isLearningPlanLoading,
  learningPlanError,
  onRetryLearningPlan,
  onLessonAction,
  updatingLessonId,
  progressState,
  isDark,
  t,
}: ProgressSectionProps) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const score = assessmentResult?.overall_score ?? 72;
  const cardClass = isDark
    ? "rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "rounded-3xl border border-[#DDEAE5] bg-white/92 p-5 shadow-xl shadow-slate-900/6";
  const nextLesson = learningPlan?.suggested_next_lesson;

  return (
    <div className="min-w-0 max-w-full space-y-5">
      <div className="flex max-w-full gap-2 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-black transition ${
              activeTab === tab.id
                ? "bg-gradient-to-r from-[#0F766E] to-[#14B8A6] text-white shadow-lg shadow-teal-950/10"
                : isDark
                  ? "bg-white/8 text-teal-50/72 hover:bg-white/12"
                  : "bg-white text-[#60746F] ring-1 ring-[#DDEAE5] hover:text-[#07192F]"
            }`}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {assessmentError ? (
        <div className={isDark ? "rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-200" : "rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700"}>
          {assessmentError}
        </div>
      ) : null}

      {activeTab === "overview" ? (
        <>
          <section className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <div className={`${cardClass} text-center`}>
              <h2 className="text-lg font-black tracking-normal">{t("dashboard.overallProgress")}</h2>
              <div className="mt-5 flex justify-center">
                <ProgressRing value={score} caption={assessmentResult ? t("assessment.completed") : t("common.prototypeData")} isDark={isDark} size={190} stroke={20} />
              </div>
            </div>
            <div className={cardClass}>
              <h2 className="text-lg font-black tracking-normal">{t("dashboard.progressOverTime")}</h2>
              <MiniTrend value={score} isDark={isDark} />
            </div>
          </section>

          <section className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className={cardClass}>
              <h2 className="text-lg font-black tracking-normal">{t("dashboard.skillProgress")}</h2>
              <div className="mt-5 space-y-5">
                {prototypeData.skillProgress.map((item) => (
                  <SkillBar
                    key={item.skillKey}
                    label={t(item.skillKey)}
                    value={item.value}
                    icon={item.skillKey === "dashboard.writing" ? "write" : item.skillKey === "dashboard.vocabulary" ? "vocabulary" : item.skillKey === "dashboard.comprehension" ? "comprehension" : "book"}
                    isDark={isDark}
                  />
                ))}
              </div>
            </div>
            <div className={cardClass}>
              <h2 className="text-lg font-black tracking-normal">{t("dashboard.recommendedNextStep")}</h2>
              {isLearningPlanLoading ? (
                <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("learning.loading")}</p>
              ) : learningPlanError ? (
                <>
                  <p className="mt-3 text-sm font-bold text-red-500">{learningPlanError}</p>
                  <button type="button" onClick={onRetryLearningPlan} className="mt-5 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
                    {t("common.retry")}
                  </button>
                </>
              ) : nextLesson ? (
                <>
                  <span className={isDark ? "mt-5 grid h-16 w-16 place-items-center rounded-3xl bg-white/8" : "mt-5 grid h-16 w-16 place-items-center rounded-3xl bg-[#E9F8F4]"}>
                    <LiteracyIcon name="path" className="h-10 w-10" />
                  </span>
                  <h3 className="mt-4 text-xl font-black tracking-normal">{nextLesson.title}</h3>
                  <p className={isDark ? "mt-3 text-sm leading-6 text-teal-50/66" : "mt-3 text-sm leading-6 text-[#60746F]"}>{nextLesson.description}</p>
                  <button
                    type="button"
                    onClick={() => onLessonAction(nextLesson)}
                    disabled={updatingLessonId === nextLesson.lesson_id || nextLesson.current_progress_status === "completed"}
                    className="group mt-5 w-full rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-4 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {nextLesson.current_progress_status === "not_started" ? t("learning.startLesson") : t("learning.markComplete")}{" "}
                    <span className="odyssey-button-arrow inline-block">-&gt;</span>
                  </button>
                </>
              ) : (
                <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("learning.empty")}</p>
              )}
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-lg font-black tracking-normal">{t("common.progress")}</h2>
            {progressState.isProgressLoading ? (
              <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("common.loading")}</p>
            ) : progressState.progressError ? (
              <>
                <p className="mt-3 text-sm font-bold text-red-500">{progressState.progressError}</p>
                <button type="button" onClick={progressState.onRetryProgress} className="mt-5 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
                  {t("common.retry")}
                </button>
              </>
            ) : progressState.progressRecords.length ? (
              <div className="mt-5 space-y-3">
                {progressState.progressRecords.slice(0, 5).map((record) => (
                  <article key={record.lesson_id} className={isDark ? "rounded-2xl bg-white/8 p-4" : "rounded-2xl bg-[#EEF8F4] p-4"}>
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                      <h3 className="text-sm font-black">{record.lesson_title || `Lesson ${record.lesson_id}`}</h3>
                      <span className={isDark ? "text-xs font-black text-teal-50/66" : "text-xs font-black text-[#60746F]"}>{record.completion_status}</span>
                    </div>
                    <div className={`mt-3 grid grid-cols-2 gap-3 text-xs font-bold ${isDark ? "text-teal-50/72" : "text-[#60746F]"}`}>
                      <p>{t("lesson.questionsAttempted")}: {record.questions_attempted}</p>
                      <p>{t("lesson.score")}: {Math.round(record.score)}%</p>
                      <p>{t("lesson.timeSpent")}: {record.time_spent_seconds}s</p>
                      <p>{t("lesson.currentDifficulty")}: {record.current_difficulty || t("common.notAvailable")}</p>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("common.notAvailable")}</p>
            )}
          </section>
        </>
      ) : null}

      {activeTab === "skills" ? (
        <section className={cardClass}>
          <h2 className="text-lg font-black tracking-normal">{t("dashboard.skillProgress")}</h2>
          <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
            {prototypeData.skillProgress.map((item) => (
              <SkillBar key={item.skillKey} label={t(item.skillKey)} value={item.value} isDark={isDark} />
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "activity" ? (
        <section className={cardClass}>
          <h2 className="text-lg font-black tracking-normal">{t("dashboard.recentActivity")}</h2>
          <div className={isDark ? "mt-4 divide-y divide-white/10" : "mt-4 divide-y divide-[#DDEAE5]"}>
            {prototypeData.recentActivities.map((activity, index) => (
              <div key={activity} className="flex flex-col gap-1 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-bold">{t(activity)}</p>
                <p className={isDark ? "text-sm text-teal-50/62" : "text-sm text-[#60746F]"}>
                  {t("dashboard.sessionCompleted", { number: index + 1 })}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "achievements" ? (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {achievements.map((achievement) => (
            <article key={achievement.titleKey} className={cardClass}>
              <LiteracyIcon name={achievement.icon} className="h-12 w-12" />
              <h3 className="mt-4 text-lg font-black tracking-normal">{t(achievement.titleKey)}</h3>
              <p className={isDark ? "mt-2 text-sm text-teal-50/66" : "mt-2 text-sm text-[#60746F]"}>{t(achievement.detailKey)}</p>
            </article>
          ))}
        </section>
      ) : null}

      <AssessmentStatusCard
        status={assessmentStatus}
        result={assessmentResult}
        onStart={onStartAssessment}
        isDark={isDark}
        t={t}
      />
    </div>
  );
}
