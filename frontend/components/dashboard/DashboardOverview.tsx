"use client";

import { AssessmentStatusCard } from "@/components/assessment/AssessmentStatusCard";
import { HeroBookIllustration, LiteracyIcon, type LiteracyIconName } from "@/components/ui/LiteracyIllustrations";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { SkillBar } from "@/components/ui/SkillBar";
import type { ProgressStatus, RecommendedLesson, SkillType } from "@/lib/learning/types";
import type { TranslationKey } from "@/lib/i18n/translations";
import type {
  AssessmentState,
  DashboardPrototypeData,
  LearningPlanState,
  Translate,
  UserProfile,
} from "./types";

type DashboardOverviewProps = AssessmentState &
  LearningPlanState & {
    prototypeData: DashboardPrototypeData;
    profile: UserProfile | null;
    email: string;
    isDark: boolean;
    t: Translate;
    onPrototypeAction: (label: string) => void;
  };

const skillIcons: Record<string, LiteracyIconName> = {
  "dashboard.reading": "book",
  "dashboard.writing": "write",
  "dashboard.vocabulary": "vocabulary",
  "dashboard.comprehension": "comprehension",
};

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="odyssey-button-arrow ml-1 inline-block h-4 w-4"
      fill="none"
    >
      <path
        d="M4 10h11m-4-4 4 4-4 4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function formatSkill(skill: SkillType, t: Translate) {
  return t(`dashboard.${skill}` as TranslationKey);
}

function formatProgressStatus(status: ProgressStatus, t: Translate) {
  if (status === "completed") {
    return t("assessment.completed");
  }
  if (status === "in_progress") {
    return t("assessment.inProgress");
  }
  return t("assessment.notCompleted");
}

