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
  clearStoredUiLanguage,
  normalizeLanguage,
  type LanguageCode,
  writeStoredUiLanguage,
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
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((nextLanguage: LanguageCode) => {
    setLanguageState(nextLanguage);
    writeStoredUiLanguage(nextLanguage);
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
    clearStoredUiLanguage();
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
