export type LanguageCode = "en" | "hi" | "ta" | "te" | "kn";

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
  { code: "kn", label: "ಕನ್ನಡ" },
];

export function normalizeLanguage(value?: string | null): LanguageCode {
  const normalized = value?.trim().toLowerCase() || "";
  const base = normalized.split("-")[0];

  switch (normalized) {
    case "hi":
    case "hindi":
    case "hi-in":
    case "हिन्दी":
      return "hi";
    case "ta":
    case "tamil":
    case "ta-in":
    case "தமிழ்":
      return "ta";
    case "te":
    case "telugu":
    case "te-in":
    case "తెలుగు":
      return "te";
    case "kn":
    case "kannada":
    case "kn-in":
    case "ಕನ್ನಡ":
      return "kn";
    case "en":
    case "english":
    case "en-in":
    case "en-us":
    case "en-gb":
      return "en";
    default:
      break;
  }

  switch (base) {
    case "hi":
      return "hi";
    case "ta":
      return "ta";
    case "te":
      return "te";
    case "kn":
      return "kn";
    default:
      return "en";
  }
}
