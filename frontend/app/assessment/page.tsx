"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/LanguageProvider";
import { AssessmentIntro } from "@/components/assessment/AssessmentIntro";
import { AssessmentProgress } from "@/components/assessment/AssessmentProgress";
import { AssessmentReview } from "@/components/assessment/AssessmentReview";
import { AssessmentResult } from "@/components/assessment/AssessmentResult";
import { AssessmentSection } from "@/components/assessment/AssessmentSection";
import {
  getAssessmentResult,
  getAssessmentStatus,
  saveAssessmentAnswers,
  startAssessment,
  submitAssessment,
} from "@/lib/assessment/api";
import type {
  AssessmentAnswers,
  AssessmentAttempt,
  AssessmentResult as AssessmentResultType,
} from "@/lib/assessment/types";
import { validateQuestion } from "@/lib/assessment/validation";
import { LANGUAGE_STORAGE_KEY } from "@/lib/i18n/types";
import type { TranslationKey } from "@/lib/i18n/translations";

type Theme = "light" | "dark";
type Stage = "intro" | "question" | "review" | "result";

export default function InitialAssessmentPage() {
  const router = useRouter();
  const { setLanguageFromValue, resetLanguage, t } = useLanguage();
  const [theme, setTheme] = useState<Theme>("light");
  const [token, setToken] = useState("");
  const [stage, setStage] = useState<Stage>("intro");
  const [attempt, setAttempt] = useState<AssessmentAttempt | null>(null);
  const [answers, setAnswers] = useState<AssessmentAnswers>({});
  const [result, setResult] = useState<AssessmentResultType | null>(null);
  const [sectionIndex, setSectionIndex] = useState(0);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");

  const isDark = theme === "dark";

  const loadStatus = useCallback(
    async (authToken: string) => {
      setLoading(true);
      setError("");
      try {
        const status = await getAssessmentStatus(authToken);
        if (!status.required && !status.completed && status.reason === "role_not_learner") {
          router.replace("/dashboard");
          return;
        }
        if (status.completed) {
          const completedResult = await getAssessmentResult(authToken);
          setResult(completedResult);
          setStage("result");
          return;
        }
        if (status.has_in_progress_attempt) {
          const resumed = await startAssessment(authToken);
          setAttempt(resumed);
          setLanguageFromValue(resumed.language);
          setAnswers(resumed.answers || {});
          setStage("question");
        }
      } catch (caught) {
        console.error(caught);
        setError(t("assessment.loadError"));
      } finally {
        setLoading(false);
      }
    },
    [router, setLanguageFromValue, t],
  );

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    const resolvedTheme =
      savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";

    const authToken = localStorage.getItem("access_token");
    const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);

    queueMicrotask(() => {
      setTheme(resolvedTheme);
      setLanguageFromValue(storedLanguage);
      if (authToken) {
        setToken(authToken);
      }
    });

    if (!authToken) {
      resetLanguage();
      router.replace("/login");
      return;
    }

    queueMicrotask(() => {
      void loadStatus(authToken);
    });
  }, [loadStatus, resetLanguage, router, setLanguageFromValue]);

  const sections = useMemo(() => attempt?.sections || [], [attempt]);
  const currentSection = sections[sectionIndex];
  const currentQuestion = currentSection?.questions[questionIndex];
  const totalQuestions = useMemo(
    () => sections.reduce((total, section) => total + section.questions.length, 0),
    [sections],
  );
  const completedBeforeCurrent = useMemo(
    () =>
      sections
        .slice(0, sectionIndex)
        .reduce((total, section) => total + section.questions.length, 0),
    [sectionIndex, sections],
  );
  const overallPercent =
    totalQuestions > 0
      ? Math.round(((completedBeforeCurrent + questionIndex + 1) / totalQuestions) * 100)
      : 0;

  const pageClass = isDark
    ? "min-h-screen bg-[#0F1517] text-[#F4F7F6]"
    : "min-h-screen bg-[#F5F7F6] text-[#172033]";
  const panelClass = isDark
    ? "border-[#2B373B] bg-[#151D20]"
    : "border-[#DDE3E0] bg-white";
  const secondaryTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] disabled:opacity-60"
    : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F] disabled:opacity-60";
  const secondaryButtonClass = isDark
    ? "rounded-xl border border-[#2B373B] px-5 py-3 text-sm font-semibold text-[#F4F7F6] transition hover:bg-[#202B2F]"
    : "rounded-xl border border-[#DDE3E0] px-5 py-3 text-sm font-semibold text-[#172033] transition hover:bg-[#EEF3F1]";

  async function startOrResumeAssessment() {
    if (!token) {
      router.replace("/login");
      return;
    }

    setIsStarting(true);
    setError("");
    try {
      const started = await startAssessment(token);
      setAttempt(started);
      setLanguageFromValue(started.language);
      setAnswers(started.answers || {});
      setStage("question");
    } catch (caught) {
      console.error(caught);
      setError(t("assessment.startError"));
    } finally {
      setIsStarting(false);
    }
  }

  async function saveProgress(nextAnswers: AssessmentAnswers = answers) {
    if (!attempt || !token) {
      return false;
    }
    setIsSaving(true);
    setSaveMessage(t("assessment.saving"));
    try {
      await saveAssessmentAnswers(token, attempt.attempt_id, nextAnswers);
      setSaveMessage(t("assessment.saved"));
      return true;
    } catch (caught) {
      console.error(caught);
      setSaveMessage("");
      setError(t("assessment.saveError"));
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function goNext() {
    if (!currentQuestion || !currentSection) {
      return;
    }
    const validationKey = validateQuestion(
      currentQuestion,
      answers[currentQuestion.attempt_question_id],
    );
    if (validationKey) {
      setFieldError(t(validationKey));
      return;
    }
    setFieldError("");
    const saved = await saveProgress();
    if (!saved) {
      return;
    }
    if (questionIndex < currentSection.questions.length - 1) {
      setQuestionIndex(questionIndex + 1);
      return;
    }
    if (sectionIndex < sections.length - 1) {
      setSectionIndex(sectionIndex + 1);
      setQuestionIndex(0);
      return;
    }
    setStage("review");
  }

  async function goPrevious() {
    setFieldError("");
    await saveProgress();
    if (questionIndex > 0) {
      setQuestionIndex(questionIndex - 1);
      return;
    }
    if (sectionIndex > 0) {
      const previousSection = sections[sectionIndex - 1];
      setSectionIndex(sectionIndex - 1);
      setQuestionIndex(previousSection.questions.length - 1);
    }
  }

  async function submit() {
    if (!attempt || !token) {
      return;
    }
    const unanswered = sections.some((section) =>
      section.questions.some((question) =>
        validateQuestion(question, answers[question.attempt_question_id]),
      ),
    );
    if (unanswered) {
      setError(t("assessment.requiredAnswer"));
      return;
    }
    if (!window.confirm(t("assessment.confirmSubmit"))) {
      return;
    }
    setIsSubmitting(true);
    setError("");
    try {
      const saved = await saveProgress();
      if (!saved) {
        return;
      }
      const submitted = await submitAssessment(token, attempt.attempt_id);
      setResult(submitted);
      setStage("result");
    } catch (caught) {
      console.error(caught);
      setError(t("assessment.submitError"));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loading) {
    return <main className={`${pageClass} flex items-center justify-center p-6`}>{t("common.loading")}</main>;
  }

  return (
    <main className={`${pageClass} transition-colors`}>
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center gap-5 px-5 py-8">
        {error ? (
          <div className={`rounded-2xl border p-4 text-sm font-medium text-red-500 ${panelClass}`}>
            {error}
          </div>
        ) : null}

        {stage === "intro" ? (
          <AssessmentIntro
            onStart={startOrResumeAssessment}
            isStarting={isStarting}
            isDark={isDark}
            t={t}
          />
        ) : null}

        {stage === "question" && attempt && currentSection && currentQuestion ? (
          <section className={`space-y-5 rounded-2xl border p-5 shadow-xl ${panelClass}`}>
            <AssessmentProgress
              sectionLabel={t(`assessment.${currentSection.section}` as TranslationKey)}
              sectionIndex={sectionIndex}
              questionIndex={questionIndex}
              sectionTotal={currentSection.questions.length}
              overallPercent={overallPercent}
              t={t}
              isDark={isDark}
            />
            <AssessmentSection
              question={currentQuestion}
              answer={answers[currentQuestion.attempt_question_id]}
              error={fieldError}
              onChange={(answer) => {
                setAnswers((previous) => ({
                  ...previous,
                  [currentQuestion.attempt_question_id]: answer,
                }));
                setFieldError("");
                setSaveMessage("");
              }}
              t={t}
              isDark={isDark}
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className={`text-sm ${secondaryTextClass}`}>
                {isSaving ? t("assessment.saving") : saveMessage}
              </p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={goPrevious} className={secondaryButtonClass}>
                  {t("assessment.previous")}
                </button>
                <button type="button" onClick={goNext} disabled={isSaving} className={buttonClass}>
                  {sectionIndex === sections.length - 1 &&
                  questionIndex === currentSection.questions.length - 1
                    ? t("assessment.review")
                    : t("assessment.next")}
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {stage === "review" && attempt ? (
          <AssessmentReview
            sections={attempt.sections}
            answers={answers}
            onGoToSection={(nextSectionIndex) => {
              setSectionIndex(nextSectionIndex);
              setQuestionIndex(0);
              setStage("question");
            }}
            onSubmit={submit}
            isSubmitting={isSubmitting}
            isDark={isDark}
            t={t}
          />
        ) : null}

        {stage === "result" && result ? (
          <AssessmentResult
            result={result}
            onDashboard={() => router.replace("/dashboard")}
            isDark={isDark}
            t={t}
          />
        ) : null}
      </div>
    </main>
  );
}
