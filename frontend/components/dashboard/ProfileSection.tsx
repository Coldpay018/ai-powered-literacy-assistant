"use client";

import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import { LANGUAGE_OPTIONS, normalizeLanguage, type LanguageCode } from "@/lib/i18n/types";
import type { TranslationKey } from "@/lib/i18n/translations";
import type {
  AssessmentState,
  ExperienceLevel,
  ProfileForm,
  Translate,
  UserProfile,
} from "./types";

const experienceOptions = ["Beginner", "Intermediate", "Advanced"] as const;

type ProfileSectionProps = AssessmentState & {
  profile: UserProfile | null;
  profileForm: ProfileForm;
  isProfileLoading: boolean;
  isEditingProfile: boolean;
  isSavingProfile: boolean;
  profileError: string;
  profileMessage: string;
  isDark: boolean;
  t: Translate;
  onRetryProfile: () => void;
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onSaveProfile: () => void;
  onLogout: () => void;
  onProfileFormChange: (form: ProfileForm) => void;
  completionMode?: boolean;
};

export function ProfileSection({
  profile,
  profileForm,
  isProfileLoading,
  isEditingProfile,
  isSavingProfile,
  profileError,
  profileMessage,
  assessmentStatus,
  assessmentResult,
  isDark,
  t,
  onRetryProfile,
  onBeginEdit,
  onCancelEdit,
  onSaveProfile,
  onLogout,
  onProfileFormChange,
  completionMode = false,
}: ProfileSectionProps) {
  const cardClass = isDark
    ? "rounded-3xl border border-white/10 bg-[#0D1D2F]/82 p-5 shadow-2xl shadow-black/20"
    : "rounded-3xl border border-[#DDEAE5] bg-white/92 p-5 shadow-xl shadow-slate-900/6";
  const inputClass = isDark
    ? "mt-2 h-12 w-full rounded-2xl border border-white/10 bg-white/8 px-4 text-sm text-white outline-none transition placeholder:text-white/35 focus:border-[#63D8C8] focus:ring-4 focus:ring-[#63D8C8]/15"
    : "mt-2 h-12 w-full rounded-2xl border border-[#DDEAE5] bg-white px-4 text-sm text-[#07192F] outline-none transition placeholder:text-[#98A2B3] focus:border-[#0F766E] focus:ring-4 focus:ring-[#14B8A6]/15";

  if (isProfileLoading) {
    return (
      <section className={cardClass}>
        <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>{t("profile.accountDetails")}</p>
        <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("profile.loading")}</p>
      </section>
    );
  }

  if (profileError && !profile) {
    return (
      <section className={cardClass}>
        <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>{t("profile.accountDetails")}</p>
        <p className="mt-3 text-sm font-bold text-red-500">{profileError}</p>
        <button type="button" onClick={onRetryProfile} className="mt-6 rounded-2xl bg-[#0F766E] px-5 py-3 text-sm font-black text-white">
          {t("common.retry")}
        </button>
      </section>
    );
  }

  if (!profile) {
    return (
      <section className={cardClass}>
        <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>{t("profile.accountDetails")}</p>
        <p className={isDark ? "mt-3 text-sm text-teal-50/66" : "mt-3 text-sm text-[#60746F]"}>{t("profile.notAvailable")}</p>
      </section>
    );
  }

  const initials = profile.full_name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "U";
  const status = assessmentResult
    ? t("assessment.completed")
    : assessmentStatus?.has_in_progress_attempt
      ? t("assessment.inProgress")
      : t("assessment.notCompleted");
  const level = assessmentResult
    ? t(`assessment.level.${assessmentResult.proficiency_level}` as TranslationKey)
    : t("common.notAvailable");
  const experienceLabel = (value: string | null) =>
    value
      ? t(`assessment.level.${value.toLowerCase()}` as TranslationKey)
      : t("common.notAvailable");
  const languageLabel = (value: string | null) =>
    value
      ? LANGUAGE_OPTIONS.find((option) => option.code === normalizeLanguage(value))?.label || value
      : t("common.notAvailable");

  const rows: Array<[string, string]> = [
    [t("common.fullName"), profile.full_name],
    [t("common.email"), profile.email],
    [t("common.age"), String(profile.age)],
    [t("common.comfortableLanguage"), languageLabel(profile.comfortable_language)],
    [t("common.learningLanguage"), languageLabel(profile.learning_language)],
    [t("common.experienceLevel"), experienceLabel(profile.experience_level)],
    [t("common.educationLevel"), profile.education_level],
    [t("common.role"), t(`option.role.${profile.role}` as TranslationKey)],
    [t("assessment.status"), status],
    [t("assessment.currentLevel"), level],
  ];

  return (
    <div className="space-y-5">
      <section className={cardClass}>
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="grid h-20 w-20 place-items-center rounded-[1.6rem] bg-gradient-to-br from-[#D9F6EF] to-[#14B8A6] text-2xl font-black text-[#07192F] shadow-lg shadow-teal-950/10">
              {initials}
            </div>
            <div>
              <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>{t("common.appName")}</p>
              <h2 className="mt-1 text-2xl font-black tracking-normal">{profile.full_name}</h2>
              <p className={isDark ? "mt-1 text-sm text-teal-50/62" : "mt-1 text-sm text-[#60746F]"}>{profile.email}</p>
            </div>
          </div>
          {!isEditingProfile && !completionMode ? (
            <button type="button" onClick={onBeginEdit} className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white">
              {t("profile.editProfile")}
            </button>
          ) : null}
        </div>
      </section>

      {profileMessage ? (
        <div className={isDark ? "rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-bold text-emerald-200" : "rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800"}>
          {profileMessage}
        </div>
      ) : null}

      {profileError ? (
        <div className={isDark ? "rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-200" : "rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700"}>
          {profileError}
        </div>
      ) : null}

      {isEditingProfile || completionMode ? (
        <section className={cardClass}>
          {completionMode ? (
            <div className="mb-5">
              <p className={isDark ? "text-sm font-black text-[#63D8C8]" : "text-sm font-black text-[#0F766E]"}>
                {t("profile.completeTitle")}
              </p>
              <p className={isDark ? "mt-2 text-sm leading-6 text-teal-50/66" : "mt-2 text-sm leading-6 text-[#60746F]"}>
                {t("profile.completeHelp")}
              </p>
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {!completionMode ? (
              <label className="block md:col-span-2">
              <span className="text-sm font-bold">{t("common.fullName")}</span>
              <input
                type="text"
                value={profileForm.full_name}
                onChange={(event) => onProfileFormChange({ ...profileForm, full_name: event.target.value })}
                className={inputClass}
              />
              </label>
            ) : null}
            {!completionMode ? (
              <label className="block">
              <span className="text-sm font-bold">{t("common.age")}</span>
              <input
                type="number"
                min="1"
                value={profileForm.age}
                onChange={(event) => onProfileFormChange({ ...profileForm, age: event.target.value })}
                className={inputClass}
              />
              </label>
            ) : null}
            {!completionMode ? (
              <label className="block">
              <span className="text-sm font-bold">{t("common.email")}</span>
              <input
                type="email"
                value={profileForm.email}
                onChange={(event) => onProfileFormChange({ ...profileForm, email: event.target.value })}
                className={inputClass}
              />
              </label>
            ) : null}
            <label className="block">
              <span className="text-sm font-bold">{t("common.comfortableLanguage")}</span>
              <select
                value={profileForm.comfortable_language}
                onChange={(event) => {
                  const comfortableLanguage = event.target.value as LanguageCode;
                  onProfileFormChange({
                    ...profileForm,
                    comfortable_language: comfortableLanguage,
                    learning_language:
                      profileForm.learning_language && profileForm.learning_language === comfortableLanguage
                        ? LANGUAGE_OPTIONS.find((option) => option.code !== comfortableLanguage)?.code || "en"
                        : profileForm.learning_language,
                  });
                }}
                className={inputClass}
              >
                <option value="" disabled>
                  {t("profile.selectOption")}
                </option>
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-bold">{t("common.learningLanguage")}</span>
              <select
                value={profileForm.learning_language}
                onChange={(event) =>
                  onProfileFormChange({
                    ...profileForm,
                    learning_language: event.target.value as LanguageCode,
                  })
                }
                className={inputClass}
              >
                <option value="" disabled>
                  {t("profile.selectOption")}
                </option>
                {LANGUAGE_OPTIONS.filter(
                  (option) => option.code !== profileForm.comfortable_language,
                ).map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-bold">{t("common.experienceLevel")}</span>
              <select
                value={profileForm.experience_level}
                onChange={(event) =>
                  onProfileFormChange({
                    ...profileForm,
                    experience_level: event.target.value as ExperienceLevel,
                  })
                }
                className={inputClass}
              >
                <option value="" disabled>
                  {t("profile.selectOption")}
                </option>
                {experienceOptions.map((levelOption) => (
                  <option key={levelOption} value={levelOption}>
                    {t(`assessment.level.${levelOption.toLowerCase()}` as TranslationKey)}
                  </option>
                ))}
              </select>
            </label>
            {!completionMode ? (
              <label className="block">
                <span className="text-sm font-bold">{t("common.educationLevel")}</span>
                <input
                  type="text"
                  value={profileForm.education_level}
                  onChange={(event) => onProfileFormChange({ ...profileForm, education_level: event.target.value })}
                  className={inputClass}
                />
              </label>
            ) : null}
          </div>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={onSaveProfile}
              disabled={isSavingProfile}
              className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSavingProfile ? t("profile.saving") : t("profile.saveChanges")}
            </button>
            <button
              type="button"
              onClick={onCancelEdit}
              disabled={isSavingProfile}
              className={`${completionMode ? "hidden" : ""} ${isDark ? "rounded-2xl border border-white/10 px-5 py-3 text-sm font-black text-white transition hover:bg-white/8" : "rounded-2xl border border-[#DDEAE5] bg-white px-5 py-3 text-sm font-black text-[#07192F] transition hover:bg-[#F7FBFA]"}`}
            >
              {t("common.cancel")}
            </button>
          </div>
        </section>
      ) : (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {rows.map(([label, value]) => (
            <article key={label} className={cardClass}>
              <div className="flex items-center gap-3">
                <span className={isDark ? "grid h-10 w-10 place-items-center rounded-xl bg-white/8" : "grid h-10 w-10 place-items-center rounded-xl bg-[#E9F8F4]"}>
                  <LiteracyIcon name="profile" className="h-6 w-6" />
                </span>
                <div className="min-w-0">
                  <p className={isDark ? "text-xs font-black text-teal-50/55" : "text-xs font-black text-[#60746F]"}>{label}</p>
                  <p className="mt-1 truncate text-sm font-black">{value}</p>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}

      <button
        type="button"
        onClick={onLogout}
        className={isDark ? "rounded-2xl border border-white/10 px-5 py-3 text-sm font-black text-white transition hover:bg-white/8" : "rounded-2xl border border-[#DDEAE5] bg-white px-5 py-3 text-sm font-black text-[#07192F] transition hover:bg-[#F7FBFA]"}
      >
        {t("common.logout")}
      </button>
    </div>
  );
}
