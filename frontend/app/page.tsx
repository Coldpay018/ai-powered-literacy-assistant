"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/LanguageProvider";
import {
  LANGUAGE_OPTIONS,
  LANGUAGE_STORAGE_KEY,
  type LanguageCode,
} from "@/lib/i18n/types";
import { getAssessmentStatus } from "@/lib/assessment/api";

const API_BASE_URL = "http://127.0.0.1:8000";

const educationOptions = [
  { value: "No formal education", labelKey: "option.education.none" },
  { value: "Primary", labelKey: "option.education.primary" },
  { value: "Secondary", labelKey: "option.education.secondary" },
  { value: "Higher Secondary", labelKey: "option.education.higherSecondary" },
  { value: "Undergraduate", labelKey: "option.education.undergraduate" },
  { value: "Graduate", labelKey: "option.education.graduate" },
] as const;

const roleOptions = [
  { value: "learner", labelKey: "option.role.learner" },
  { value: "educator", labelKey: "option.role.educator" },
  { value: "administrator", labelKey: "option.role.administrator" },
] as const;

type ActiveTab = "login" | "register";
type Theme = "light" | "dark";

type RegisterForm = {
  full_name: string;
  age: string;
  email: string;
  password: string;
  preferred_language: string;
  education_level: string;
  role: string;
};

type LoginForm = {
  email: string;
  password: string;
};

