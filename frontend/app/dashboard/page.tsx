"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/LanguageProvider";
import { AppShell } from "@/components/dashboard/AppShell";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { LearningActivitiesSection } from "@/components/dashboard/LearningActivitiesSection";
import { ProfileSection } from "@/components/dashboard/ProfileSection";
import { ProgressSection } from "@/components/dashboard/ProgressSection";
import { ResourcesSection } from "@/components/dashboard/ResourcesSection";
import type {
  ActiveSection,
  DashboardPrototypeData,
  ProfileForm,
  UserProfile,
} from "@/components/dashboard/types";
import {
  getAssessmentResult,
  getAssessmentStatus,
  isAuthenticationError,
} from "@/lib/assessment/api";
import type {
  AssessmentResult,
  AssessmentStatusResponse,
} from "@/lib/assessment/types";
import {
  getLearningPlan,
  getProgressRecords,
} from "@/lib/learning/api";
import type {
  LearningPlan,
  ProgressRecord,
  RecommendedLesson,
} from "@/lib/learning/types";
import {
  clearStoredUiLanguage,
  normalizeLanguage,
} from "@/lib/i18n/types";
import type { TranslationKey } from "@/lib/i18n/translations";
import { API_BASE_URL } from "@/lib/api/config";

const navItems = [
  { id: "dashboard", labelKey: "common.dashboard" },
  { id: "learningActivities", labelKey: "dashboard.nav.learningActivities" },
  { id: "progress", labelKey: "common.progress" },
  { id: "resources", labelKey: "common.resources" },
  { id: "profile", labelKey: "common.profile" },
] as const satisfies ReadonlyArray<{ id: ActiveSection; labelKey: TranslationKey }>;

type Theme = "light" | "dark";

type ApiErrorDetail = string | { msg?: string }[] | { msg?: string };

async function readErrorMessage(response: Response) {
  try {
    const data = (await response.json()) as { detail?: ApiErrorDetail };
    const detail = data.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join(" ");
    }

    if (detail?.msg) {
      return detail.msg;
    }
  } catch {
    return "";
  }

  return "";
}

const prototypeDashboardData: DashboardPrototypeData = {
  summaryCards: [
    {
      labelKey: "dashboard.activitiesCompleted",
      value: "18",
      detailKey: "dashboard.activitiesCompletedDetail",
    },
    {
      labelKey: "dashboard.learningStreak",
      valueKey: "dashboard.learningStreakValue",
      detailKey: "dashboard.learningStreakDetail",
    },
    {
      labelKey: "dashboard.overallProgress",
      valueKey: "dashboard.overallProgressValue",
      detailKey: "dashboard.overallProgressDetail",
    },
  ],
  skillProgress: [
    { skillKey: "dashboard.reading", value: 78 },
    { skillKey: "dashboard.writing", value: 64 },
    { skillKey: "dashboard.vocabulary", value: 82 },
    { skillKey: "dashboard.comprehension", value: 58 },
  ],
  recentActivities: [
    "dashboard.completedVowelPractice",
    "dashboard.reviewedVocabulary",
    "dashboard.finishedPassage",
  ],
  learningActivities: [
    {
      titleKey: "dashboard.readAndMatch",
      descriptionKey: "dashboard.readAndMatchDescription",
      difficultyKey: "dashboard.beginner",
      duration: "12 min",
      category: "reading",
    },
    {
      titleKey: "dashboard.soundBuilder",
      descriptionKey: "dashboard.soundBuilderDescription",
      difficultyKey: "dashboard.beginner",
      duration: "10 min",
      category: "vocabulary",
    },
    {
      titleKey: "dashboard.sentenceSteps",
      descriptionKey: "dashboard.sentenceStepsDescription",
      difficultyKey: "dashboard.intermediate",
      duration: "15 min",
      category: "writing",
    },
  ],
  resources: [
    {
      titleKey: "dashboard.dailyReadingPractice",
      descriptionKey: "dashboard.dailyReadingPracticeDescription",
      type: "Practice",
    },
    {
      titleKey: "dashboard.vocabularyWordBank",
      descriptionKey: "dashboard.vocabularyWordBankDescription",
      type: "Word Bank",
    },
    {
      titleKey: "dashboard.writingPrompts",
      descriptionKey: "dashboard.writingPromptsDescription",
      type: "Prompts",
    },
  ],
};

