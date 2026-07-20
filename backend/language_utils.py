SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te", "kn"}


def normalize_language(value: str | None) -> str:
    normalized_value = (value or "").strip().lower()
    base_value = normalized_value.split("-", 1)[0]

    if normalized_value in {"hi", "hindi", "hi-in", "हिन्दी"} or base_value == "hi":
        return "hi"
    if normalized_value in {"ta", "tamil", "ta-in", "தமிழ்"} or base_value == "ta":
        return "ta"
    if normalized_value in {"te", "telugu", "te-in", "తెలుగు"} or base_value == "te":
        return "te"
    if normalized_value in {"kn", "kannada", "kn-in", "ಕನ್ನಡ"} or base_value == "kn":
        return "kn"
    if normalized_value in {"en", "english", "en-in", "en-us", "en-gb"} or base_value == "en":
        return "en"

    raise ValueError("Unsupported language")
