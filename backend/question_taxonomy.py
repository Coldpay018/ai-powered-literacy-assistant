from __future__ import annotations

from typing import Final

from language_utils import normalize_language


DIFFICULTY_SCALE: Final[dict[int, str]] = {
    1: "Very easy",
    2: "Easy",
    3: "Moderate",
    4: "Difficult",
    5: "Advanced",
}

AGE_GROUPS: Final[tuple[str, ...]] = ("Child", "Teenager", "Adult")
EXPERIENCE_LEVELS: Final[tuple[str, ...]] = ("Beginner", "Intermediate", "Advanced")
QUESTION_SKILLS: Final[tuple[str, ...]] = (
    "reading",
    "writing",
    "grammar",
    "vocabulary",
    "listening",
    "speaking",
    "comprehension",
)
QUESTION_TYPES: Final[tuple[str, ...]] = (
    "multiple_choice",
    "fill_in_the_blank",
    "sentence_ordering",
    "sentence_rearrange",
    "reading_comprehension",
    "typing_writing",
    "speaking",
    "listening",
    "spoken_answer",
    "reading_aloud",
    "sentence_repetition",
    "pronunciation",
    "spoken_fill_blank",
)

LEGACY_DIFFICULTY_TO_SCORE: Final[dict[str, int]] = {
    "beginner": 1,
    "intermediate": 3,
    "advanced": 5,
}

EXPERIENCE_TO_STARTING_DIFFICULTY: Final[dict[str, int]] = {
    "Beginner": 2,
    "Intermediate": 3,
    "Advanced": 4,
}

LEGACY_QUESTION_TYPE_TO_NORMALIZED: Final[dict[str, str]] = {
    "mcq": "multiple_choice",
    "true_false": "multiple_choice",
    "reading_mcq": "reading_comprehension",
    "copy_typing": "typing_writing",
    "short_response": "typing_writing",
    "short_answer": "typing_writing",
    "sentence_completion": "fill_in_the_blank",
    "fill_blank": "fill_in_the_blank",
    "sequence": "sentence_ordering",
    "matching": "sentence_ordering",
    "drag_drop": "sentence_ordering",
}

LEGACY_SKILL_TO_QUESTION_SKILL: Final[dict[str, str]] = {
    "word recognition": "vocabulary",
    "literal comprehension": "reading",
    "passage comprehension": "reading",
    "copy accuracy": "writing",
    "sentence completion": "grammar",
    "short response": "writing",
    "vocabulary": "vocabulary",
    "sentence meaning": "grammar",
    "basic comprehension": "comprehension",
}

LEGACY_SKILL_TO_GROUP: Final[dict[str, str]] = {
    "reading": "reading",
    "writing": "writing",
    "comprehension": "comprehension",
    "grammar": "grammar",
    "vocabulary": "vocabulary",
    "listening": "listening",
    "speaking": "speaking",
}


def clamp_difficulty(value: int) -> int:
    return max(1, min(5, value))


def normalize_difficulty_value(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        if 1 <= value <= 5:
            return value
        raise ValueError("Invalid difficulty value")

    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned.isdigit():
        numeric = int(cleaned)
        if 1 <= numeric <= 5:
            return numeric
        raise ValueError("Invalid difficulty value")
    if cleaned in LEGACY_DIFFICULTY_TO_SCORE:
        return LEGACY_DIFFICULTY_TO_SCORE[cleaned]
    raise ValueError("Invalid difficulty value")


def normalize_age_group(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().title()
    if cleaned not in AGE_GROUPS:
        raise ValueError("Invalid age group")
    return cleaned


def normalize_experience_level(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().title()
    if cleaned not in EXPERIENCE_LEVELS:
        raise ValueError("Invalid experience level")
    return cleaned


def normalize_question_skill(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    normalized = LEGACY_SKILL_TO_GROUP.get(cleaned, cleaned)
    if normalized not in QUESTION_SKILLS:
        raise ValueError("Invalid skill value")
    return normalized


def normalize_question_type(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned in QUESTION_TYPES:
        return cleaned
    if cleaned in LEGACY_QUESTION_TYPE_TO_NORMALIZED:
        return LEGACY_QUESTION_TYPE_TO_NORMALIZED[cleaned]
    raise ValueError("Unsupported question type")


def normalize_question_language(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_language(value)


def normalize_question_pair(
    comfortable_language: str | None,
    learning_language: str | None,
) -> tuple[str | None, str | None]:
    normalized_comfortable = normalize_question_language(comfortable_language)
    normalized_learning = normalize_question_language(learning_language)
    if (
        normalized_comfortable
        and normalized_learning
        and normalized_comfortable == normalized_learning
    ):
        raise ValueError("Comfortable language and learning language must be different")
    return normalized_comfortable, normalized_learning


def derive_age_group(age: int) -> str:
    if 6 <= age <= 12:
        return "Child"
    if 13 <= age <= 17:
        return "Teenager"
    if age >= 18:
        return "Adult"
    raise ValueError("Age must be at least 6")


def experience_level_to_starting_difficulty(value: str | None) -> int:
    if value is None:
        return EXPERIENCE_TO_STARTING_DIFFICULTY["Beginner"]
    cleaned = normalize_experience_level(value)
    if cleaned is None:
        return EXPERIENCE_TO_STARTING_DIFFICULTY["Beginner"]
    return EXPERIENCE_TO_STARTING_DIFFICULTY[cleaned]


def score_to_difficulty(score: float | int | None) -> int:
    if score is None:
        return EXPERIENCE_TO_STARTING_DIFFICULTY["Beginner"]

    numeric_score = float(score)
    if numeric_score >= 90:
        return 5
    if numeric_score >= 75:
        return 4
    if numeric_score >= 55:
        return 3
    if numeric_score >= 35:
        return 2
    return 1


def difficulty_label(value: int | str | None) -> str | None:
    normalized = normalize_difficulty_value(value)
    if normalized is None:
        return None
    return DIFFICULTY_SCALE[normalized]


def question_skills_for_filter(value: str | None) -> list[str]:
    normalized = normalize_question_skill(value)
    if normalized is None:
        return []
    return [normalized]


def question_types_for_filter(value: str | None) -> list[str]:
    normalized = normalize_question_type(value)
    if normalized is None:
        return []
    reverse_map: dict[str, list[str]] = {}
    for legacy, normalized_type in LEGACY_QUESTION_TYPE_TO_NORMALIZED.items():
        reverse_map.setdefault(normalized_type, []).append(legacy)
    return reverse_map.get(normalized, [normalized])
