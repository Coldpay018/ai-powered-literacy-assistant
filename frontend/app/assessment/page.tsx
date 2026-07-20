"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useLanguage } from "@/components/LanguageProvider";
import { AssessmentIntro } from "@/components/assessment/AssessmentIntro";
import { AssessmentProgress } from "@/components/assessment/AssessmentProgress";
import { AssessmentResult } from "@/components/assessment/AssessmentResult";
import { AssessmentSection } from "@/components/assessment/AssessmentSection";
import {
  getAssessmentResult,
  getAssessmentStatus,
  isAuthenticationError,
  startAssessment,
  submitAssessmentSpokenAnswer,
  submitAssessmentAnswer,
} from "@/lib/assessment/api";
import type {
  AssessmentAnswerValue,
  AssessmentAttempt,
  AssessmentResult as AssessmentResultType,
} from "@/lib/assessment/types";
import { API_BASE_URL } from "@/lib/api/config";
import { applyDocumentTheme } from "@/lib/theme";

type Theme = "light" | "dark";
type Stage = "intro" | "question" | "result";
type UserProfile = {
  comfortable_language?: string;
  learning_language?: string;
  profile_complete?: boolean;
};

export default function InitialAssessmentPage() {
  const router = useRouter();
  const { setLanguageFromValue, resetLanguage, t } = useLanguage();
  const [theme, setTheme] = useState<Theme>("light");
  const [token, setToken] = useState("");
  const [stage, setStage] = useState<Stage>("intro");
  const [attempt, setAttempt] = useState<AssessmentAttempt | null>(null);
  const [result, setResult] = useState<AssessmentResultType | null>(null);
  const [answer, setAnswer] = useState<AssessmentAnswerValue>({});
  const [loading, setLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [speechFeedback, setSpeechFeedback] = useState("");

  const isDark = theme === "dark";

  useEffect(() => {
    applyDocumentTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (!speechFeedback) {
      return;
    }
    const timeout = window.setTimeout(() => {
      setSpeechFeedback("");
    }, 2200);
    return () => {
      window.clearTimeout(timeout);
    };
  }, [speechFeedback]);

  const currentQuestion = attempt?.current_question || null;

  const loadProfileLanguage = useCallback(
    async (authToken: string) => {
      try {
        const response = await fetch(`${API_BASE_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });

        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem("access_token");
          resetLanguage();
          router.replace("/login");
          return false;
        }

        if (!response.ok) {
          setError(t("profile.loadError"));
          return false;
        }

        const user = (await response.json()) as UserProfile;
        const resolvedUiLanguage = setLanguageFromValue(user.comfortable_language);
        console.log({
          comfortableLanguage: user.comfortable_language,
          learningLanguage: user.learning_language,
          appliedUiLanguage: resolvedUiLanguage,
        });
        if (!user.profile_complete) {
          router.replace("/dashboard");
          return false;
        }
        return true;
      } catch (caught) {
        console.error(caught);
        setError(t("profile.loadError"));
        return false;
      }
    },
    [resetLanguage, router, setLanguageFromValue, t],
  );

  const loadAssessment = useCallback(
    async (authToken: string) => {
      setLoading(true);
      setError("");
      setSpeechFeedback("");
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

        const activeAttempt = await startAssessment(authToken);
        setAttempt(activeAttempt);
        setAnswer({});
        setStage(activeAttempt.assessment_complete ? "result" : activeAttempt.current_question ? "question" : "intro");

        if (activeAttempt.assessment_complete) {
          const completedResult = await getAssessmentResult(authToken);
          setResult(completedResult);
          setStage("result");
        }
      } catch (caught) {
        console.error(caught);
        if (isAuthenticationError(caught)) {
          resetLanguage();
          router.replace("/login");
          return;
        }
        setError(t("assessment.loadError"));
      } finally {
        setLoading(false);
      }
    },
    [resetLanguage, router, t],
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

    queueMicrotask(() => {
      setTheme(resolvedTheme);
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
      void loadProfileLanguage(authToken).then((loadedProfile) => {
        if (loadedProfile) {
          void loadAssessment(authToken);
        } else {
          setLoading(false);
        }
      });
    });
  }, [loadAssessment, loadProfileLanguage, resetLanguage, router]);

  const totalQuestions = attempt?.total_questions || 0;
  const answeredQuestions = attempt?.answered_questions || 0;
  const completedSkills = attempt?.completed_skills || [];
  const currentSkill = currentQuestion?.skill || null;
  const currentDifficulty = currentQuestion?.difficulty_rating || null;
  const overallPercent = totalQuestions > 0 ? Math.round((answeredQuestions / totalQuestions) * 100) : 0;
  const currentQuestionNumber = answeredQuestions + (currentQuestion ? 1 : 0);
  const isFinalQuestion = currentQuestionNumber > 0 && currentQuestionNumber === totalQuestions;
  const submitLabel = isFinalQuestion ? t("assessment.submit") : t("assessment.submitAnswer");

  const pageClass = isDark
    ? "min-h-screen bg-[#0F1517] text-[#F4F7F6]"
    : "min-h-screen bg-[var(--app-page)] text-[#172033]";
  const panelClass = isDark
    ? "border-[#2B373B] bg-[#151D20]"
    : "border-[var(--app-border)] bg-[var(--app-surface)]";
  const secondaryTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const buttonClass = isDark
    ? "rounded-xl bg-[#63B3A7] px-5 py-3 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] disabled:opacity-60"
    : "rounded-xl bg-[#2F7D73] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25675F] disabled:opacity-60";

  const startOrResumeAssessment = async () => {
    if (!token) {
      router.replace("/login");
      return;
    }

    setIsStarting(true);
    setError("");
    setSpeechFeedback("");
    try {
      const started = await startAssessment(token);
      setAttempt(started);
      setAnswer({});
      if (started.assessment_complete) {
        const completedResult = await getAssessmentResult(token);
        setResult(completedResult);
        setStage("result");
        return;
      }
      if (started.current_question) {
        setStage("question");
      } else {
        setError(t("assessment.noQuestionsAvailable"));
      }
    } catch (caught) {
      console.error(caught);
      if (isAuthenticationError(caught)) {
        resetLanguage();
        router.replace("/login");
        return;
      }
      setError(t("assessment.startError"));
    } finally {
      setIsStarting(false);
    }
  };

  const submitAnswer = async () => {
    if (!attempt || !currentQuestion || !token) {
      return;
    }

    const validationKey = validateCurrentAnswer(currentQuestion, answer);
    if (validationKey) {
      setFieldError(t(validationKey));
      return;
    }

    setFieldError("");
    setIsSubmitting(true);
    setError("");
    setSpeechFeedback("");

    try {
      const submitted = await submitAssessmentAnswer(
        token,
        attempt.attempt_id,
        currentQuestion.attempt_question_id,
        answer,
      );

      const nextAttempt: AssessmentAttempt = {
        ...attempt,
        answered_questions: submitted.answered_questions,
        total_questions: submitted.total_questions,
        completed_skills: submitted.completed_skills,
        current_question: submitted.next_question,
        assessment_complete: submitted.assessment_complete,
        final_skill_profile: submitted.final_skill_profile,
      };
      setAttempt(nextAttempt);

      if (submitted.result) {
        setResult(submitted.result);
        setStage("result");
        return;
      }

      if (submitted.next_question) {
        setAnswer({});
        setStage("question");
        return;
      }

      const refreshed = await getAssessmentResult(token);
      setResult(refreshed);
      setStage("result");
    } catch (caught) {
      console.error(caught);
      if (isAuthenticationError(caught)) {
        resetLanguage();
        router.replace("/login");
        return;
      }
      setError(t("assessment.answerError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitSpokenAnswer = async (recognizedText: string) => {
    if (!attempt || !currentQuestion || !token) {
      return;
    }

    setFieldError("");
    setIsSubmitting(true);
    setError("");
    setSpeechFeedback("");

    try {
      const submitted = await submitAssessmentSpokenAnswer(
        token,
        attempt.attempt_id,
        currentQuestion.attempt_question_id,
        recognizedText,
      );

      const nextAttempt: AssessmentAttempt = {
        ...attempt,
        answered_questions: submitted.answered_questions,
        total_questions: submitted.total_questions,
        completed_skills: submitted.completed_skills,
        current_question: submitted.next_question,
        assessment_complete: submitted.assessment_complete,
        final_skill_profile: submitted.final_skill_profile,
      };
      setAttempt(nextAttempt);
      setSpeechFeedback(submitted.feedback || "");

      if (submitted.result) {
        setResult(submitted.result);
        setStage("result");
        return;
      }

      if (submitted.next_question) {
        setAnswer({});
        setStage("question");
        return;
      }

      const refreshed = await getAssessmentResult(token);
      setResult(refreshed);
      setStage("result");
    } catch (caught) {
      console.error(caught);
      if (isAuthenticationError(caught)) {
        resetLanguage();
        router.replace("/login");
        return;
      }
      setError(t("assessment.answerError"));
    } finally {
      setIsSubmitting(false);
    }
  };

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
          <AssessmentIntro onStart={startOrResumeAssessment} isStarting={isStarting} isDark={isDark} t={t} />
        ) : null}

        {stage === "question" && attempt && currentQuestion ? (
          <section className={`space-y-5 rounded-2xl border p-5 shadow-xl ${panelClass}`}>
            <AssessmentProgress
              answeredQuestions={answeredQuestions}
              totalQuestions={totalQuestions}
              completedSkills={completedSkills}
              currentSkill={currentSkill}
              currentDifficulty={currentDifficulty}
              overallPercent={overallPercent}
              t={t}
              isDark={isDark}
            />
            <AssessmentSection
              key={currentQuestion.attempt_question_id}
              question={currentQuestion}
              answer={answer}
              error={fieldError}
              submitLabel={submitLabel}
              ttsLanguage={currentQuestion.learning_language || currentQuestion.speech_language}
              feedback={speechFeedback}
              onChange={(nextAnswer) => {
                setAnswer(nextAnswer);
                setFieldError("");
              }}
              onSubmit={submitAnswer}
              onSubmitRecognizedText={submitSpokenAnswer}
              isSubmitting={isSubmitting}
              t={t}
              isDark={isDark}
            />
            {currentQuestion.input_mode !== "letter_tiles" && currentQuestion.input_mode !== "word_tiles" ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
                <button type="button" onClick={submitAnswer} disabled={isSubmitting} className={buttonClass}>
                  {isSubmitting ? t("assessment.submitting") : submitLabel}
                </button>
              </div>
            ) : null}
          </section>
        ) : null}

        {stage === "result" && result ? (
          <AssessmentResult result={result} onDashboard={() => router.push("/dashboard")} isDark={isDark} t={t} />
        ) : null}

        {stage === "question" && attempt && currentQuestion ? (
          <p className={`text-sm ${secondaryTextClass}`}>
            {t("assessment.questionOf", { current: currentQuestionNumber, total: totalQuestions })}
          </p>
        ) : null}

      </div>
    </main>
  );
}

function validateCurrentAnswer(
  question: AssessmentAttempt["current_question"],
  answer: AssessmentAnswerValue,
) {
  if (!question) {
    return "";
  }

  if (question.question_type === "reading_mcq" || question.question_type === "mcq") {
    return answer.selected_option_id ? "" : "assessment.requiredAnswer";
  }

  if (question.question_type === "short_response") {
    return answer.text && answer.text.length <= 1000 ? "" : "assessment.answerTooLong";
  }

  if (
    question.question_type === "copy_typing" ||
    question.question_type === "sentence_completion" ||
    question.question_type === "sentence_rearrange"
  ) {
    return answer.text && answer.text.length <= 500 ? "" : "assessment.answerTooLong";
  }

  return answer.text?.trim() ? "" : "assessment.requiredAnswer";
}
