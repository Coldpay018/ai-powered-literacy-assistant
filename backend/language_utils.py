SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te"}


def normalize_language(value: str | None) -> str:
    normalized_value = (value or "").strip().lower()

    if normalized_value in {"hi", "hindi", "हिन्दी"}:
        return "hi"
    if normalized_value in {"ta", "tamil", "தமிழ்"}:
        return "ta"
    if normalized_value in {"te", "telugu", "తెలుగు"}:
        return "te"
    if normalized_value in {"en", "english"}:
        return "en"

    raise ValueError("Unsupported language")
