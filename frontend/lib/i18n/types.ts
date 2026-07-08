export type LanguageCode = "en" | "hi" | "ta" | "te";

export const LANGUAGE_STORAGE_KEY = "preferred_language";

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
