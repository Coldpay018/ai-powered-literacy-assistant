"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand/BrandMark";
import { useLanguage } from "@/components/LanguageProvider";
import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import { TTSControls } from "@/components/tts/TTSControls";
import { API_BASE_URL } from "@/lib/api/config";
import type { TranslationKey } from "@/lib/i18n/translations";
import { getLessonPlayer, submitLessonQuiz, updateLessonProgress } from "@/lib/learning/api";
import type { LessonContentBlock, LessonPlayer, LessonQuizSubmitResponse } from "@/lib/learning/types";
import { buildLessonSpeechConfig } from "@/lib/tts/content";
import { applyDocumentTheme } from "@/lib/theme";

type Theme = "light" | "dark";

type UserProfile = {
  comfortable_language?: string;
  learning_language?: string;
};

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asPairs(value: unknown): Array<{ left: string; right: string }> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is { left: string; right: string } =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as { left?: unknown }).left === "string" &&
      typeof (item as { right?: unknown }).right === "string",
  );
}

function blockProgress(index: number, total: number) {
  if (total <= 1) {
    return 90;
  }
  return Math.min(90, Math.max(5, Math.round(((index + 1) / total) * 90)));
}

function getElapsedSeconds(startedAt: number | null) {
  return startedAt ? Math.max(1, Math.floor((Date.now() - startedAt) / 1000)) : 0;
}

function BlockContent({
  block,
  speechConfig,
  t,
  isDark,
}: {
  block: LessonContentBlock;
  speechConfig: { text: string; language: string | null; label: TranslationKey } | null;
  t: (key: TranslationKey, replacements?: Record<string, string | number>) => string;
  isDark: boolean;
}) {
  const items = asStringList(block.metadata?.items);
  const pairs = asPairs(block.metadata?.pairs);

  if (block.content_type === "image" && block.content_url) {
    return (
      <div className={isDark ? "rounded-3xl bg-white/6 p-4" : "rounded-3xl bg-[var(--app-surface-muted)] p-4"}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={block.content_url} alt={block.title} className="mx-auto max-h-[360px] w-full object-contain" />
      </div>
    );
  }

  if (block.content_type === "audio" && block.content_url) {
    return <audio controls src={block.content_url} className="mt-4 w-full" />;
  }

  if (block.content_type === "sequence" && items.length) {
    return (
      <ol className="mt-4 space-y-3">
        {items.map((item, index) => (
          <li key={item} className={isDark ? "rounded-2xl bg-white/8 p-4 text-sm font-bold" : "rounded-2xl bg-[var(--app-surface-muted)] p-4 text-sm font-bold text-[#172033]"}>
            {index + 1}. {item}
          </li>
        ))}
      </ol>
    );
  }

  if (block.content_type === "matching" && pairs.length) {
    return (
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {pairs.map((pair) => (
          <div key={`${pair.left}-${pair.right}`} className={isDark ? "rounded-2xl bg-white/8 p-4" : "rounded-2xl bg-[var(--app-surface-muted)] p-4"}>
            <p className="text-sm font-black">{pair.left}</p>
            <p className={isDark ? "mt-2 text-sm text-teal-50/66" : "mt-2 text-sm text-[#667085]"}>{pair.right}</p>
          </div>
        ))}
      </div>
    );
  }

  return (
    <>
      {speechConfig ? (
        <div className="mb-4">
          <TTSControls
            text={speechConfig.text}
            language={speechConfig.language}
            label={speechConfig.label}
            t={t}
            isDark={isDark}
          />
        </div>
      ) : null}
      <p className={isDark ? "whitespace-pre-wrap text-base leading-8 text-teal-50/78" : "whitespace-pre-wrap text-base leading-8 text-[#334642]"}>
        {block.text_content}
      </p>
    </>
  );
}

