"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { TTSControls } from "@/components/tts/TTSControls";
import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import { useLanguage } from "@/components/LanguageProvider";
import { API_BASE_URL } from "@/lib/api/config";
import {
  getDueFlashcards,
  getFlashcardDecks,
  reviewFlashcard,
} from "@/lib/learning/api";
import type { Flashcard, FlashcardDeck } from "@/lib/learning/types";

type UserProfile = {
  comfortable_language: string | null;
};

export default function FlashcardsPage() {
  const router = useRouter();
  const { setLanguageFromValue, t } = useLanguage();
  const [decks, setDecks] = useState<FlashcardDeck[]>([]);
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(null);
  const [dueCards, setDueCards] = useState<Flashcard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isReviewing, setIsReviewing] = useState(false);
  const [error, setError] = useState("");
  const [isRevealed, setIsRevealed] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [xpEarned, setXPEarned] = useState(0);

  const selectedDeck = useMemo(
    () => decks.find((deck) => deck.id === selectedDeckId) || null,
    [decks, selectedDeckId],
  );
  const currentCard = dueCards[0] || null;

  const loadDueCards = useCallback(async (token: string, deckId: number) => {
    const cards = await getDueFlashcards(token, deckId);
    setDueCards(cards);
    setIsRevealed(false);
    setReviewedCount(0);
    setXPEarned(0);
  }, []);

  const loadFlashcards = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const profileResponse = await fetch(`${API_BASE_URL}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!profileResponse.ok) {
        router.replace("/login");
        return;
      }
      const profile = (await profileResponse.json()) as UserProfile;
      setLanguageFromValue(profile.comfortable_language);

      const nextDecks = await getFlashcardDecks(token);
      setDecks(nextDecks);
      const firstDeck = nextDecks[0] || null;
      setSelectedDeckId(firstDeck?.id ?? null);
      if (firstDeck) {
        await loadDueCards(token, firstDeck.id);
      } else {
        setDueCards([]);
      }
    } catch {
      setError(t("flashcards.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [loadDueCards, router, setLanguageFromValue, t]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadFlashcards();
    });
  }, [loadFlashcards]);

  async function handleDeckChange(deckId: number) {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setSelectedDeckId(deckId);
    setError("");
    try {
      await loadDueCards(token, deckId);
    } catch {
      setError(t("flashcards.loadError"));
    }
  }

  async function handleReview(outcome: "need_practice" | "know") {
    if (!currentCard) {
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setIsReviewing(true);
    setError("");
    try {
      const result = await reviewFlashcard(token, currentCard.id, outcome);
      setXPEarned((value) => value + result.xp_earned);
      setReviewedCount((value) => value + 1);
      setDueCards((cards) => cards.slice(1));
      setIsRevealed(false);
      setDecks((items) =>
        items.map((deck) =>
          deck.id === currentCard.deck_id
            ? { ...deck, progress: result.deck_progress }
            : deck,
        ),
      );
    } catch {
      setError(t("flashcards.reviewError"));
    } finally {
      setIsReviewing(false);
    }
  }

  const pageClass = "min-h-screen bg-[var(--app-page)] px-4 py-6 text-[#172033] md:px-8";
  const cardClass = "rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/6";

  return (
    <main className={pageClass}>
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-black text-[#0F766E]">{t("common.appName")}</p>
            <h1 className="mt-1 break-words text-3xl font-black tracking-normal">{t("flashcards.title")}</h1>
          </div>
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface)] px-4 py-3 text-sm font-black text-[#0F766E]"
          >
            {t("common.dashboard")}
          </button>
        </header>

        {error ? (
          <section className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">
            {error}
          </section>
        ) : null}

        {isLoading ? (
          <section className={cardClass}>
            <p className="text-sm font-bold text-[#667085]">{t("flashcards.loading")}</p>
          </section>
        ) : !decks.length ? (
          <section className={cardClass}>
            <span className="grid h-14 w-14 place-items-center rounded-2xl bg-[var(--app-surface-muted)]">
              <LiteracyIcon name="vocabulary" className="h-9 w-9" />
            </span>
            <h2 className="mt-4 text-xl font-black tracking-normal">{t("flashcards.noDecksTitle")}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">{t("flashcards.noDecksDescription")}</p>
          </section>
        ) : (
          <>
            <section className={cardClass}>
              <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                  <label htmlFor="deck" className="text-sm font-black text-[#0F766E]">
                    {t("flashcards.deck")}
                  </label>
                  <select
                    id="deck"
                    value={selectedDeckId ?? ""}
                    onChange={(event) => void handleDeckChange(Number(event.target.value))}
                    className="mt-2 w-full rounded-2xl border border-[var(--app-border)] bg-white px-4 py-3 text-sm font-bold md:w-80"
                  >
                    {decks.map((deck) => (
                      <option key={deck.id} value={deck.id}>
                        {deck.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-wrap gap-2 text-xs font-black text-[#667085]">
                  <span className="rounded-full bg-[var(--app-surface-soft)] px-3 py-1">
                    {t("flashcards.cardsDue", { count: selectedDeck?.progress.due_cards ?? dueCards.length })}
                  </span>
                  <span className="rounded-full bg-[var(--app-surface-soft)] px-3 py-1">
                    {t("flashcards.cardsMastered", { count: selectedDeck?.progress.mastered_cards ?? 0 })}
                  </span>
                </div>
              </div>
            </section>

            {!currentCard ? (
              <section className={cardClass}>
                <h2 className="text-xl font-black tracking-normal">{t("flashcards.reviewComplete")}</h2>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  {reviewedCount > 0 ? t("flashcards.completionSummary", { count: reviewedCount }) : t("flashcards.comeBackLater")}
                </p>
                {xpEarned > 0 ? (
                  <p className="mt-3 text-sm font-black text-[#0F766E]">{t("flashcards.xpEarned", { amount: xpEarned })}</p>
                ) : null}
              </section>
            ) : (
              <section className={`${cardClass} min-h-[420px]`}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-black text-[#0F766E]">{selectedDeck?.title}</p>
                    <h2 className="mt-2 break-words text-4xl font-black tracking-normal">{currentCard.front_text}</h2>
                  </div>
                  <TTSControls
                    text={[currentCard.front_text, currentCard.example_text].filter(Boolean).join(". ")}
                    language={selectedDeck?.learning_language}
                    label="tts.readContent"
                    t={t}
                    isDark={false}
                    variant="single"
                    buttonText={t("tts.play")}
                    ariaLabel={t("tts.play")}
                  />
                </div>

                {currentCard.example_text ? (
                  <p className="mt-6 break-words rounded-2xl bg-[var(--app-surface-muted)] px-4 py-3 text-lg font-bold">
                    {currentCard.example_text}
                  </p>
                ) : null}

                {!isRevealed ? (
                  <button
                    type="button"
                    onClick={() => setIsRevealed(true)}
                    className="mt-8 rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white"
                  >
                    {t("flashcards.revealAnswer")}
                  </button>
                ) : (
                  <div className="mt-8 space-y-4">
                    <div>
                      <p className="text-sm font-black text-[#0F766E]">{t("flashcards.meaning")}</p>
                      <p className="mt-2 break-words text-2xl font-black tracking-normal">{currentCard.back_text}</p>
                    </div>
                    {currentCard.example_translation ? (
                      <p className="break-words rounded-2xl bg-[var(--app-surface-soft)] px-4 py-3 text-sm leading-6 text-[#667085]">
                        {currentCard.example_translation}
                      </p>
                    ) : null}
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <button
                        type="button"
                        onClick={() => void handleReview("need_practice")}
                        disabled={isReviewing}
                        className="rounded-2xl border border-[var(--app-border)] px-5 py-3 text-sm font-black text-[#0F766E] disabled:opacity-60"
                      >
                        {t("flashcards.needPractice")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleReview("know")}
                        disabled={isReviewing}
                        className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white disabled:opacity-60"
                      >
                        {t("flashcards.know")}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