export default function Dashboard() {
  const router = useRouter();
  const { setLanguageFromValue, resetLanguage, t } = useLanguage();
  const [email, setEmail] = useState("");
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [activeSection, setActiveSection] = useState<ActiveSection>("dashboard");
  const [theme, setTheme] = useState<Theme>("light");
  const [statusMessage, setStatusMessage] = useState("");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileForm>({
    full_name: "",
    age: "",
    email: "",
    comfortable_language: "en",
    learning_language: "hi",
    experience_level: "Beginner",
    education_level: "",
  });
  const [isProfileLoading, setIsProfileLoading] = useState(true);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [assessmentStatus, setAssessmentStatus] =
    useState<AssessmentStatusResponse | null>(null);
  const [assessmentResult, setAssessmentResult] =
    useState<AssessmentResult | null>(null);
  const [assessmentError, setAssessmentError] = useState("");
  const [learningPlan, setLearningPlan] = useState<LearningPlan | null>(null);
  const [isLearningPlanLoading, setIsLearningPlanLoading] = useState(false);
  const [learningPlanError, setLearningPlanError] = useState("");
  const [updatingLessonId] = useState<number | null>(null);
  const [progressRecords, setProgressRecords] = useState<ProgressRecord[]>([]);
  const [isProgressLoading, setIsProgressLoading] = useState(false);
  const [progressError, setProgressError] = useState("");

  const syncProfileForm = useCallback((nextProfile: UserProfile) => {
    setProfileForm({
      full_name: nextProfile.full_name,
      age: String(nextProfile.age),
      email: nextProfile.email,
      comfortable_language: nextProfile.comfortable_language
        ? normalizeLanguage(nextProfile.comfortable_language)
        : "",
      learning_language: nextProfile.learning_language
        ? normalizeLanguage(nextProfile.learning_language)
        : "",
      experience_level: nextProfile.experience_level || "",
      education_level: nextProfile.education_level,
    });
  }, []);

  const handleUnauthorizedProfile = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    clearStoredUiLanguage();
    resetLanguage();
    router.replace("/login");
  }, [resetLanguage, router]);

  const mapApiError = useCallback(
    (message: string) => {
      if (message.includes("Email is already registered")) {
        return t("auth.emailRegistered");
      }

      if (message.includes("Invalid authentication token")) {
        return t("profile.sessionExpired");
      }

      if (message.includes("Unsupported language")) {
        return t("auth.genericError");
      }

      return message || t("auth.genericError");
    },
    [t],
  );

  const fetchProfile = useCallback(
    async (tokenOverride?: string) => {
      const token = tokenOverride || localStorage.getItem("access_token");

      if (!token) {
        handleUnauthorizedProfile();
        return null;
      }

      setIsProfileLoading(true);
      setProfileError("");

      try {
        const response = await fetch(`${API_BASE_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.status === 401 || response.status === 403) {
          setProfileError(t("profile.sessionExpired"));
          handleUnauthorizedProfile();
          return null;
        }

        if (!response.ok) {
          setProfileError(mapApiError(await readErrorMessage(response)));
          return null;
        }

        const data = (await response.json()) as UserProfile;
        const resolvedUiLanguage = setLanguageFromValue(data.comfortable_language);
        console.log({
          comfortableLanguage: data.comfortable_language,
          learningLanguage: data.learning_language,
          appliedUiLanguage: resolvedUiLanguage,
        });
        setProfile(data);
        setEmail(data.email);
        localStorage.setItem("login_email", data.email);
        syncProfileForm(data);
        return data;
      } catch {
        setProfileError(t("profile.loadError"));
        return null;
      } finally {
        setIsProfileLoading(false);
      }
    },
    [handleUnauthorizedProfile, mapApiError, setLanguageFromValue, syncProfileForm, t],
  );

  const fetchAssessmentStatus = useCallback(
    async (tokenOverride?: string) => {
      const token = tokenOverride || localStorage.getItem("access_token");

      if (!token) {
        handleUnauthorizedProfile();
        return;
      }

      setAssessmentError("");
      try {
        const status = await getAssessmentStatus(token);
        setAssessmentStatus(status);

        if (status.required || status.has_in_progress_attempt) {
          router.replace("/assessment");
          return;
        }

        if (status.completed) {
          const result = await getAssessmentResult(token);
          setAssessmentResult(result);
        }
      } catch (caught) {
        console.error(caught);
        if (isAuthenticationError(caught)) {
          setAssessmentError(t("profile.sessionExpired"));
          handleUnauthorizedProfile();
          return;
        }
        setAssessmentError(t("assessment.statusError"));
      }
    },
    [handleUnauthorizedProfile, router, t],
  );

  const fetchLearningPlan = useCallback(
    async (tokenOverride?: string) => {
      const token = tokenOverride || localStorage.getItem("access_token");

      if (!token) {
        handleUnauthorizedProfile();
        return;
      }

      setIsLearningPlanLoading(true);
      setLearningPlanError("");

      try {
        const plan = await getLearningPlan(token);
        setLearningPlan(plan);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "";
        if (message.includes("assessment")) {
          setLearningPlanError(t("learning.assessmentRequired"));
        } else if (message.includes("Embedding model")) {
          setLearningPlanError(t("learning.modelUnavailable"));
        } else {
          setLearningPlanError(t("learning.loadError"));
        }
      } finally {
        setIsLearningPlanLoading(false);
      }
    },
    [handleUnauthorizedProfile, t],
  );

  const fetchProgressRecords = useCallback(
    async (tokenOverride?: string) => {
      const token = tokenOverride || localStorage.getItem("access_token");

      if (!token) {
        handleUnauthorizedProfile();
        return;
      }

      setIsProgressLoading(true);
      setProgressError("");

      try {
        const records = await getProgressRecords(token);
        setProgressRecords(records);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "";
        setProgressError(mapApiError(message));
      } finally {
        setIsProgressLoading(false);
      }
    },
    [handleUnauthorizedProfile, mapApiError],
  );

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    const resolvedTheme =
      savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";

    const token = localStorage.getItem("access_token");
    const storedEmail = localStorage.getItem("login_email");
    if (!token) {
      router.replace("/login");
      return;
    }

    queueMicrotask(() => {
      setTheme(resolvedTheme);
      setEmail(storedEmail || "");
    });

    queueMicrotask(() => {
      void fetchProfile(token)
        .then((nextProfile) => {
          if (!nextProfile?.profile_complete) {
            return null;
          }
          return Promise.all([
            fetchAssessmentStatus(token),
            fetchLearningPlan(token),
            fetchProgressRecords(token),
          ]).then(() => null);
        })
        .finally(() => setIsCheckingAuth(false));
    });
  }, [fetchAssessmentStatus, fetchLearningPlan, fetchProgressRecords, fetchProfile, router]);

  function beginProfileEdit() {
    if (profile) {
      syncProfileForm(profile);
    }

    setIsEditingProfile(true);
    setProfileMessage("");
    setProfileError("");
  }

  function cancelProfileEdit() {
    if (profile) {
      syncProfileForm(profile);
    }

    setIsEditingProfile(false);
    setProfileMessage("");
    setProfileError("");
  }

  async function handleProfileSave() {
    if (!profile) {
      return;
    }

    const updates: Partial<ProfileForm> = {};
    const trimmedFullName = profileForm.full_name.trim();
    const trimmedEmail = profileForm.email.trim();
    const selectedComfortableLanguage = profileForm.comfortable_language;
    const selectedLearningLanguage = profileForm.learning_language;
    const selectedExperienceLevel = profileForm.experience_level;
    const trimmedEducationLevel = profileForm.education_level.trim();
    const parsedAge = Number(profileForm.age);

    if (!Number.isInteger(parsedAge) || parsedAge <= 0) {
      setProfileError(t("profile.ageInvalid"));
      setProfileMessage("");
      return;
    }

    if (trimmedFullName !== profile.full_name) {
      updates.full_name = trimmedFullName;
    }

    if (parsedAge !== profile.age) {
      updates.age = String(parsedAge);
    }

    if (trimmedEmail !== profile.email) {
      updates.email = trimmedEmail;
    }

    if (selectedComfortableLanguage === selectedLearningLanguage) {
      setProfileError(t("profile.languagesMustDiffer"));
      setProfileMessage("");
      return;
    }

    if (!selectedComfortableLanguage || !selectedLearningLanguage || !selectedExperienceLevel) {
      setProfileError(t("profile.completeRequired"));
      setProfileMessage("");
      return;
    }

    if (selectedComfortableLanguage !== normalizeLanguage(profile.comfortable_language)) {
      updates.comfortable_language = selectedComfortableLanguage;
    }

    if (selectedLearningLanguage !== normalizeLanguage(profile.learning_language)) {
      updates.learning_language = selectedLearningLanguage;
    }

    if (selectedExperienceLevel !== profile.experience_level) {
      updates.experience_level = selectedExperienceLevel;
    }

    if (trimmedEducationLevel !== profile.education_level) {
      updates.education_level = trimmedEducationLevel;
    }

    if (!Object.keys(updates).length) {
      if (profile.profile_complete) {
        setProfileMessage(t("profile.noChanges"));
        setIsEditingProfile(false);
        return;
      }
      updates.comfortable_language = selectedComfortableLanguage;
      updates.learning_language = selectedLearningLanguage;
      updates.experience_level = selectedExperienceLevel;
    }

    const token = localStorage.getItem("access_token");

    if (!token) {
      handleUnauthorizedProfile();
      return;
    }

    setIsSavingProfile(true);
    setProfileError("");
    setProfileMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/users/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...updates,
          age: updates.age ? Number(updates.age) : undefined,
        }),
      });

      if (response.status === 401 || response.status === 403) {
        setProfileError(t("profile.sessionExpired"));
        handleUnauthorizedProfile();
        return;
      }

      if (!response.ok) {
        setProfileError(mapApiError(await readErrorMessage(response)));
        return;
      }

      const data = (await response.json()) as UserProfile;
      const resolvedUiLanguage = setLanguageFromValue(data.comfortable_language);
      console.log({
        comfortableLanguage: data.comfortable_language,
        learningLanguage: data.learning_language,
        appliedUiLanguage: resolvedUiLanguage,
      });
      setProfile(data);
      setEmail(data.email);
      localStorage.setItem("login_email", data.email);
      syncProfileForm(data);
      setIsEditingProfile(false);
      setProfileMessage(t("profile.updated"));
      const nextProfile = await fetchProfile(token);
      if (nextProfile?.profile_complete) {
        await fetchAssessmentStatus(token);
        await fetchLearningPlan(token);
        await fetchProgressRecords(token);
      }
    } catch {
      setProfileError(t("profile.saveError"));
    } finally {
      setIsSavingProfile(false);
    }
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", nextTheme);
    setTheme(nextTheme);
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    clearStoredUiLanguage();
    resetLanguage();
    router.replace("/login");
  }

  function showPrototypeMessage(label: string) {
    setStatusMessage(t("dashboard.prototypeMessage", { label }));
  }

  function formatLevel(level: string) {
    return t(`assessment.level.${level}` as TranslationKey);
  }

  async function handleLessonAction(lesson: RecommendedLesson) {
    const token = localStorage.getItem("access_token");
    if (!token) {
      handleUnauthorizedProfile();
      return;
    }
    router.push(`/lessons/${lesson.lesson_id}`);
  }

  function handleSectionChange(section: ActiveSection) {
    setActiveSection(section);
    setStatusMessage("");
  }

  function renderActiveSection() {
    const assessmentState = {
      assessmentStatus,
      assessmentResult,
      assessmentError,
      onStartAssessment: () => router.push("/assessment"),
      onViewAssessmentResult: () => setActiveSection("progress"),
    };
    const learningPlanState = {
      learningPlan,
      isLearningPlanLoading,
      learningPlanError,
      updatingLessonId,
      onRetryLearningPlan: () => fetchLearningPlan(),
      onLessonAction: handleLessonAction,
    };
    const progressState = {
      progressRecords,
      isProgressLoading,
      progressError,
      onRetryProgress: () => fetchProgressRecords(),
    };
    const isDark = theme === "dark";

    if (activeSection === "learningActivities") {
      return (
        <LearningActivitiesSection
          prototypeData={prototypeDashboardData}
          isDark={isDark}
          t={t}
          onPrototypeAction={showPrototypeMessage}
        />
      );
    }

    if (activeSection === "progress") {
      return (
        <ProgressSection
          {...assessmentState}
          {...learningPlanState}
          prototypeData={prototypeDashboardData}
          progressState={progressState}
          isDark={isDark}
          t={t}
        />
      );
    }

    if (activeSection === "resources") {
      return (
        <ResourcesSection
          prototypeData={prototypeDashboardData}
          isDark={isDark}
          t={t}
          onPrototypeAction={showPrototypeMessage}
        />
      );
    }

    if (activeSection === "profile") {
      return (
        <ProfileSection
          {...assessmentState}
          profile={profile}
          profileForm={profileForm}
          isProfileLoading={isProfileLoading}
          isEditingProfile={isEditingProfile}
          isSavingProfile={isSavingProfile}
          profileError={profileError}
          profileMessage={profileMessage}
          isDark={isDark}
          t={t}
          onRetryProfile={() => fetchProfile()}
          onBeginEdit={beginProfileEdit}
          onCancelEdit={cancelProfileEdit}
          onSaveProfile={handleProfileSave}
          onLogout={handleLogout}
          onProfileFormChange={setProfileForm}
        />
      );
    }

    return (
      <DashboardOverview
        {...assessmentState}
        {...learningPlanState}
        prototypeData={prototypeDashboardData}
        profile={profile}
        email={email}
        isDark={isDark}
        t={t}
        onPrototypeAction={showPrototypeMessage}
      />
    );
  }

  if (isCheckingAuth) {
    return (
      <main className={theme === "dark" ? "min-h-screen bg-[#071426]" : "min-h-screen bg-[#F7FBFA]"} />
    );
  }

  if (profile && !profile.profile_complete) {
    const assessmentState = {
      assessmentStatus,
      assessmentResult,
      assessmentError,
      onStartAssessment: () => undefined,
      onViewAssessmentResult: () => undefined,
    };

    return (
      <AppShell
        activeSection="profile"
        navItems={navItems}
        theme={theme}
        email={email}
        profile={profile}
        currentLevel={t("common.notAvailable")}
        streakLabel={t("dashboard.learningStreakValue")}
        t={t}
        onSectionChange={() => undefined}
        onThemeToggle={toggleTheme}
        onLogout={handleLogout}
      >
        <ProfileSection
          {...assessmentState}
          profile={profile}
          profileForm={profileForm}
          isProfileLoading={isProfileLoading}
          isEditingProfile={false}
          isSavingProfile={isSavingProfile}
          profileError={profileError}
          profileMessage={profileMessage}
          isDark={theme === "dark"}
          t={t}
          onRetryProfile={() => fetchProfile()}
          onBeginEdit={() => undefined}
          onCancelEdit={() => undefined}
          onSaveProfile={handleProfileSave}
          onLogout={handleLogout}
          onProfileFormChange={setProfileForm}
          completionMode
        />
      </AppShell>
    );
  }

  const currentLevel = assessmentResult
    ? formatLevel(assessmentResult.proficiency_level)
    : learningPlan
      ? formatLevel(learningPlan.learner_proficiency_level)
      : t("common.notAvailable");
  const streakLabel = t("dashboard.learningStreakValue");

  return (
    <AppShell
      activeSection={activeSection}
      navItems={navItems}
      theme={theme}
      email={email}
      profile={profile}
      currentLevel={currentLevel}
      streakLabel={streakLabel}
      t={t}
      onSectionChange={handleSectionChange}
      onThemeToggle={toggleTheme}
      onLogout={handleLogout}
    >
      {statusMessage ? (
        <div
          className={
            theme === "dark"
              ? "mb-5 rounded-2xl border border-white/10 bg-white/8 px-4 py-3 text-sm font-bold text-teal-50/80"
              : "mb-5 rounded-2xl border border-[#DDEAE5] bg-white px-4 py-3 text-sm font-bold text-[#60746F] shadow-sm"
          }
        >
          {statusMessage}
        </div>
      ) : null}
      {renderActiveSection()}
    </AppShell>
  );
}
