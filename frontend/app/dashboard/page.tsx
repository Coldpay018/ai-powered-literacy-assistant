"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/LanguageProvider";
import { AssessmentStatusCard } from "@/components/assessment/AssessmentStatusCard";
import {
  getAssessmentResult,
  getAssessmentStatus,
} from "@/lib/assessment/api";
import type {
  AssessmentResult,
  AssessmentStatusResponse,
} from "@/lib/assessment/types";
import {
  LANGUAGE_OPTIONS,
  LANGUAGE_STORAGE_KEY,
  normalizeLanguage,
  type LanguageCode,
} from "@/lib/i18n/types";
import type { TranslationKey } from "@/lib/i18n/translations";

const API_BASE_URL = "http://127.0.0.1:8000";

const navItems = [
  { id: "dashboard", labelKey: "common.dashboard" },
  { id: "learningActivities", labelKey: "dashboard.nav.learningActivities" },
  { id: "progress", labelKey: "common.progress" },
  { id: "resources", labelKey: "common.resources" },
  { id: "profile", labelKey: "common.profile" },
] as const;

type ActiveSection = (typeof navItems)[number]["id"];
type Theme = "light" | "dark";

type UserProfile = {
  id: number;
  full_name: string;
  age: number;
  email: string;
  preferred_language: string;
  education_level: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

type ProfileForm = {
  full_name: string;
  age: string;
  email: string;
  preferred_language: LanguageCode;
  education_level: string;
};

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

const prototypeDashboardData = {
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
    },
    {
      titleKey: "dashboard.soundBuilder",
      descriptionKey: "dashboard.soundBuilderDescription",
      difficultyKey: "dashboard.beginner",
      duration: "10 min",
    },
    {
      titleKey: "dashboard.sentenceSteps",
      descriptionKey: "dashboard.sentenceStepsDescription",
      difficultyKey: "dashboard.intermediate",
      duration: "15 min",
    },
  ],
  resources: [
    {
      titleKey: "dashboard.dailyReadingPractice",
      descriptionKey: "dashboard.dailyReadingPracticeDescription",
    },
    {
      titleKey: "dashboard.vocabularyWordBank",
      descriptionKey: "dashboard.vocabularyWordBankDescription",
    },
    {
      titleKey: "dashboard.writingPrompts",
      descriptionKey: "dashboard.writingPromptsDescription",
    },
  ],
} satisfies {
  summaryCards: Array<{
    labelKey: TranslationKey;
    value?: string;
    valueKey?: TranslationKey;
    detailKey: TranslationKey;
  }>;
  skillProgress: Array<{ skillKey: TranslationKey; value: number }>;
  recentActivities: TranslationKey[];
  learningActivities: Array<{
    titleKey: TranslationKey;
    descriptionKey: TranslationKey;
    difficultyKey: TranslationKey;
    duration: string;
  }>;
  resources: Array<{ titleKey: TranslationKey; descriptionKey: TranslationKey }>;
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
    preferred_language: "en",
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

  const syncProfileForm = useCallback((nextProfile: UserProfile) => {
    setProfileForm({
      full_name: nextProfile.full_name,
      age: String(nextProfile.age),
      email: nextProfile.email,
      preferred_language: normalizeLanguage(nextProfile.preferred_language),
      education_level: nextProfile.education_level,
    });
  }, []);

  const handleUnauthorizedProfile = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
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
        return;
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
          return;
        }

        if (!response.ok) {
          setProfileError(mapApiError(await readErrorMessage(response)));
          return;
        }

        const data = (await response.json()) as UserProfile;
        const nextLanguage = setLanguageFromValue(data.preferred_language);
        setProfile(data);
        setEmail(data.email);
        localStorage.setItem("login_email", data.email);
        localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
        syncProfileForm(data);
      } catch {
        setProfileError(
          t("profile.loadError"),
        );
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
        setAssessmentError(t("assessment.statusError"));
      }
    },
    [handleUnauthorizedProfile, router, t],
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
    const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);

    if (!token) {
      router.replace("/login");
      return;
    }

    queueMicrotask(() => {
      setTheme(resolvedTheme);
      setLanguageFromValue(storedLanguage);
      setEmail(storedEmail || "");
    });

    queueMicrotask(() => {
      void fetchProfile(token);
      void fetchAssessmentStatus(token).finally(() => setIsCheckingAuth(false));
    });
  }, [fetchAssessmentStatus, fetchProfile, router, setLanguageFromValue]);

  const isDark = theme === "dark";

  const pageClass = isDark
    ? "min-h-screen bg-[#0F1517] text-[#F4F7F6]"
    : "min-h-screen bg-[#F5F7F6] text-[#172033]";
  const panelClass = isDark
    ? "border-[#2B373B] bg-[#151D20] shadow-black/30"
    : "border-[#DDE3E0] bg-white shadow-slate-900/5";
  const elevatedClass = isDark
    ? "border-[#2B373B] bg-[#1B2529] shadow-black/35"
    : "border-[#DDE3E0] bg-white shadow-slate-900/5";
  const mutedSurfaceClass = isDark ? "bg-[#202B2F]" : "bg-[#EEF3F1]";
  const secondaryTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const accentTextClass = isDark ? "text-[#63B3A7]" : "text-[#2F7D73]";
  const buttonClass = isDark
    ? "h-11 rounded-xl bg-[#63B3A7] px-5 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC]"
    : "h-11 rounded-xl bg-[#2F7D73] px-5 text-sm font-semibold text-white transition hover:bg-[#25675F]";
  const fullButtonClass = `${buttonClass} w-full`;
  const inputClass = isDark
    ? "mt-2 h-11 w-full rounded-xl border border-[#2B373B] bg-[#202B2F] px-3.5 text-sm text-[#F4F7F6] outline-none transition placeholder:text-[#6F7D80] focus:border-[#63B3A7] focus:ring-4 focus:ring-[#63B3A7]/20"
    : "mt-2 h-11 w-full rounded-xl border border-[#DDE3E0] bg-white px-3.5 text-sm text-[#172033] outline-none transition placeholder:text-[#98A2B3] focus:border-[#2F7D73] focus:ring-4 focus:ring-[#2F7D73]/15";

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
    const selectedPreferredLanguage = profileForm.preferred_language;
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

    if (selectedPreferredLanguage !== normalizeLanguage(profile.preferred_language)) {
      updates.preferred_language = selectedPreferredLanguage;
    }

    if (trimmedEducationLevel !== profile.education_level) {
      updates.education_level = trimmedEducationLevel;
    }

    if (!Object.keys(updates).length) {
      setProfileMessage(t("profile.noChanges"));
      setIsEditingProfile(false);
      return;
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
      const nextLanguage = setLanguageFromValue(data.preferred_language);
      setProfile(data);
      setEmail(data.email);
      localStorage.setItem("login_email", data.email);
      localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
      syncProfileForm(data);
      setIsEditingProfile(false);
      setProfileMessage(t("profile.updated"));
      await fetchProfile(token);
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
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    resetLanguage();
    router.replace("/login");
  }

  function showPrototypeMessage(label: string) {
    setStatusMessage(t("dashboard.prototypeMessage", { label }));
  }

  function renderSkillProgress() {
    return (
      <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
        <div className="mb-5">
          <h2 className="text-lg font-semibold tracking-tight">
            {t("dashboard.skillProgress")}
          </h2>
          <p className={`mt-1 text-sm ${secondaryTextClass}`}>
            {t("dashboard.skillProgressHelp")}
          </p>
        </div>

        <div className="space-y-5">
          {prototypeDashboardData.skillProgress.map((item) => (
            <div key={item.skillKey}>
              <div className="mb-2 flex items-center justify-between gap-4">
                <p className="text-sm font-semibold">{t(item.skillKey)}</p>
                <p className={`text-sm ${secondaryTextClass}`}>{item.value}%</p>
              </div>
              <div className={`h-3 rounded-full ${mutedSurfaceClass}`}>
                <div
                  className={`h-3 rounded-full ${
                    isDark ? "bg-[#63B3A7]" : "bg-[#2F7D73]"
                  }`}
                  style={{ width: `${item.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  function renderDashboardSection() {
    return (
      <>
        <AssessmentStatusCard
          status={assessmentStatus}
          result={assessmentResult}
          onStart={() => router.push("/assessment")}
          onViewResult={() => setActiveSection("progress")}
          isDark={isDark}
          t={t}
        />

        {assessmentError ? (
          <div className={`rounded-2xl border px-4 py-3 text-sm font-medium text-red-500 ${elevatedClass}`}>
            {assessmentError}
          </div>
        ) : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {prototypeDashboardData.summaryCards.map((card) => (
            <article
              key={card.labelKey}
              className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}
            >
              <p className={`text-sm font-medium ${secondaryTextClass}`}>
                {t(card.labelKey)}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-tight">
                {card.valueKey ? t(card.valueKey) : card.value}
              </p>
              <p className={`mt-2 text-sm ${accentTextClass}`}>
                {t(card.detailKey)}
              </p>
            </article>
          ))}
        </section>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          {renderSkillProgress()}

          <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
            <p className={`text-sm font-semibold ${accentTextClass}`}>
              {t("dashboard.recommendedActivity")}
            </p>
            <h2 className="mt-3 text-xl font-semibold tracking-tight">
              {t("dashboard.readAndMatch")}
            </h2>
            <p className={`mt-3 text-sm leading-6 ${secondaryTextClass}`}>
              {t("dashboard.readAndMatchDescription")}
            </p>
            <div
              className={`mt-4 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${mutedSurfaceClass} ${accentTextClass}`}
            >
              {t("dashboard.beginner")} · 12 min
            </div>
            <button
              type="button"
              onClick={() => showPrototypeMessage(t("dashboard.readAndMatch"))}
              className={`mt-6 ${fullButtonClass}`}
            >
              {t("dashboard.startActivity")}
            </button>
          </section>
        </div>

        <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
          <h2 className="text-lg font-semibold tracking-tight">
            {t("dashboard.recentActivity")}
          </h2>
          <div className={`mt-4 divide-y ${isDark ? "divide-[#2B373B]" : "divide-[#DDE3E0]"}`}>
            {prototypeDashboardData.recentActivities.map((activity, index) => (
              <div
                key={activity}
                className="flex flex-col gap-1 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className="text-sm font-medium">{t(activity)}</p>
                <p className={`text-sm ${secondaryTextClass}`}>
                  {t("dashboard.sessionCompleted", { number: index + 1 })}
                </p>
              </div>
            ))}
          </div>
        </section>
      </>
    );
  }

  function renderLearningActivitiesSection() {
    return (
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {prototypeDashboardData.learningActivities.map((activity) => (
          <article
            key={activity.titleKey}
            className={`flex flex-col rounded-2xl border p-5 shadow-xl ${elevatedClass}`}
          >
            <h2 className="text-lg font-semibold tracking-tight">
              {t(activity.titleKey)}
            </h2>
            <p className={`mt-3 flex-1 text-sm leading-6 ${secondaryTextClass}`}>
              {t(activity.descriptionKey)}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${mutedSurfaceClass} ${accentTextClass}`}
              >
                {t(activity.difficultyKey)}
              </span>
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${mutedSurfaceClass} ${secondaryTextClass}`}
              >
                {activity.duration}
              </span>
            </div>
            <button
              type="button"
              onClick={() => showPrototypeMessage(t(activity.titleKey))}
              className={`mt-6 ${fullButtonClass}`}
            >
              {t("dashboard.start")}
            </button>
          </article>
        ))}
      </section>
    );
  }

  function renderProgressSection() {
    return (
      <>
        <AssessmentStatusCard
          status={assessmentStatus}
          result={assessmentResult}
          onStart={() => router.push("/assessment")}
          isDark={isDark}
          t={t}
        />

        {assessmentResult ? (
          <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
            <h2 className="text-lg font-semibold tracking-tight">
              {t("assessment.result")}
            </h2>
            <div className={`mt-4 divide-y ${isDark ? "divide-[#2B373B]" : "divide-[#DDE3E0]"}`}>
              {[
                [t("assessment.readingScore"), `${assessmentResult.reading_score}%`],
                [t("assessment.typingScore"), `${assessmentResult.typing_score}%`],
                [t("assessment.mcqScore"), `${assessmentResult.mcq_score}%`],
                [t("assessment.overallScore"), `${assessmentResult.overall_score}%`],
                [
                  t("assessment.currentLevel"),
                  t(`assessment.level.${assessmentResult.proficiency_level}` as TranslationKey),
                ],
                [
                  t("assessment.completedOn"),
                  new Date(assessmentResult.completed_at).toLocaleDateString(),
                ],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4 py-3 text-sm">
                  <span className={secondaryTextClass}>{label}</span>
                  <span className="font-semibold">{value}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {prototypeDashboardData.summaryCards.map((card) => (
            <article
              key={card.labelKey}
              className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}
            >
              <p className={`text-sm font-medium ${secondaryTextClass}`}>
                {t(card.labelKey)}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-tight">
                {card.valueKey ? t(card.valueKey) : card.value}
              </p>
              <p className={`mt-2 text-sm ${accentTextClass}`}>
                {t("common.prototypeData")}
              </p>
            </article>
          ))}
        </section>
        {renderSkillProgress()}
      </>
    );
  }

  function renderResourcesSection() {
    return (
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {prototypeDashboardData.resources.map((resource) => (
          <article
            key={resource.titleKey}
            className={`flex flex-col rounded-2xl border p-5 shadow-xl ${elevatedClass}`}
          >
            <h2 className="text-lg font-semibold tracking-tight">
              {t(resource.titleKey)}
            </h2>
            <p className={`mt-3 flex-1 text-sm leading-6 ${secondaryTextClass}`}>
              {t(resource.descriptionKey)}
            </p>
            <button
              type="button"
              onClick={() => showPrototypeMessage(t(resource.titleKey))}
              className={`mt-6 ${fullButtonClass}`}
            >
              {t("dashboard.viewResource")}
            </button>
          </article>
        ))}
      </section>
    );
  }

  function renderProfileSection() {
    if (isProfileLoading) {
      return (
        <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
          <p className={`text-sm font-semibold ${accentTextClass}`}>
            {t("profile.accountDetails")}
          </p>
          <p className={`mt-3 text-sm ${secondaryTextClass}`}>
            {t("profile.loading")}
          </p>
        </section>
      );
    }

    if (profileError && !profile) {
      return (
        <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
          <p className={`text-sm font-semibold ${accentTextClass}`}>
            {t("profile.accountDetails")}
          </p>
          <p className="mt-3 text-sm font-medium text-red-500">{profileError}</p>
          <button
            type="button"
            onClick={() => fetchProfile()}
            className={`mt-6 ${buttonClass}`}
          >
            {t("common.retry")}
          </button>
        </section>
      );
    }

    if (!profile) {
      return (
        <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
          <p className={`text-sm font-semibold ${accentTextClass}`}>
            {t("profile.accountDetails")}
          </p>
          <p className={`mt-3 text-sm ${secondaryTextClass}`}>
            {t("profile.notAvailable")}
          </p>
        </section>
      );
    }

    return (
      <section className={`rounded-2xl border p-5 shadow-xl ${elevatedClass}`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className={`text-sm font-semibold ${accentTextClass}`}>
              {t("profile.accountDetails")}
            </p>
            <h2 className="mt-3 text-xl font-semibold tracking-tight">
              {t("profile.yourProfile")}
            </h2>
          </div>
          {!isEditingProfile ? (
            <button
              type="button"
              onClick={beginProfileEdit}
              className={buttonClass}
            >
              {t("profile.editProfile")}
            </button>
          ) : null}
        </div>

        {profileMessage ? (
          <div
            className={`mt-5 rounded-xl border px-4 py-3 text-sm font-medium ${
              isDark
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}
          >
            {profileMessage}
          </div>
        ) : null}

        {profileError ? (
          <div
            className={`mt-5 rounded-xl border px-4 py-3 text-sm font-medium ${
              isDark
                ? "border-red-500/35 bg-red-500/10 text-red-200"
                : "border-red-200 bg-red-50 text-red-800"
            }`}
          >
            {profileError}
          </div>
        ) : null}

        {isEditingProfile ? (
          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="block md:col-span-2">
              <span className="text-sm font-medium">{t("common.fullName")}</span>
              <input
                type="text"
                value={profileForm.full_name}
                onChange={(event) =>
                  setProfileForm({
                    ...profileForm,
                    full_name: event.target.value,
                  })
                }
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium">{t("common.age")}</span>
              <input
                type="number"
                min="1"
                value={profileForm.age}
                onChange={(event) =>
                  setProfileForm({ ...profileForm, age: event.target.value })
                }
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium">{t("common.email")}</span>
              <input
                type="email"
                value={profileForm.email}
                onChange={(event) =>
                  setProfileForm({ ...profileForm, email: event.target.value })
                }
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium">
                {t("common.preferredLanguage")}
              </span>
              <select
                value={profileForm.preferred_language}
                onChange={(event) =>
                  setProfileForm({
                    ...profileForm,
                    preferred_language: event.target.value as LanguageCode,
                  })
                }
                className={inputClass}
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm font-medium">
                {t("common.educationLevel")}
              </span>
              <input
                type="text"
                value={profileForm.education_level}
                onChange={(event) =>
                  setProfileForm({
                    ...profileForm,
                    education_level: event.target.value,
                  })
                }
                className={inputClass}
              />
            </label>

            <div className="flex flex-col gap-3 md:col-span-2 sm:flex-row">
              <button
                type="button"
                onClick={handleProfileSave}
                disabled={isSavingProfile}
                className={buttonClass}
              >
                {isSavingProfile ? t("profile.saving") : t("profile.saveChanges")}
              </button>
              <button
                type="button"
                onClick={cancelProfileEdit}
                disabled={isSavingProfile}
                className={`h-11 rounded-xl border px-5 text-sm font-semibold transition ${
                  isDark
                    ? "border-[#2B373B] text-[#F4F7F6] hover:bg-[#202B2F]"
                    : "border-[#DDE3E0] text-[#172033] hover:bg-[#EEF3F1]"
                }`}
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        ) : (
          <div
            className={`mt-5 divide-y ${
              isDark ? "divide-[#2B373B]" : "divide-[#DDE3E0]"
            }`}
          >
            {[
              [t("profile.userId"), String(profile.id)],
              [t("common.fullName"), profile.full_name],
              [t("common.email"), profile.email],
              [t("common.age"), String(profile.age)],
              [
                t("common.preferredLanguage"),
                LANGUAGE_OPTIONS.find(
                  (option) =>
                    option.code === normalizeLanguage(profile.preferred_language),
                )?.label || profile.preferred_language,
              ],
              [t("common.educationLevel"), profile.education_level],
              [t("common.role"), t(`option.role.${profile.role}` as TranslationKey)],
              [
                t("assessment.status"),
                assessmentResult
                  ? t("assessment.completed")
                  : assessmentStatus?.has_in_progress_attempt
                    ? t("assessment.inProgress")
                    : t("assessment.notCompleted"),
              ],
              [
                t("assessment.currentLevel"),
                assessmentResult
                  ? t(`assessment.level.${assessmentResult.proficiency_level}` as TranslationKey)
                  : t("common.notAvailable"),
              ],
              [
                t("assessment.completedOn"),
                assessmentResult
                  ? new Date(assessmentResult.completed_at).toLocaleDateString()
                  : t("common.notAvailable"),
              ],
              [t("profile.sessionStatus"), t("common.signedIn")],
            ].map(([label, value]) => (
              <div
                key={label}
                className="flex flex-col gap-1 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className={`text-sm font-medium ${secondaryTextClass}`}>
                  {label}
                </p>
                <p className="text-sm font-semibold">{value}</p>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={handleLogout}
          className={`mt-6 ${buttonClass}`}
        >
          {t("common.logout")}
        </button>
      </section>
    );
  }

  function renderActiveSection() {
    if (activeSection === "learningActivities") {
      return renderLearningActivitiesSection();
    }

    if (activeSection === "progress") {
      return renderProgressSection();
    }

    if (activeSection === "resources") {
      return renderResourcesSection();
    }

    if (activeSection === "profile") {
      return renderProfileSection();
    }

    return renderDashboardSection();
  }

  if (isCheckingAuth) {
    return <main className={pageClass} />;
  }

  return (
    <main className={`${pageClass} transition-colors`}>
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-5 lg:grid lg:grid-cols-[240px_1fr] lg:px-8 lg:py-8">
        <aside
          className={`rounded-2xl border p-4 shadow-xl lg:min-h-[calc(100vh-4rem)] ${panelClass}`}
        >
          <div className="mb-5">
            <p className={`text-sm font-semibold ${accentTextClass}`}>
              {t("common.appName")}
            </p>
            <p className={`mt-1 text-xs ${secondaryTextClass}`}>
              {t("common.dashboard")}
            </p>
          </div>

          <nav className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {navItems.map((item) => {
              const isActive = item.id === activeSection;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveSection(item.id);
                    setStatusMessage("");
                  }}
                  aria-pressed={isActive}
                  className={`whitespace-nowrap rounded-xl px-3 py-2 text-left text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                    isActive
                      ? isDark
                        ? "bg-[#63B3A7] text-[#0F1517] focus:ring-[#63B3A7]/20"
                        : "bg-[#2F7D73] text-white focus:ring-[#2F7D73]/15"
                      : isDark
                        ? "text-[#A8B3B0] hover:bg-[#202B2F] hover:text-[#F4F7F6] focus:ring-[#63B3A7]/20"
                        : "text-[#667085] hover:bg-[#EEF3F1] hover:text-[#172033] focus:ring-[#2F7D73]/15"
                  }`}
                >
                  {t(item.labelKey)}
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="space-y-5">
          <header
            className={`flex flex-col gap-4 rounded-2xl border p-5 shadow-xl sm:flex-row sm:items-center sm:justify-between ${elevatedClass}`}
          >
            <div>
              <p className={`text-sm font-semibold ${accentTextClass}`}>
                {t(navItems.find((item) => item.id === activeSection)?.labelKey || "common.dashboard")}
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                {activeSection === "dashboard"
                  ? t("dashboard.title")
                  : t(navItems.find((item) => item.id === activeSection)?.labelKey || "common.dashboard")}
              </h1>
              <p className={`mt-2 text-sm leading-6 ${secondaryTextClass}`}>
                {email
                  ? `${t("dashboard.signedInAs")} ${email}`
                  : t("dashboard.signedInGeneric")}
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={
                  theme === "dark"
                    ? t("common.switchToLight")
                    : t("common.switchToDark")
                }
                className={`inline-flex h-10 items-center justify-center gap-2 rounded-full border px-3 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                  isDark
                    ? "border-[#2B373B] bg-[#1B2529] text-[#F4F7F6] hover:bg-[#202B2F] focus:ring-[#63B3A7]/20"
                    : "border-[#DDE3E0] bg-white text-[#172033] hover:bg-[#EEF3F1] focus:ring-[#2F7D73]/15"
                }`}
              >
                <span>{theme === "dark" ? t("common.light") : t("common.dark")}</span>
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className={buttonClass}
              >
                {t("common.logout")}
              </button>
            </div>
          </header>

          {statusMessage ? (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm font-medium ${elevatedClass}`}
            >
              {statusMessage}
            </div>
          ) : null}

          {renderActiveSection()}
        </section>
      </div>
    </main>
  );
}
