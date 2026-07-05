"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const navItems = [
  "Dashboard",
  "Learning Activities",
  "Progress",
  "Resources",
  "Profile",
];

const summaryCards = [
  { label: "Activities Completed", value: "18", detail: "4 this week" },
  { label: "Current Learning Streak", value: "6 days", detail: "Keep it going" },
  { label: "Overall Progress", value: "72%", detail: "Level 3 learner" },
];

const skillProgress = [
  { skill: "Reading", value: 78 },
  { skill: "Writing", value: 64 },
  { skill: "Vocabulary", value: 82 },
  { skill: "Comprehension", value: 58 },
];

const recentActivities = [
  "Completed vowel sound practice",
  "Reviewed 12 new vocabulary words",
  "Finished a short reading passage",
];

export default function Dashboard() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const storedEmail = localStorage.getItem("login_email");

    if (!token) {
      router.replace("/login");
      return;
    }

    queueMicrotask(() => {
      setEmail(storedEmail || "");
      setIsCheckingAuth(false);
    });
  }, [router]);

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("login_email");
    router.replace("/login");
  }

  if (isCheckingAuth) {
    return <main className="min-h-screen bg-[#F5F7F6]" />;
  }

  return (
    <main className="min-h-screen bg-[#F5F7F6] text-[#172033]">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-5 lg:grid lg:grid-cols-[240px_1fr] lg:px-8 lg:py-8">
        <aside className="rounded-2xl border border-[#DDE3E0] bg-white p-4 shadow-xl shadow-slate-900/5 lg:min-h-[calc(100vh-4rem)]">
          <div className="mb-5">
            <p className="text-sm font-semibold text-[#2F7D73]">
              Literacy Assistant
            </p>
            <p className="mt-1 text-xs text-[#667085]">Learning dashboard</p>
          </div>

          <nav className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {navItems.map((item) => (
              <button
                key={item}
                type="button"
                className={`whitespace-nowrap rounded-xl px-3 py-2 text-left text-sm font-semibold transition ${
                  item === "Dashboard"
                    ? "bg-[#2F7D73] text-white"
                    : "text-[#667085] hover:bg-[#EEF3F1] hover:text-[#172033]"
                }`}
              >
                {item}
              </button>
            ))}
          </nav>
        </aside>

        <section className="space-y-5">
          <header className="flex flex-col gap-4 rounded-2xl border border-[#DDE3E0] bg-white p-5 shadow-xl shadow-slate-900/5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-[#2F7D73]">Dashboard</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Welcome back
              </h1>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                {email ? `Signed in as ${email}` : "You are signed in."}
              </p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="h-11 rounded-xl bg-[#2F7D73] px-5 text-sm font-semibold text-white transition hover:bg-[#25675F]"
            >
              Logout
            </button>
          </header>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {summaryCards.map((card) => (
              <article
                key={card.label}
                className="rounded-2xl border border-[#DDE3E0] bg-white p-5 shadow-xl shadow-slate-900/5"
              >
                <p className="text-sm font-medium text-[#667085]">{card.label}</p>
                <p className="mt-3 text-3xl font-semibold tracking-tight">
                  {card.value}
                </p>
                <p className="mt-2 text-sm text-[#2F7D73]">{card.detail}</p>
              </article>
            ))}
          </section>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
            <section className="rounded-2xl border border-[#DDE3E0] bg-white p-5 shadow-xl shadow-slate-900/5">
              <div className="mb-5">
                <h2 className="text-lg font-semibold tracking-tight">
                  Literacy Skill Progress
                </h2>
                <p className="mt-1 text-sm text-[#667085]">
                  Practice balance across core literacy skills.
                </p>
              </div>

              <div className="space-y-5">
                {skillProgress.map((item) => (
                  <div key={item.skill}>
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <p className="text-sm font-semibold">{item.skill}</p>
                      <p className="text-sm text-[#667085]">{item.value}%</p>
                    </div>
                    <div className="h-3 rounded-full bg-[#EEF3F1]">
                      <div
                        className="h-3 rounded-full bg-[#2F7D73]"
                        style={{ width: `${item.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-[#DDE3E0] bg-white p-5 shadow-xl shadow-slate-900/5">
              <p className="text-sm font-semibold text-[#2F7D73]">
                Recommended Activity
              </p>
              <h2 className="mt-3 text-xl font-semibold tracking-tight">
                Read and Match
              </h2>
              <p className="mt-3 text-sm leading-6 text-[#667085]">
                Read a short passage and match key words with their meanings to
                strengthen vocabulary and comprehension.
              </p>
              <div className="mt-4 inline-flex rounded-full bg-[#EEF3F1] px-3 py-1 text-sm font-semibold text-[#2F7D73]">
                Beginner · 12 min
              </div>
              <button
                type="button"
                className="mt-6 h-11 w-full rounded-xl bg-[#2F7D73] px-5 text-sm font-semibold text-white transition hover:bg-[#25675F]"
              >
                Start Activity
              </button>
            </section>
          </div>

          <section className="rounded-2xl border border-[#DDE3E0] bg-white p-5 shadow-xl shadow-slate-900/5">
            <h2 className="text-lg font-semibold tracking-tight">
              Recent Activity
            </h2>
            <div className="mt-4 divide-y divide-[#DDE3E0]">
              {recentActivities.map((activity, index) => (
                <div
                  key={activity}
                  className="flex flex-col gap-1 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <p className="text-sm font-medium">{activity}</p>
                  <p className="text-sm text-[#667085]">
                    Session {index + 1} completed
                  </p>
                </div>
              ))}
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