export default function LessonPlayerPage() {
  const params = useParams<{ lessonId: string }>();
  const router = useRouter();
  const { setLanguageFromValue, resetLanguage, t } = useLanguage();
  const lessonId = Number(params.lessonId);
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);
  const [lesson, setLesson] = useState<LessonPlayer | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [quizResult, setQuizResult] = useState<LessonQuizSubmitResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [sessionStartedAt, setSessionStartedAt] = useState<number | null>(null);

  const isDark = theme === "dark";

  useEffect(() => {
    applyDocumentTheme(theme);
  }, [theme]);

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    const resolvedTheme =
      savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
    queueMicrotask(() => {
      setTheme(resolvedTheme);
      setMounted(true);
    });
  }, []);

  useEffect(() => {
    async function loadLesson() {
      const token = localStorage.getItem("access_token");
      if (!token) {
        resetLanguage();
        router.replace("/login");
        return;
      }

      setIsLoading(true);
      setError("");
      try {
        const profileResponse = await fetch(`${API_BASE_URL}/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (profileResponse.ok) {
          const user = (await profileResponse.json()) as UserProfile;
          setProfile(user);
          const resolvedUiLanguage = setLanguageFromValue(user.comfortable_language);
          console.log({
            comfortableLanguage: user.comfortable_language,
            learningLanguage: user.learning_language,
            appliedUiLanguage: resolvedUiLanguage,
          });
        }

        const data = await getLessonPlayer(token, lessonId);
        setLesson(data);
        setSessionStartedAt(Date.now());
        const resumeIndex = data.progress?.last_content_block_id
          ? data.content_blocks.findIndex((block) => block.id === data.progress?.last_content_block_id)
          : 0;
        setCurrentIndex(resumeIndex >= 0 ? resumeIndex : 0);
      } catch (caught) {
        if (caught instanceof Error && caught.message === "Lesson is locked") {
          setError(t("lesson.locked"));
        } else {
          setError(t("lesson.loadError"));
        }
      } finally {
        setIsLoading(false);
      }
    }

    if (Number.isFinite(lessonId)) {
      void loadLesson();
    }
  }, [lessonId, resetLanguage, router, setLanguageFromValue, t]);

  const currentBlock = lesson?.content_blocks[currentIndex] || null;
  const quizQuestions = lesson?.questions || [];
  const progressValue = quizResult?.progress.progress_percentage ?? lesson?.progress?.progress_percentage ?? 0;
  const cardClass = isDark
    ? "rounded-3xl border border-white/10 bg-[#0D1D2F]/86 p-5 shadow-2xl shadow-black/20"
    : "rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/6";
  const mutedText = isDark ? "text-teal-50/66" : "text-[#667085]";
  const blockTabs = useMemo(() => lesson?.content_blocks || [], [lesson]);
  const progressRecord = quizResult?.progress ?? lesson?.progress ?? null;
  const speechConfig = currentBlock
    ? buildLessonSpeechConfig(
        currentBlock,
        profile?.comfortable_language,
        profile?.learning_language || lesson?.language,
      )
    : null;

  async function saveProgress(nextIndex: number) {
    if (!lesson) {
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    const nextBlock = lesson.content_blocks[nextIndex];
    const elapsedSeconds = getElapsedSeconds(sessionStartedAt);
    setIsSaving(true);
    setMessage("");
    try {
      const progress = await updateLessonProgress(
        token,
        lesson.id,
        "in_progress",
        blockProgress(nextIndex, lesson.content_blocks.length),
        nextBlock?.id,
        elapsedSeconds,
      );
      setLesson({ ...lesson, progress });
      setMessage(t("lesson.progressSaved"));
    } catch {
      setError(t("lesson.saveError"));
    } finally {
      setIsSaving(false);
    }
  }

  async function goToBlock(nextIndex: number) {
    if (!lesson || nextIndex < 0 || nextIndex >= lesson.content_blocks.length) {
      return;
    }
    setCurrentIndex(nextIndex);
    await saveProgress(nextIndex);
  }

  async function submitQuiz() {
    if (!lesson) {
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      const elapsedSeconds = getElapsedSeconds(sessionStartedAt);
      const result = await submitLessonQuiz(token, lesson.id, answers, elapsedSeconds);
      setQuizResult(result);
      setLesson({ ...lesson, progress: result.progress });
      setMessage(t("lesson.completed"));
    } catch {
      setError(t("lesson.quizError"));
    } finally {
      setIsSaving(false);
    }
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", nextTheme);
    setTheme(nextTheme);
  }

  if (!mounted) {
    return <main className="min-h-screen bg-[var(--app-page)]" />;
  }

  return (
    <main className={isDark ? "min-h-screen bg-[radial-gradient(circle_at_top_right,#123D3C_0,#071426_38%,#050B14_100%)] text-[#F7FBFA]" : "min-h-screen bg-[var(--app-page)] text-[#172033]"}>
      <header className={isDark ? "sticky top-0 z-20 border-b border-white/10 bg-[#071426]/90 px-4 py-4 backdrop-blur md:px-7" : "sticky top-0 z-20 border-b border-[var(--app-border)] bg-[var(--app-page)] px-4 py-4 backdrop-blur md:px-7"}>
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          <BrandMark light={isDark} compact />
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => router.push("/dashboard")} className={isDark ? "rounded-full border border-white/10 px-4 py-2 text-sm font-bold text-white" : "rounded-full border border-[var(--app-border)] bg-white px-4 py-2 text-sm font-bold text-[#172033]"}>
              {t("assessment.goToDashboard")}
            </button>
            <button type="button" onClick={toggleTheme} className={isDark ? "rounded-full border border-white/10 px-4 py-2 text-sm font-bold text-white" : "rounded-full border border-[var(--app-border)] bg-white px-4 py-2 text-sm font-bold text-[#172033]"}>
              {theme === "dark" ? t("common.light") : t("common.dark")}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-5 px-4 py-5 md:px-7 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className={cardClass}>
          <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>{t("lesson.player")}</p>
          <h1 className="mt-2 break-words text-2xl font-black tracking-normal">{lesson?.title || t("common.loading")}</h1>
          <p className={`mt-3 text-sm leading-6 ${mutedText}`}>{lesson?.description}</p>
          {lesson?.description ? (
            <div className="mt-4">
              <TTSControls
                text={lesson.description}
                language={profile?.comfortable_language || lesson.language}
                label="tts.readExplanation"
                t={t}
                isDark={isDark}
              />
            </div>
          ) : null}
          <div className="mt-5">
            <div className={isDark ? "h-3 overflow-hidden rounded-full bg-white/10" : "h-3 overflow-hidden rounded-full bg-[var(--app-surface-muted)]"}>
              <div className="h-full rounded-full bg-gradient-to-r from-[#0F766E] to-[#14B8A6]" style={{ width: `${progressValue}%` }} />
            </div>
            <p className={`mt-2 text-xs font-black ${mutedText}`}>{Math.round(progressValue)}%</p>
          </div>
          {progressRecord ? (
            <div className="mt-5 grid grid-cols-2 gap-3 text-xs font-bold">
              <div className={isDark ? "rounded-2xl bg-white/8 p-3" : "rounded-2xl bg-[var(--app-surface-muted)] p-3"}>
                <p className={mutedText}>{t("lesson.questionsAttempted")}</p>
                <p className="mt-1 text-sm font-black">{progressRecord.questions_attempted}</p>
              </div>
              <div className={isDark ? "rounded-2xl bg-white/8 p-3" : "rounded-2xl bg-[var(--app-surface-muted)] p-3"}>
                <p className={mutedText}>{t("lesson.timeSpent")}</p>
                <p className="mt-1 text-sm font-black">{t("dashboard.timeSpentSeconds", { seconds: progressRecord.time_spent_seconds })}</p>
              </div>
              <div className={isDark ? "rounded-2xl bg-white/8 p-3" : "rounded-2xl bg-[var(--app-surface-muted)] p-3"}>
                <p className={mutedText}>{t("lesson.score")}</p>
                <p className="mt-1 text-sm font-black">{Math.round(progressRecord.score)}%</p>
              </div>
              <div className={isDark ? "rounded-2xl bg-white/8 p-3" : "rounded-2xl bg-[var(--app-surface-muted)] p-3"}>
                <p className={mutedText}>{t("lesson.currentDifficulty")}</p>
                <p className="mt-1 text-sm font-black">
                  {progressRecord.current_difficulty
                    ? t(`assessment.level.${progressRecord.current_difficulty.toLowerCase()}` as TranslationKey)
                    : t("common.notAvailable")}
                </p>
              </div>
            </div>
          ) : null}
          <nav className="mt-5 space-y-2">
            {blockTabs.map((block, index) => (
              <button
                key={block.id}
                type="button"
                onClick={() => void goToBlock(index)}
                className={`w-full rounded-2xl px-4 py-3 text-left text-sm font-bold transition ${
                  index === currentIndex
                    ? "bg-gradient-to-r from-[#0F766E] to-[#14B8A6] text-white"
                    : isDark
                      ? "bg-white/8 text-teal-50/72 hover:bg-white/12"
                      : "bg-[var(--app-surface-muted)] text-[#667085] hover:text-[#172033]"
                }`}
              >
                {block.title}
              </button>
            ))}
          </nav>
        </aside>

        <section className="min-w-0 space-y-5">
          {isLoading ? (
            <div className={cardClass}>{t("lesson.loading")}</div>
          ) : error ? (
            <div className={cardClass}>
              <p className="text-sm font-bold text-red-500">{error}</p>
              <button type="button" onClick={() => router.push("/dashboard")} className="mt-5 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
                {t("assessment.goToDashboard")}
              </button>
            </div>
          ) : lesson && !lesson.is_unlocked ? (
            <div className={cardClass}>
              <div className="flex items-center gap-3">
                <LiteracyIcon name="lightbulb" className="h-8 w-8" />
                <h2 className="text-xl font-black tracking-normal">{t("lesson.locked")}</h2>
              </div>
              <p className={`mt-3 text-sm leading-6 ${mutedText}`}>
                {lesson.lock_reason || t("lesson.locked")}
              </p>
              <button type="button" onClick={() => router.push("/dashboard")} className="mt-5 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
                {t("assessment.goToDashboard")}
              </button>
            </div>
          ) : lesson && currentBlock ? (
            <>
              {message ? <div className={isDark ? "rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-bold text-emerald-200" : "rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800"}>{message}</div> : null}

              <article className={cardClass}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
                      {t(`lesson.type.${currentBlock.content_type}` as TranslationKey)}
                    </p>
                    <h2 className="mt-2 break-words text-3xl font-black tracking-normal">{currentBlock.title}</h2>
                  </div>
                  <span className={isDark ? "rounded-full bg-white/8 px-3 py-1 text-xs font-black text-teal-50/72" : "rounded-full bg-[var(--app-surface-muted)] px-3 py-1 text-xs font-black text-[#0F766E]"}>
                    {currentIndex + 1}/{lesson.content_blocks.length}
                  </span>
                </div>
                <div className="mt-6">
                  <BlockContent block={currentBlock} speechConfig={speechConfig} t={t} isDark={isDark} />
                </div>
              </article>

              <article className={cardClass}>
                <div className="flex items-center gap-3">
                  <LiteracyIcon name="lightbulb" className="h-8 w-8" />
                  <h2 className="text-xl font-black tracking-normal">{t("lesson.quiz")}</h2>
                </div>
                <div className="mt-5 space-y-5">
                  {quizQuestions.map((question) => {
                    const result = quizResult?.results.find((item) => item.question_id === question.id);
                    return (
                      <div key={question.id} className={isDark ? "rounded-2xl bg-white/6 p-4" : "rounded-2xl bg-[var(--app-surface-muted)] p-4"}>
                        <div className="mb-3">
                          <TTSControls
                            text={question.question_text}
                            language={profile?.learning_language || lesson?.language}
                            label="tts.readContent"
                            t={t}
                            isDark={isDark}
                          />
                        </div>
                        <p className="text-sm font-black">{question.sequence_order}. {question.question_text}</p>
                        {question.options.length ? (
                          <div className="mt-3 grid gap-2">
                            {question.options.map((option) => (
                              <label key={option.id} className="flex items-center gap-3 text-sm font-bold">
                                <input
                                  type="radio"
                                  name={`question-${question.id}`}
                                  value={option.option_text}
                                  checked={answers[question.id] === option.option_text}
                                  onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })}
                                />
                                {option.option_text}
                              </label>
                            ))}
                          </div>
                        ) : (
                          <input
                            type="text"
                            value={answers[question.id] || ""}
                            onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })}
                            className={isDark ? "mt-3 h-12 w-full rounded-2xl border border-white/10 bg-white/8 px-4 text-sm text-white outline-none" : "mt-3 h-12 w-full rounded-2xl border border-[var(--app-border)] bg-white px-4 text-sm text-[#172033] outline-none"}
                            placeholder={t("assessment.enterYourAnswer")}
                          />
                        )}
                        {result ? (
                          <p className={result.correct ? "mt-3 text-sm font-bold text-emerald-500" : "mt-3 text-sm font-bold text-red-500"}>
                            {result.correct ? t("lesson.correct") : `${t("lesson.correctAnswer")}: ${result.correct_answer}`}
                          </p>
                        ) : null}
                        {result?.explanation ? <p className={`mt-2 text-sm ${mutedText}`}>{result.explanation}</p> : null}
                      </div>
                    );
                  })}
                </div>
                <button type="button" onClick={() => void submitQuiz()} disabled={isSaving || quizQuestions.length === 0} className="mt-5 rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60">
                  {quizResult ? `${t("lesson.score")}: ${quizResult.score}%` : t("assessment.submit")}
                </button>
              </article>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <button type="button" onClick={() => void goToBlock(currentIndex - 1)} disabled={currentIndex === 0 || isSaving} className={isDark ? "rounded-2xl border border-white/10 px-5 py-3 text-sm font-black text-white disabled:opacity-50" : "rounded-2xl border border-[var(--app-border)] bg-white px-5 py-3 text-sm font-black text-[#172033] disabled:opacity-50"}>
                  {t("assessment.previous")}
                </button>
                <div className="flex flex-col gap-3 sm:flex-row">
                  {lesson.previous_lesson ? (
                    <button type="button" onClick={() => router.push(`/lessons/${lesson.previous_lesson?.id}`)} className={isDark ? "rounded-2xl border border-white/10 px-5 py-3 text-sm font-black text-white" : "rounded-2xl border border-[var(--app-border)] bg-white px-5 py-3 text-sm font-black text-[#172033]"}>
                      {t("lesson.previousLesson")}
                    </button>
                  ) : null}
                  {currentIndex < lesson.content_blocks.length - 1 ? (
                    <button type="button" onClick={() => void goToBlock(currentIndex + 1)} disabled={isSaving} className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white disabled:opacity-60">
                      {isSaving ? t("profile.saving") : t("assessment.next")}
                    </button>
                  ) : lesson.next_lesson ? (
                    <button
                      type="button"
                      onClick={() => {
                        if (!lesson.next_lesson?.is_unlocked) {
                          setMessage(t("lesson.locked"));
                          return;
                        }
                        router.push(`/lessons/${lesson.next_lesson.id}`);
                      }}
                      aria-disabled={!lesson.next_lesson.is_unlocked}
                      className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white"
                    >
                      {lesson.next_lesson.is_unlocked ? t("lesson.nextLesson") : t("lesson.nextLocked")}
                    </button>
                  ) : null}
                </div>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