function LessonCard({
  lesson,
  isDark,
  updatingLessonId,
  t,
  onLessonAction,
}: {
  lesson: RecommendedLesson;
  isDark: boolean;
  updatingLessonId: number | null;
  t: Translate;
  onLessonAction: (lesson: RecommendedLesson) => void;
}) {
  return (
    <article
      className={
        isDark
          ? "odyssey-card flex h-full min-w-0 max-w-full flex-col rounded-3xl border border-white/10 bg-white/6 p-4"
          : "odyssey-card flex h-full min-w-0 max-w-full flex-col rounded-3xl border border-[#DDEAE5] bg-white p-4 shadow-lg shadow-slate-900/5"
      }
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <span className={isDark ? "grid h-14 w-14 place-items-center rounded-2xl bg-white/8" : "grid h-14 w-14 place-items-center rounded-2xl bg-[#E9F8F4]"}>
          <LiteracyIcon name={lesson.skill_type === "writing" ? "write" : lesson.skill_type === "comprehension" ? "comprehension" : "book"} className="h-8 w-8 transition group-hover:scale-105" />
        </span>
        <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[#EEF8F4] px-3 py-1 text-xs font-black text-[#0F766E]"}>
          {formatProgressStatus(lesson.current_progress_status, t)}
        </span>
      </div>
      <h3 className="break-words text-base font-black tracking-normal">{lesson.title}</h3>
      <p className={isDark ? "mt-2 line-clamp-3 text-sm leading-6 text-teal-50/66" : "mt-2 line-clamp-3 text-sm leading-6 text-[#60746F]"}>
        {lesson.description}
      </p>
      <div className="mb-5 mt-4 flex flex-wrap gap-2 text-xs font-black">
        <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-teal-50/72" : "rounded-full bg-[#F4F1E7] px-3 py-1 text-[#60746F]"}>
          {formatSkill(lesson.skill_type, t)}
        </span>
        <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-teal-50/72" : "rounded-full bg-[#F4F1E7] px-3 py-1 text-[#60746F]"}>
          {lesson.estimated_duration_minutes} min
        </span>
      </div>
      <button
        type="button"
        onClick={() => onLessonAction(lesson)}
        disabled={updatingLessonId === lesson.lesson_id || lesson.current_progress_status === "completed"}
        className="group mt-auto rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-4 py-3 text-sm font-black text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {lesson.current_progress_status === "not_started"
          ? t("learning.startLesson")
          : lesson.current_progress_status === "in_progress"
            ? t("learning.markComplete")
            : t("assessment.completed")}
        <ArrowIcon />
      </button>
    </article>
  );
}

function RecommendedLearningPath({
  state,
  isDark,
  t,
}: {
  state: LearningPlanState;
  isDark: boolean;
  t: Translate;
}) {
  const cardClass = isDark
    ? "rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "rounded-3xl border border-[#DDEAE5] bg-white/92 p-5 shadow-xl shadow-slate-900/6";

  if (state.isLearningPlanLoading) {
    return (
      <section className={`${cardClass} min-w-0 max-w-full`}>
        <h2 className="break-words text-lg font-black tracking-normal">{t("learning.recommendedPath")}</h2>
        <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("learning.loading")}</p>
      </section>
    );
  }

  if (state.learningPlanError) {
    return (
      <section className={`${cardClass} min-w-0 max-w-full`}>
        <h2 className="break-words text-lg font-black tracking-normal">{t("learning.recommendedPath")}</h2>
        <p className="mt-3 text-sm font-bold text-red-500">{state.learningPlanError}</p>
        <button type="button" onClick={state.onRetryLearningPlan} className="mt-5 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
          {t("common.retry")}
        </button>
      </section>
    );
  }

  if (!state.learningPlan || !state.learningPlan.recommended_lessons.length) {
    return (
      <section className={`${cardClass} min-w-0 max-w-full`}>
        <h2 className="break-words text-lg font-black tracking-normal">{t("learning.recommendedPath")}</h2>
        <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("learning.empty")}</p>
      </section>
    );
  }

  return (
    <section className={`${cardClass} min-w-0 max-w-full`}>
      <div className="mb-5 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
            {t("learning.recommendedPath")}
          </p>
          <h2 className="mt-1 break-words text-xl font-black tracking-normal">
            {state.learningPlan.suggested_next_lesson?.title || t("learning.nextLesson")}
          </h2>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2 text-xs font-black">
          <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-teal-50/72" : "rounded-full bg-[#EEF8F4] px-3 py-1 text-[#0F766E]"}>
            {t("learning.weakestSkill")}: {formatSkill(state.learningPlan.weakest_skill, t)}
          </span>
          <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-teal-50/72" : "rounded-full bg-[#EEF8F4] px-3 py-1 text-[#0F766E]"}>
            {t("learning.completed")}: {state.learningPlan.completion_summary.completed_lessons_count}/{state.learningPlan.completion_summary.total_recommended_lessons}
          </span>
        </div>
      </div>
      <div className="grid min-w-0 max-w-full grid-cols-1 items-stretch gap-4 md:grid-cols-2">
        {state.learningPlan.recommended_lessons.map((lesson) => (
          <LessonCard
            key={lesson.lesson_id}
            lesson={lesson}
            isDark={isDark}
            updatingLessonId={state.updatingLessonId}
            t={t}
            onLessonAction={state.onLessonAction}
          />
        ))}
      </div>
    </section>
  );
}

export function DashboardOverview(props: DashboardOverviewProps) {
  const {
    prototypeData,
    profile,
    email,
    isDark,
    t,
    onPrototypeAction,
    assessmentStatus,
    assessmentResult,
    assessmentError,
    onStartAssessment,
    onViewAssessmentResult,
  } = props;

  const overallScore = assessmentResult?.overall_score ?? 72;
  const currentLevel = assessmentResult
    ? t(`assessment.level.${assessmentResult.proficiency_level}` as TranslationKey)
    : assessmentStatus?.proficiency_level
      ? assessmentStatus.proficiency_level
      : t("common.prototypeData");
  const cardClass = isDark
    ? "odyssey-card rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "odyssey-card rounded-3xl border border-[#DDEAE5] bg-white/92 p-5 shadow-xl shadow-slate-900/6";

  return (
    <div className="min-w-0 max-w-full space-y-5">
      <section className={isDark ? "rounded-[2rem] border border-white/10 bg-gradient-to-br from-[#0D1D2F] to-[#083A3A] p-5 shadow-2xl shadow-black/20 md:p-7" : "rounded-[2rem] border border-white/80 bg-gradient-to-br from-white to-[#E9F8F4] p-5 shadow-xl shadow-slate-900/8 md:p-7"}>
        <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
          <div className="min-w-0">
            <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
              {t("common.appName")}
            </p>
            <h2 className="mt-2 break-words text-3xl font-black tracking-normal md:text-4xl">
              Good to see you, {profile?.full_name || email || "User"}.
            </h2>
            <p className={isDark ? "mt-3 max-w-2xl text-sm leading-6 text-teal-50/66" : "mt-3 max-w-2xl text-sm leading-6 text-[#60746F]"}>
              {t("auth.heroDescription")}
            </p>
          </div>
          <HeroBookIllustration className="mx-auto hidden h-auto w-full max-w-[250px] drop-shadow-xl md:block" />
        </div>
      </section>

      {assessmentError ? (
        <div className={isDark ? "rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-200" : "rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700"}>
          {assessmentError}
        </div>
      ) : null}

      <section className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {prototypeData.summaryCards.map((card) => (
          <article key={card.labelKey} className={cardClass}>
            <p className={isDark ? "text-sm font-bold text-teal-50/64" : "text-sm font-bold text-[#60746F]"}>{t(card.labelKey)}</p>
            <p className="mt-3 text-4xl font-black tracking-normal">{card.valueKey ? t(card.valueKey) : card.value}</p>
            <p className={isDark ? "mt-2 text-sm font-bold text-[#63D8C8]" : "mt-2 text-sm font-bold text-[#0F766E]"}>{t(card.detailKey)}</p>
          </article>
        ))}
        <article className={cardClass}>
          <p className={isDark ? "text-sm font-bold text-teal-50/64" : "text-sm font-bold text-[#60746F]"}>{t("assessment.currentLevel")}</p>
          <p className="mt-3 text-2xl font-black tracking-normal">{currentLevel}</p>
          <p className={isDark ? "mt-2 text-sm font-bold text-[#63D8C8]" : "mt-2 text-sm font-bold text-[#0F766E]"}>
            {assessmentResult ? t("assessment.completed") : t("common.prototypeData")}
          </p>
        </article>
      </section>

      <section className="grid min-w-0 grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <div className="min-w-0 space-y-5">
          <div className={cardClass}>
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-black tracking-normal">{t("dashboard.skillProgress")}</h2>
                <p className={isDark ? "mt-1 text-sm text-teal-50/62" : "mt-1 text-sm text-[#60746F]"}>
                  {t("dashboard.skillProgressHelp")}
                </p>
              </div>
            </div>
            <div className="space-y-5">
              {prototypeData.skillProgress.map((item) => (
                <SkillBar
                  key={item.skillKey}
                  label={t(item.skillKey)}
                  value={item.value}
                  icon={skillIcons[item.skillKey] || "book"}
                  isDark={isDark}
                />
              ))}
            </div>
          </div>

          <RecommendedLearningPath state={props} isDark={isDark} t={t} />
        </div>

        <aside className="min-w-0 space-y-5">
          <div className={cardClass}>
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
                  {t("dashboard.overallProgress")}
                </p>
                <h2 className="mt-1 break-words text-xl font-black tracking-normal">{currentLevel}</h2>
              </div>
              <ProgressRing value={overallScore} isDark={isDark} size={122} stroke={14} />
            </div>
            <AssessmentStatusCard
              status={assessmentStatus}
              result={assessmentResult}
              onStart={onStartAssessment}
              onViewResult={onViewAssessmentResult}
              isDark={isDark}
              t={t}
            />
          </div>

          <article className={cardClass}>
            <span className={isDark ? "grid h-16 w-16 place-items-center rounded-3xl bg-white/8" : "grid h-16 w-16 place-items-center rounded-3xl bg-[#E9F8F4]"}>
              <LiteracyIcon name="lightbulb" className="h-10 w-10" />
            </span>
            <p className={isDark ? "mt-5 text-sm font-black text-[#63D8C8]" : "mt-5 text-sm font-black text-[#0F766E]"}>
              {t("dashboard.recommendedActivity")}
            </p>
            <h2 className="mt-2 text-xl font-black tracking-normal">{t("dashboard.readAndMatch")}</h2>
            <p className={isDark ? "mt-3 text-sm leading-6 text-teal-50/66" : "mt-3 text-sm leading-6 text-[#60746F]"}>
              {t("dashboard.readAndMatchDescription")}
            </p>
            <button
              type="button"
              onClick={() => onPrototypeAction(t("dashboard.readAndMatch"))}
              className="group mt-6 inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-4 py-3 text-sm font-black text-white"
            >
              {t("dashboard.startActivity")}
              <ArrowIcon />
            </button>
          </article>
        </aside>
      </section>

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
    </div>
  );
}
