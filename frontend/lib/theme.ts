export type ThemeMode = "light" | "dark";

export function applyDocumentTheme(theme: ThemeMode) {
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.dataset.theme = theme;
}