type UserProfile = {
  preferred_language?: string;
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

export default function Home() {
  const router = useRouter();
  const { language, setLanguage, setLanguageFromValue, resetLanguage, t } =
    useLanguage();
  const [activeTab, setActiveTab] = useState<ActiveTab>("login");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loggedInEmail, setLoggedInEmail] = useState("");
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");

  const [registerForm, setRegisterForm] = useState<RegisterForm>({
    full_name: "",
    age: "",
    email: "",
    password: "",
    preferred_language: "en",
    education_level: "Primary",
    role: "learner",
  });

  const [loginForm, setLoginForm] = useState<LoginForm>({
    email: "",
    password: "",
  });

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
    queueMicrotask(() => {
      setRegisterForm((previous) => ({
        ...previous,
        preferred_language: language,
      }));
    });
  }, [language]);

  const isDark = theme === "dark";

  const pageClass = isDark
    ? "min-h-screen bg-[#0F1517] text-[#F4F7F6]"
    : "min-h-screen bg-[#F5F7F6] text-[#172033]";
  const panelClass = isDark
    ? "border-[#2B373B] bg-[#151D20] shadow-black/35"
    : "border-[#DDE3E0] bg-white shadow-slate-900/8";
  const elevatedClass = isDark
    ? "border-[#2B373B] bg-[#151D20] shadow-black/35"
    : "border-[#DDE3E0] bg-white shadow-slate-900/10";
  const mutedSurfaceClass = isDark ? "bg-[#202B2F]" : "bg-[#EEF3F1]";
  const primaryTextClass = isDark ? "text-[#F4F7F6]" : "text-[#172033]";
  const secondaryTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const accentTextClass = isDark ? "text-[#63B3A7]" : "text-[#2F7D73]";
  const borderClass = isDark ? "border-[#2B373B]" : "border-[#DDE3E0]";
  const inputClass = isDark
    ? "mt-2 h-12 w-full rounded-xl border border-[#2B373B] bg-[#202B2F] px-4 text-sm text-[#F4F7F6] outline-none transition placeholder:text-[#6F7D80] hover:border-[#3A494D] focus:border-[#63B3A7] focus:ring-4 focus:ring-[#63B3A7]/20"
    : "mt-2 h-12 w-full rounded-xl border border-[#DDE3E0] bg-white px-4 text-sm text-[#172033] outline-none transition placeholder:text-[#98A2B3] hover:border-[#C7D1CD] focus:border-[#2F7D73] focus:ring-4 focus:ring-[#2F7D73]/15";
  const labelClass = `text-sm font-medium ${primaryTextClass}`;
  const buttonClass = isDark
    ? "h-12 w-full rounded-xl bg-[#63B3A7] px-5 text-sm font-semibold text-[#0F1517] shadow-lg shadow-[#63B3A7]/10 transition hover:bg-[#79C7BC] focus:outline-none focus:ring-4 focus:ring-[#63B3A7]/20 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
    : "h-12 w-full rounded-xl bg-[#2F7D73] px-5 text-sm font-semibold text-white shadow-lg shadow-[#2F7D73]/15 transition hover:bg-[#25675F] focus:outline-none focus:ring-4 focus:ring-[#2F7D73]/15 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60";
  const benefitKeys = [
    "auth.benefitLanguage",
    "auth.benefitPath",
    "auth.benefitProgress",
  ] as const;

  function clearStatus() {
    setMessage("");
    setError("");
  }

  function switchTab(tab: ActiveTab) {
    setActiveTab(tab);
    clearStatus();
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", nextTheme);
    setTheme(nextTheme);
  }

  function mapApiError(message: string) {
    if (message.includes("Invalid email or password")) {
      return t("auth.invalidCredentials");
    }

    if (message.includes("Email is already registered")) {
      return t("auth.emailRegistered");
    }

    if (message.includes("Unsupported language")) {
      return t("auth.genericError");
    }

    if (message) {
      return message;
    }

    return t("auth.genericError");
  }

  function handleLanguageChange(event: ChangeEvent<HTMLSelectElement>) {
    const selectedLanguage = event.target.value as LanguageCode;

    setRegisterForm((previous) => ({
      ...previous,
      preferred_language: selectedLanguage,
    }));
    setLanguage(selectedLanguage);
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearStatus();
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...registerForm,
          age: Number(registerForm.age),
        }),
      });

      if (!response.ok) {
        setError(mapApiError(await readErrorMessage(response)));
        return;
      }

      const selectedLanguage = registerForm.preferred_language as LanguageCode;
      setLanguage(selectedLanguage);
      setMessage(t("auth.registrationSuccessful"));
      setActiveTab("login");
      setLoginForm({
        email: registerForm.email,
        password: "",
      });
      setRegisterForm({
        full_name: "",
        age: "",
        email: "",
        password: "",
        preferred_language: selectedLanguage,
        education_level: "Primary",
        role: "learner",
      });
      router.push("/login");
    } catch {
      setError(t("auth.backendUnavailable"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearStatus();
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(loginForm),
      });

      if (!response.ok) {
        setError(mapApiError(await readErrorMessage(response)));
        return;
      }

      const data = (await response.json()) as { access_token: string };
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("login_email", loginForm.email);
      try {
        const profileResponse = await fetch(`${API_BASE_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${data.access_token}`,
          },
        });

        if (profileResponse.ok) {
          const profile = (await profileResponse.json()) as UserProfile;
          setLanguageFromValue(profile.preferred_language);
        }
      } catch {
        console.warn("Could not load profile language after login.");
      }

      try {
        const assessmentStatus = await getAssessmentStatus(data.access_token);
        setLoggedInEmail(loginForm.email);
        setMessage(t("auth.loginSuccessful"));
        if (assessmentStatus.required || assessmentStatus.has_in_progress_attempt) {
          router.push("/assessment");
          return;
        }
        router.push("/dashboard");
        return;
      } catch (caught) {
        console.error(caught);
        setError(t("assessment.statusError"));
        return;
      }
    } catch {
      setError(t("auth.backendUnavailable"));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    resetLanguage();
    setLoggedInEmail("");
    setLoginForm({ email: "", password: "" });
    setRegisterForm((previous) => ({
      ...previous,
      preferred_language: "en",
    }));
    setActiveTab("login");
    setMessage("");
    setError("");
  }

  if (!mounted) {
    return <main className="min-h-screen bg-[#F5F7F6]" />;
  }

  const themeToggle = (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={
        theme === "dark" ? t("common.switchToLight") : t("common.switchToDark")
      }
      className={`inline-flex h-10 items-center gap-2 rounded-full border px-3 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
        isDark
          ? "border-[#2B373B] bg-[#1B2529] text-[#F4F7F6] hover:bg-[#202B2F] focus:ring-[#63B3A7]/20"
          : "border-[#DDE3E0] bg-white text-[#172033] hover:bg-[#EEF3F1] focus:ring-[#2F7D73]/15"
      }`}
    >
      <span>{theme === "dark" ? t("common.light") : t("common.dark")}</span>
    </button>
  );

  if (loggedInEmail) {
    return (
      <main className={`${pageClass} px-5 py-6 transition-colors`}>
        <div className="mx-auto flex max-w-4xl justify-end">{themeToggle}</div>
        <section className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-4xl items-center justify-center">
          <div
            className={`w-full max-w-md rounded-3xl border p-8 shadow-xl ${elevatedClass}`}
          >
            <div
              className={`mb-6 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${
                isDark
                  ? "bg-[#202B2F] text-[#63B3A7]"
                  : "bg-[#EEF3F1] text-[#2F7D73]"
              }`}
            >
              {t("auth.loginSuccessful")}
            </div>
            <h1 className={`text-2xl font-semibold tracking-tight ${primaryTextClass}`}>
              {t("auth.welcomeBack")}
            </h1>
            <p className={`mt-3 text-base leading-7 ${secondaryTextClass}`}>
              {t("auth.signedInAs")}{" "}
              <span className={`font-semibold ${primaryTextClass}`}>
                {loggedInEmail}
              </span>
              .
            </p>
            <button type="button" onClick={handleLogout} className={`mt-8 ${buttonClass}`}>
              {t("common.logout")}
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={`${pageClass} transition-colors`}>
      <div className="mx-auto flex max-w-6xl justify-end px-4 pt-4 sm:px-6 md:px-8">
        {themeToggle}
      </div>

      <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl grid-cols-1 gap-4 px-4 py-5 sm:px-6 md:px-8 lg:grid-cols-[0.42fr_0.58fr] lg:items-center lg:gap-5 lg:py-7">
        <div
          className={`overflow-hidden rounded-3xl border p-5 shadow-2xl sm:p-6 lg:min-h-[580px] lg:p-8 ${panelClass}`}
        >
          <div className="flex h-full flex-col justify-between gap-6">
            <div>
              <p className={`text-sm font-semibold ${accentTextClass}`}>
                {t("common.platform")}
              </p>
              <h1
                className={`mt-4 max-w-md text-3xl font-semibold leading-tight tracking-tight sm:text-4xl ${primaryTextClass}`}
              >
                {t("auth.heroHeading")}
              </h1>
              <p className={`mt-2 text-sm font-semibold ${accentTextClass}`}>
                {t("common.appName")}
              </p>
              <p className={`mt-4 max-w-md text-base leading-7 ${secondaryTextClass}`}>
                {t("auth.heroDescription")}
              </p>
              <ul className="mt-5 space-y-3">
                {benefitKeys.map((key) => (
                  <li key={key} className="flex gap-3 text-sm leading-6">
                    <span
                      aria-hidden="true"
                      className={`mt-2 h-2 w-2 shrink-0 rounded-full ${
                        isDark ? "bg-[#63B3A7]" : "bg-[#2F7D73]"
                      }`}
                    />
                    <span className={secondaryTextClass}>{t(key)}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-col items-center gap-3 pt-1">
              <div
                className={`flex w-full justify-center rounded-2xl py-4 ${
                  isDark ? "bg-[#202B2F]/45" : "bg-[#EEF3F1]/70"
                }`}
              >
                <Image
                  src="/assets/literacy-book.svg"
                  alt="Line-art open book with a glowing letter above it"
                  width={720}
                  height={520}
                  priority
                  className="h-auto w-full max-w-[300px] sm:max-w-[340px] lg:max-w-[360px]"
                />
              </div>
              <figure className={`px-2 text-center ${secondaryTextClass}`}>
                <blockquote className="text-sm italic leading-6">
                  &ldquo;{t("auth.quote")}&rdquo;
                </blockquote>
              </figure>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center">
          <section
            className={`w-full max-w-[500px] rounded-3xl border p-5 shadow-2xl sm:p-7 lg:p-8 ${elevatedClass}`}
          >
            <div
              className={`mb-4 grid grid-cols-2 rounded-2xl border p-1.5 ${borderClass} ${mutedSurfaceClass}`}
            >
              <button
                type="button"
                onClick={() => switchTab("login")}
                aria-pressed={activeTab === "login"}
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                  activeTab === "login"
                    ? isDark
                      ? "bg-[#63B3A7] text-[#0F1517] shadow-sm ring-1 ring-[#63B3A7]"
                      : "bg-[#2F7D73] text-white shadow-sm ring-1 ring-[#2F7D73]"
                    : isDark
                      ? "text-[#A8B3B0] hover:bg-[#1B2529] hover:text-[#F4F7F6] focus:ring-[#63B3A7]/20"
                      : "text-[#667085] hover:bg-white hover:text-[#172033] focus:ring-[#2F7D73]/15"
                }`}
              >
                {t("auth.login")}
              </button>
              <button
                type="button"
                onClick={() => switchTab("register")}
                aria-pressed={activeTab === "register"}
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                  activeTab === "register"
                    ? isDark
                      ? "bg-[#63B3A7] text-[#0F1517] shadow-sm ring-1 ring-[#63B3A7]"
                      : "bg-[#2F7D73] text-white shadow-sm ring-1 ring-[#2F7D73]"
                    : isDark
                      ? "text-[#A8B3B0] hover:bg-[#1B2529] hover:text-[#F4F7F6] focus:ring-[#63B3A7]/20"
                      : "text-[#667085] hover:bg-white hover:text-[#172033] focus:ring-[#2F7D73]/15"
                }`}
              >
                {t("auth.register")}
              </button>
            </div>

            <div className="mb-6">
              <h2 className={`text-2xl font-semibold tracking-tight sm:text-[28px] ${primaryTextClass}`}>
                {activeTab === "login"
                  ? t("auth.welcomeBack")
                  : t("auth.createAccount")}
              </h2>
              <p className={`mt-2 text-sm leading-6 ${secondaryTextClass}`}>
                {activeTab === "login"
                  ? t("auth.loginJourney")
                  : t("auth.registerJourney")}
              </p>
            </div>

            {message ? (
              <div
                className={`mb-5 rounded-2xl border px-4 py-3 text-sm font-medium ${
                  isDark
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                    : "border-emerald-200 bg-emerald-50 text-emerald-800"
                }`}
              >
                {message}
              </div>
            ) : null}

            {error ? (
              <div
                className={`mb-5 rounded-2xl border px-4 py-3 text-sm font-medium ${
                  isDark
                    ? "border-red-500/35 bg-red-500/10 text-red-200"
                    : "border-red-200 bg-red-50 text-red-800"
                }`}
              >
                {error}
              </div>
            ) : null}

            {activeTab === "login" ? (
              <form onSubmit={handleLogin} className="space-y-5">
                <label className="block">
                  <span className={labelClass}>{t("common.email")}</span>
                  <input
                    type="email"
                    value={loginForm.email}
                    onChange={(event) =>
                      setLoginForm({ ...loginForm, email: event.target.value })
                    }
                    required
                    className={inputClass}
                    placeholder={t("auth.emailPlaceholder")}
                  />
                </label>

                <label className="block">
                  <span className={labelClass}>{t("common.password")}</span>
                  <input
                    type="password"
                    value={loginForm.password}
                    onChange={(event) =>
                      setLoginForm({
                        ...loginForm,
                        password: event.target.value,
                      })
                    }
                    required
                    className={inputClass}
                    placeholder={t("auth.passwordPlaceholder")}
                  />
                </label>

                <button type="submit" disabled={isSubmitting} className={buttonClass}>
                  {isSubmitting ? t("auth.signingIn") : t("auth.loginButton")}
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-5">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <label className="block sm:col-span-2">
                    <span className={labelClass}>{t("common.fullName")}</span>
                    <input
                      type="text"
                      value={registerForm.full_name}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          full_name: event.target.value,
                        })
                      }
                      required
                      className={inputClass}
                      placeholder={t("auth.fullNamePlaceholder")}
                    />
                  </label>

                  <label className="block sm:col-span-2">
                    <span className={labelClass}>{t("common.email")}</span>
                    <input
                      type="email"
                      value={registerForm.email}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          email: event.target.value,
                        })
                      }
                      required
                      className={inputClass}
                      placeholder={t("auth.emailPlaceholder")}
                    />
                  </label>

                  <label className="block sm:col-span-2">
                    <span className={labelClass}>{t("common.password")}</span>
                    <input
                      type="password"
                      minLength={8}
                      value={registerForm.password}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          password: event.target.value,
                        })
                      }
                      required
                      className={inputClass}
                      placeholder={t("auth.passwordCreatePlaceholder")}
                    />
                  </label>

                  <label className="block">
                    <span className={labelClass}>{t("common.age")}</span>
                    <input
                      type="number"
                      min="1"
                      value={registerForm.age}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          age: event.target.value,
                        })
                      }
                      required
                      className={inputClass}
                      placeholder={t("auth.agePlaceholder")}
                    />
                  </label>

                  <label className="block">
                    <span className={labelClass}>{t("common.educationLevel")}</span>
                    <select
                      value={registerForm.education_level}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          education_level: event.target.value,
                        })
                      }
                      className={inputClass}
                    >
                      {educationOptions.map((level) => (
                        <option key={level.value} value={level.value}>
                          {t(level.labelKey)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className={labelClass}>{t("common.preferredLanguage")}</span>
                    <select
                      value={registerForm.preferred_language}
                      onChange={handleLanguageChange}
                      className={inputClass}
                    >
                      {LANGUAGE_OPTIONS.map((option) => (
                        <option key={option.code} value={option.code}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <span className={`mt-2 block text-xs leading-5 ${secondaryTextClass}`}>
                      {t("auth.languageHelper")}
                    </span>
                  </label>

                  <label className="block">
                    <span className={labelClass}>{t("common.role")}</span>
                    <select
                      value={registerForm.role}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          role: event.target.value,
                        })
                      }
                      className={inputClass}
                    >
                      {roleOptions.map((role) => (
                        <option key={role.value} value={role.value}>
                          {t(role.labelKey)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <button type="submit" disabled={isSubmitting} className={buttonClass}>
                  {isSubmitting ? t("auth.creatingAccount") : t("auth.registerButton")}
                </button>
              </form>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
