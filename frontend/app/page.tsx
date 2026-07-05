"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE_URL = "http://127.0.0.1:8000";

const languageOptions = [
  "English",
  "Hindi",
  "Tamil",
  "Telugu",
  "Bengali",
  "Marathi",
];

const educationOptions = [
  "No formal education",
  "Primary",
  "Secondary",
  "Higher Secondary",
  "Undergraduate",
  "Graduate",
];

const roleOptions = ["learner", "educator", "administrator"];

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
    return "Something went wrong. Please try again.";
  }

  return "Something went wrong. Please try again.";
}

export default function Home() {
  const router = useRouter();
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
    preferred_language: "English",
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

  const isDark = theme === "dark";

  const pageClass = isDark
    ? "min-h-screen bg-[#0F1517] text-[#F4F7F6]"
    : "min-h-screen bg-[#F5F7F6] text-[#172033]";
  const panelClass = isDark
    ? "border-[#2B373B] bg-[#151D20] shadow-black/30"
    : "border-[#DDE3E0] bg-white shadow-slate-900/5";
  const elevatedClass = isDark
    ? "border-[#2B373B] bg-[#1B2529] shadow-black/35"
    : "border-[#DDE3E0] bg-white shadow-slate-900/8";
  const mutedSurfaceClass = isDark ? "bg-[#202B2F]" : "bg-[#EEF3F1]";
  const primaryTextClass = isDark ? "text-[#F4F7F6]" : "text-[#172033]";
  const secondaryTextClass = isDark ? "text-[#A8B3B0]" : "text-[#667085]";
  const accentTextClass = isDark ? "text-[#63B3A7]" : "text-[#2F7D73]";
  const borderClass = isDark ? "border-[#2B373B]" : "border-[#DDE3E0]";
  const inputClass = isDark
    ? "mt-2 h-11 w-full rounded-xl border border-[#2B373B] bg-[#202B2F] px-3.5 text-sm text-[#F4F7F6] outline-none transition placeholder:text-[#6F7D80] focus:border-[#63B3A7] focus:ring-4 focus:ring-[#63B3A7]/20"
    : "mt-2 h-11 w-full rounded-xl border border-[#DDE3E0] bg-white px-3.5 text-sm text-[#172033] outline-none transition placeholder:text-[#98A2B3] focus:border-[#2F7D73] focus:ring-4 focus:ring-[#2F7D73]/15";
  const labelClass = `text-sm font-medium ${primaryTextClass}`;
  const buttonClass = isDark
    ? "h-11 w-full rounded-xl bg-[#63B3A7] px-5 text-sm font-semibold text-[#0F1517] transition hover:bg-[#79C7BC] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
    : "h-11 w-full rounded-xl bg-[#2F7D73] px-5 text-sm font-semibold text-white transition hover:bg-[#25675F] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60";

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
        setError(await readErrorMessage(response));
        return;
      }

      setMessage("Registration successful. You can log in now.");
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
        preferred_language: "English",
        education_level: "Primary",
        role: "learner",
      });
      router.push("/login");
    } catch {
      setError("Could not reach the backend. Check that FastAPI is running.");
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
        setError(await readErrorMessage(response));
        return;
      }

      const data = (await response.json()) as { access_token: string };
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("login_email", loginForm.email);
      setLoggedInEmail(loginForm.email);
      setMessage("Login successful.");
      router.push("/dashboard");
    } catch {
      setError("Could not reach the backend. Check that FastAPI is running.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    setLoggedInEmail("");
    setLoginForm({ email: "", password: "" });
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
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className={`inline-flex h-10 items-center gap-2 rounded-full border px-3 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
        isDark
          ? "border-[#2B373B] bg-[#1B2529] text-[#F4F7F6] hover:bg-[#202B2F] focus:ring-[#63B3A7]/20"
          : "border-[#DDE3E0] bg-white text-[#172033] hover:bg-[#EEF3F1] focus:ring-[#2F7D73]/15"
      }`}
    >
      <span>{theme === "dark" ? "Light" : "Dark"}</span>
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
              Login successful
            </div>
            <h1 className={`text-2xl font-semibold tracking-tight ${primaryTextClass}`}>
              Welcome back
            </h1>
            <p className={`mt-3 text-base leading-7 ${secondaryTextClass}`}>
              You are signed in as{" "}
              <span className={`font-semibold ${primaryTextClass}`}>
                {loggedInEmail}
              </span>
              .
            </p>
            <button type="button" onClick={handleLogout} className={`mt-8 ${buttonClass}`}>
              Logout
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={`${pageClass} transition-colors`}>
      <div className="mx-auto flex max-w-6xl justify-end px-5 pt-5 md:px-8">
        {themeToggle}
      </div>

      <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl grid-cols-1 gap-6 px-5 py-6 md:px-8 lg:grid-cols-[0.92fr_1.08fr] lg:items-center lg:gap-10 lg:py-10">
        <div
          className={`rounded-3xl border px-6 py-8 shadow-xl sm:px-8 lg:min-h-[560px] lg:px-10 lg:py-11 ${panelClass}`}
        >
          <div className="flex h-full flex-col justify-center">
            <div>
              <p className={`text-sm font-semibold ${accentTextClass}`}>
                Foundational Literacy Platform
              </p>
              <h1
                className={`mt-7 max-w-md text-3xl font-semibold leading-tight tracking-tight sm:text-4xl ${primaryTextClass}`}
              >
                AI-Powered Literacy Assistant
              </h1>
              <p className={`mt-4 max-w-sm text-base leading-7 ${secondaryTextClass}`}>
                Personalized literacy learning for every learner.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center">
          <section
            className={`w-full max-w-[480px] rounded-3xl border p-5 shadow-xl sm:p-7 ${elevatedClass}`}
          >
            <div
              className={`mb-3 grid grid-cols-2 rounded-xl border p-1 ${borderClass} ${mutedSurfaceClass}`}
            >
              <button
                type="button"
                onClick={() => switchTab("login")}
                aria-pressed={activeTab === "login"}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                  activeTab === "login"
                    ? isDark
                      ? "bg-[#63B3A7] text-[#0F1517] shadow-sm ring-1 ring-[#63B3A7]"
                      : "bg-[#2F7D73] text-white shadow-sm ring-1 ring-[#2F7D73]"
                    : isDark
                      ? "text-[#A8B3B0] hover:bg-[#1B2529] hover:text-[#F4F7F6] focus:ring-[#63B3A7]/20"
                      : "text-[#667085] hover:bg-white hover:text-[#172033] focus:ring-[#2F7D73]/15"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => switchTab("register")}
                aria-pressed={activeTab === "register"}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-4 ${
                  activeTab === "register"
                    ? isDark
                      ? "bg-[#63B3A7] text-[#0F1517] shadow-sm ring-1 ring-[#63B3A7]"
                      : "bg-[#2F7D73] text-white shadow-sm ring-1 ring-[#2F7D73]"
                    : isDark
                      ? "text-[#A8B3B0] hover:bg-[#1B2529] hover:text-[#F4F7F6] focus:ring-[#63B3A7]/20"
                      : "text-[#667085] hover:bg-white hover:text-[#172033] focus:ring-[#2F7D73]/15"
                }`}
              >
                Register
              </button>
            </div>

            <p className={`mb-6 text-center text-xs ${secondaryTextClass}`}>
              Secure access for learners, educators, and administrators.
            </p>

            <div className="mb-6">
              <h2 className={`text-2xl font-semibold tracking-tight ${primaryTextClass}`}>
                {activeTab === "login"
                  ? "Welcome back"
                  : "Create your account"}
              </h2>
              <p className={`mt-2 text-sm leading-6 ${secondaryTextClass}`}>
                {activeTab === "login"
                  ? "Sign in to continue."
                  : "Enter your details to get started."}
              </p>
            </div>

            {message ? (
              <div
                className={`mb-5 rounded-xl border px-4 py-3 text-sm font-medium ${
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
                className={`mb-5 rounded-xl border px-4 py-3 text-sm font-medium ${
                  isDark
                    ? "border-red-500/35 bg-red-500/10 text-red-200"
                    : "border-red-200 bg-red-50 text-red-800"
                }`}
              >
                {error}
              </div>
            ) : null}

            {activeTab === "login" ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <label className="block">
                  <span className={labelClass}>Email</span>
                  <input
                    type="email"
                    value={loginForm.email}
                    onChange={(event) =>
                      setLoginForm({ ...loginForm, email: event.target.value })
                    }
                    required
                    className={inputClass}
                    placeholder="you@example.com"
                  />
                </label>

                <label className="block">
                  <span className={labelClass}>Password</span>
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
                    placeholder="Enter your password"
                  />
                </label>

                <button type="submit" disabled={isSubmitting} className={buttonClass}>
                  {isSubmitting ? "Signing in..." : "Login"}
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <label className="block sm:col-span-2">
                    <span className={labelClass}>Full Name</span>
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
                      placeholder="Your full name"
                    />
                  </label>

                  <label className="block">
                    <span className={labelClass}>Age</span>
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
                      placeholder="20"
                    />
                  </label>

                  <label className="block">
                    <span className={labelClass}>Email</span>
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
                      placeholder="you@example.com"
                    />
                  </label>

                  <label className="block sm:col-span-2">
                    <span className={labelClass}>Password</span>
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
                      placeholder="At least 8 characters"
                    />
                  </label>

                  <label className="block">
                    <span className={labelClass}>Preferred Language</span>
                    <select
                      value={registerForm.preferred_language}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          preferred_language: event.target.value,
                        })
                      }
                      className={inputClass}
                    >
                      {languageOptions.map((language) => (
                        <option key={language}>{language}</option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className={labelClass}>Education Level</span>
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
                        <option key={level}>{level}</option>
                      ))}
                    </select>
                  </label>

                  <label className="block sm:col-span-2">
                    <span className={labelClass}>Role</span>
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
                        <option key={role}>{role}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <button type="submit" disabled={isSubmitting} className={buttonClass}>
                  {isSubmitting ? "Creating account..." : "Register"}
                </button>
              </form>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
