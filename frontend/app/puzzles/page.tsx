"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { LiteracyIcon } from "@/components/ui/LiteracyIllustrations";
import { useLanguage } from "@/components/LanguageProvider";
import { API_BASE_URL } from "@/lib/api/config";
import { getPuzzleSet, getPuzzleSets, submitPuzzleAttempt } from "@/lib/learning/api";
import type { MatchingItem, Puzzle, PuzzleSet } from "@/lib/learning/types";

type UserProfile = {
  comfortable_language: string | null;
};

type Tile = {
  id: string;
  value: string;
};

type Pair = {
  left_id: string;
  right_id: string;
};

function buildTiles(puzzle: Puzzle | null): Tile[] {
  return (puzzle?.puzzle_data.tiles || []).map((value, index) => ({
    id: `${puzzle?.id ?? "puzzle"}-${index}`,
    value,
  }));
}

export default function PuzzlesPage() {
  const router = useRouter();
  const { setLanguageFromValue, t } = useLanguage();
  const [sets, setSets] = useState<PuzzleSet[]>([]);
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null);
  const [selectedSet, setSelectedSet] = useState<PuzzleSet | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [availableTiles, setAvailableTiles] = useState<Tile[]>([]);
  const [selectedTiles, setSelectedTiles] = useState<Tile[]>([]);
  const [selectedLeftId, setSelectedLeftId] = useState<string | null>(null);
  const [selectedPairs, setSelectedPairs] = useState<Pair[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [xpEarned, setXPEarned] = useState(0);

  const currentPuzzle = selectedSet?.puzzles[currentIndex] || null;
  const leftItems = currentPuzzle?.puzzle_data.left_items || [];
  const rightItems = currentPuzzle?.puzzle_data.right_items || [];
  const isComplete = Boolean(selectedSet?.puzzles.length && currentIndex >= selectedSet.puzzles.length);

  const resetPuzzleState = useCallback((puzzle: Puzzle | null) => {
    setAvailableTiles(buildTiles(puzzle));
    setSelectedTiles([]);
    setSelectedLeftId(null);
    setSelectedPairs([]);
    setFeedback("");
  }, []);

  const loadSet = useCallback(
    async (token: string, setId: number) => {
      const nextSet = await getPuzzleSet(token, setId);
      setSelectedSet(nextSet);
      setCurrentIndex(0);
      resetPuzzleState(nextSet.puzzles[0] || null);
    },
    [resetPuzzleState],
  );

  const loadPuzzles = useCallback(async () => {
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

      const nextSets = await getPuzzleSets(token);
      setSets(nextSets);
      const firstSet = nextSets[0] || null;
      setSelectedSetId(firstSet?.id ?? null);
      if (firstSet) {
        await loadSet(token, firstSet.id);
      } else {
        setSelectedSet(null);
        resetPuzzleState(null);
      }
      setXPEarned(0);
    } catch {
      setError(t("puzzles.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [loadSet, resetPuzzleState, router, setLanguageFromValue, t]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadPuzzles();
    });
  }, [loadPuzzles]);

  async function handleSetChange(setId: number) {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setSelectedSetId(setId);
    setError("");
    setXPEarned(0);
    try {
      await loadSet(token, setId);
    } catch {
      setError(t("puzzles.loadError"));
    }
  }

  function selectTile(tile: Tile) {
    setAvailableTiles((items) => items.filter((item) => item.id !== tile.id));
    setSelectedTiles((items) => [...items, tile]);
  }

  function undoTile(tile: Tile) {
    setSelectedTiles((items) => items.filter((item) => item.id !== tile.id));
    setAvailableTiles((items) => [...items, tile].sort((a, b) => a.id.localeCompare(b.id)));
  }

  function resetCurrentPuzzle() {
    resetPuzzleState(currentPuzzle);
  }

  function selectMatch(item: MatchingItem, side: "left" | "right") {
    if (side === "left") {
      setSelectedLeftId(item.id);
      return;
    }
    if (!selectedLeftId) {
      return;
    }
    setSelectedPairs((pairs) => [
      ...pairs.filter((pair) => pair.left_id !== selectedLeftId && pair.right_id !== item.id),
      { left_id: selectedLeftId, right_id: item.id },
    ]);
    setSelectedLeftId(null);
  }

  async function submitCurrentPuzzle() {
    if (!currentPuzzle || !selectedSet) {
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    const submittedAnswer =
      currentPuzzle.puzzle_type === "jumbled_word"
        ? { tiles: selectedTiles.map((tile) => tile.value), answer: selectedTiles.map((tile) => tile.value).join("") }
        : { pairs: selectedPairs };

    setIsSubmitting(true);
    setError("");
    try {
      const result = await submitPuzzleAttempt(token, currentPuzzle.id, submittedAnswer);
      setFeedback(result.attempt.is_correct ? t("puzzles.correct") : t("puzzles.tryAgain"));
      setXPEarned((value) => value + result.xp_earned);
      setSelectedSet((current) =>
        current ? { ...current, progress: result.puzzle_set_progress } : current,
      );
      window.setTimeout(() => {
        const nextIndex = currentIndex + 1;
        setCurrentIndex(nextIndex);
        resetPuzzleState(selectedSet.puzzles[nextIndex] || null);
      }, 450);
    } catch {
      setError(t("puzzles.submitError"));
    } finally {
      setIsSubmitting(false);
    }
  }

  const selectedAnswerText = useMemo(() => selectedTiles.map((tile) => tile.value).join(""), [selectedTiles]);
  const matchedRightIds = new Set(selectedPairs.map((pair) => pair.right_id));
  const cardClass = "rounded-3xl border border-[var(--app-border)] bg-[var(--app-surface)] p-5 shadow-xl shadow-slate-900/6";

  return (
    <main className="min-h-screen bg-[var(--app-page)] px-4 py-6 text-[#172033] md:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-black text-[#0F766E]">{t("common.appName")}</p>
            <h1 className="mt-1 break-words text-3xl font-black tracking-normal">{t("puzzles.title")}</h1>
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
            <p className="text-sm font-bold text-[#667085]">{t("puzzles.loading")}</p>
          </section>
        ) : !sets.length ? (
          <section className={cardClass}>
            <span className="grid h-14 w-14 place-items-center rounded-2xl bg-[var(--app-surface-muted)]">
              <LiteracyIcon name="vocabulary" className="h-9 w-9" />
            </span>
            <h2 className="mt-4 text-xl font-black tracking-normal">{t("puzzles.noSetsTitle")}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">{t("puzzles.noSetsDescription")}</p>
          </section>
        ) : (
          <>
            <section className={cardClass}>
              <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                  <label htmlFor="puzzle-set" className="text-sm font-black text-[#0F766E]">
                    {t("puzzles.set")}
                  </label>
                  <select
                    id="puzzle-set"
                    value={selectedSetId ?? ""}
                    onChange={(event) => void handleSetChange(Number(event.target.value))}
                    className="mt-2 w-full rounded-2xl border border-[var(--app-border)] bg-white px-4 py-3 text-sm font-bold md:w-80"
                  >
                    {sets.map((set) => (
                      <option key={set.id} value={set.id}>
                        {set.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-wrap gap-2 text-xs font-black text-[#667085]">
                  <span className="rounded-full bg-[var(--app-surface-soft)] px-3 py-1">
                    {t("puzzles.progress", {
                      attempted: selectedSet?.progress.attempted_puzzles ?? 0,
                      total: selectedSet?.progress.total_puzzles ?? 0,
                    })}
                  </span>
                  <span className="rounded-full bg-[var(--app-surface-soft)] px-3 py-1">
                    {t("puzzles.accuracyValue", { accuracy: selectedSet?.progress.accuracy_percentage ?? 0 })}
                  </span>
                </div>
              </div>
            </section>

            {isComplete ? (
              <section className={cardClass}>
                <h2 className="text-xl font-black tracking-normal">{t("puzzles.puzzleComplete")}</h2>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  {t("puzzles.completionSummary", {
                    correct: selectedSet?.progress.correct_puzzles ?? 0,
                    total: selectedSet?.progress.total_puzzles ?? 0,
                  })}
                </p>
                {xpEarned > 0 ? (
                  <p className="mt-3 text-sm font-black text-[#0F766E]">{t("puzzles.xpEarned", { amount: xpEarned })}</p>
                ) : null}
              </section>
            ) : currentPuzzle ? (
              <section className={`${cardClass} min-h-[480px]`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-black text-[#0F766E]">
                      {currentPuzzle.puzzle_type === "jumbled_word" ? t("puzzles.jumbledWord") : t("puzzles.matching")}
                    </p>
                    <h2 className="mt-2 break-words text-2xl font-black tracking-normal">
                      {currentPuzzle.instruction_text}
                    </h2>
                    {currentPuzzle.prompt_text ? (
                      <p className="mt-3 break-words text-lg font-bold text-[#172033]">{currentPuzzle.prompt_text}</p>
                    ) : null}
                  </div>
                </div>

                {currentPuzzle.puzzle_type === "jumbled_word" ? (
                  <div className="mt-8 space-y-5">
                    {currentPuzzle.puzzle_data.clue ? (
                      <p className="rounded-2xl bg-[var(--app-surface-muted)] px-4 py-3 text-sm font-bold text-[#667085]">
                        {t("puzzles.clue")}: {currentPuzzle.puzzle_data.clue}
                      </p>
                    ) : null}
                    <div>
                      <p className="text-sm font-black text-[#0F766E]">{t("puzzles.selectedAnswer")}</p>
                      <div className="mt-2 flex min-h-16 flex-wrap gap-2 rounded-2xl border border-dashed border-[var(--app-border)] bg-[var(--app-surface-soft)] p-3">
                        {selectedTiles.length ? (
                          selectedTiles.map((tile) => (
                            <button
                              key={tile.id}
                              type="button"
                              onClick={() => undoTile(tile)}
                              className="min-h-11 rounded-2xl bg-white px-4 py-2 text-lg font-black text-[#172033] shadow-sm"
                            >
                              {tile.value}
                            </button>
                          ))
                        ) : (
                          <span className="text-sm font-bold text-[#667085]">{t("puzzles.selectCorrectOrder")}</span>
                        )}
                      </div>
                      {selectedAnswerText ? (
                        <p className="mt-2 break-words text-sm font-bold text-[#667085]">{selectedAnswerText}</p>
                      ) : null}
                    </div>
                    <div>
                      <p className="text-sm font-black text-[#0F766E]">{t("puzzles.availableTiles")}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {availableTiles.map((tile) => (
                          <button
                            key={tile.id}
                            type="button"
                            onClick={() => selectTile(tile)}
                            className="min-h-11 rounded-2xl border border-[var(--app-border)] bg-white px-4 py-2 text-lg font-black text-[#172033]"
                          >
                            {tile.value}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-8 grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <p className="text-sm font-black text-[#0F766E]">{t("puzzles.matchCorrectPairs")}</p>
                      {leftItems.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => selectMatch(item, "left")}
                          className={`w-full rounded-2xl border px-4 py-3 text-left text-sm font-black ${
                            selectedLeftId === item.id
                              ? "border-[#0F766E] bg-teal-50 text-[#0F766E]"
                              : "border-[var(--app-border)] bg-white text-[#172033]"
                          }`}
                        >
                          {item.text}
                        </button>
                      ))}
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm font-black text-[#0F766E]">{t("puzzles.selectedPairs")}</p>
                      {rightItems.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => selectMatch(item, "right")}
                          className={`w-full rounded-2xl border px-4 py-3 text-left text-sm font-black ${
                            matchedRightIds.has(item.id)
                              ? "border-[#0F766E] bg-teal-50 text-[#0F766E]"
                              : "border-[var(--app-border)] bg-white text-[#172033]"
                          }`}
                        >
                          {item.text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {feedback ? <p className="mt-5 text-sm font-black text-[#0F766E]">{feedback}</p> : null}
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={resetCurrentPuzzle}
                    disabled={isSubmitting}
                    className="rounded-2xl border border-[var(--app-border)] px-5 py-3 text-sm font-black text-[#0F766E] disabled:opacity-60"
                  >
                    {t("puzzles.reset")}
                  </button>
                  <button
                    type="button"
                    onClick={() => void submitCurrentPuzzle()}
                    disabled={
                      isSubmitting ||
                      (currentPuzzle.puzzle_type === "jumbled_word" && selectedTiles.length === 0) ||
                      (currentPuzzle.puzzle_type === "matching" && selectedPairs.length !== leftItems.length)
                    }
                    className="rounded-2xl bg-gradient-to-r from-[#0F766E] to-[#14B8A6] px-5 py-3 text-sm font-black text-white disabled:opacity-60"
                  >
                    {t("puzzles.submit")}
                  </button>
                </div>
              </section>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
