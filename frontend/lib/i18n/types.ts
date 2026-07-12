export type LanguageCode = "en" | "hi" | "ta" | "te";

export const UI_LANGUAGE_STORAGE_KEY = "ui_language";
export const LEGACY_LANGUAGE_STORAGE_KEY = "preferred_language";

export function writeStoredUiLanguage(language: LanguageCode) {
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  window.localStorage.removeItem(LEGACY_LANGUAGE_STORAGE_KEY);
}

export function clearStoredUiLanguage() {
  window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_LANGUAGE_STORAGE_KEY);
}

export const LANGUAGE_OPTIONS: Array<{ code: LanguageCode; label: string }> = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
];

export function normalizeLanguage(value?: string | null): LanguageCode {
  switch (value?.toLowerCase()) {
    case "hi":
    case "hindi":
    case "हिन्दी":
      return "hi";
    case "ta":
    case "tamil":
    case "தமிழ்":
      return "ta";
    case "te":
    case "telugu":
    case "తెలుగు":
      return "te";
    case "en":
    case "english":
    default:
      return "en";
  }
}
