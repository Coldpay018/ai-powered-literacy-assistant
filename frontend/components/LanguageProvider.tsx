"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { translate, type TranslationKey } from "@/lib/i18n/translations";
import {
  LANGUAGE_STORAGE_KEY,
  normalizeLanguage,
  type LanguageCode,
} from "@/lib/i18n/types";

type TranslationReplacements = Record<string, string | number>;

type LanguageContextValue = {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  setLanguageFromValue: (value?: string | null) => LanguageCode;
  t: (key: TranslationKey, replacements?: TranslationReplacements) => string;
  resetLanguage: () => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>("en");

  useEffect(() => {
    const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    queueMicrotask(() => {
      setLanguageState(normalizeLanguage(savedLanguage));
    });
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((nextLanguage: LanguageCode) => {
    setLanguageState(nextLanguage);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
  }, []);

  const setLanguageFromValue = useCallback(
    (value?: string | null) => {
      const nextLanguage = normalizeLanguage(value);
      setLanguage(nextLanguage);
      return nextLanguage;
    },
    [setLanguage],
  );

  const resetLanguage = useCallback(() => {
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    setLanguageState("en");
  }, []);

  const t = useCallback(
    (key: TranslationKey, replacements?: TranslationReplacements) =>
      translate(language, key, replacements),
    [language],
  );

  const value = useMemo(
    () => ({ language, setLanguage, setLanguageFromValue, t, resetLanguage }),
    [language, resetLanguage, setLanguage, setLanguageFromValue, t],
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }

  return context;
}
