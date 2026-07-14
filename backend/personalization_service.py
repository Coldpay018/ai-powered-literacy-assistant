from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException

import models
from language_utils import normalize_language
from schemas import ExperienceLevel


AGE_GROUPS = {
    "Child": range(6, 13),
    "Teenager": range(13, 18),
    "Adult": range(18, 10_000),
}

SKILL_ORDER = ("reading", "grammar", "vocabulary", "listening", "speaking", "writing")
VALID_DIFFICULTIES = ("beginner", "intermediate", "advanced")
EXPERIENCE_TO_DIFFICULTY = {
    "Beginner": "beginner",
    "Intermediate": "intermediate",
    "Advanced": "advanced",
}

BASE_RULES = {
    "Child": {
        "Beginner": {
            "content_tone": "playful and encouraging",
            "sentence_length": "short",
            "vocabulary_complexity": "simple",
            "translation_support": "high",
            "grammar_depth": "light",
            "question_complexity": "simple",
            "example_style": "visual-friendly examples with animals, school, and colours",
            "preferred_topics": ["animals", "school", "colours", "family", "games"],
        },
        "Intermediate": {
            "content_tone": "curious and supportive",
            "sentence_length": "medium",
            "vocabulary_complexity": "mixed",
            "translation_support": "medium",
            "grammar_depth": "moderate",
            "question_complexity": "mixed",
            "example_style": "visual examples with short stories and routines",
            "preferred_topics": ["stories", "nature", "community", "food", "routines"],
        },
        "Advanced": {
            "content_tone": "challenging and encouraging",
            "sentence_length": "long",
            "vocabulary_complexity": "advanced",
            "translation_support": "medium",
            "grammar_depth": "deep",
            "question_complexity": "complex",
            "example_style": "visual-rich problem solving and age-appropriate nonfiction",
            "preferred_topics": ["science", "adventures", "teamwork", "problem solving", "biographies"],
        },
    },
    "Teenager": {
        "Beginner": {
            "content_tone": "friendly and relatable",
            "sentence_length": "medium",
            "vocabulary_complexity": "simple",
            "translation_support": "high",
            "grammar_depth": "light",
            "question_complexity": "simple",
            "example_style": "real-life examples from school and everyday teenage life",
            "preferred_topics": ["hobbies", "school life", "friendships", "technology", "sports"],
        },
        "Intermediate": {
            "content_tone": "motivating and conversational",
            "sentence_length": "medium",
            "vocabulary_complexity": "mixed",
            "translation_support": "medium",
            "grammar_depth": "moderate",
            "question_complexity": "mixed",
            "example_style": "conversation-based examples and short reports",
            "preferred_topics": ["study plans", "social media", "community", "projects", "future goals"],
        },
        "Advanced": {
            "content_tone": "thoughtful and discussion-based",
            "sentence_length": "long",
            "vocabulary_complexity": "advanced",
            "translation_support": "minimal",
            "grammar_depth": "deep",
            "question_complexity": "complex",
            "example_style": "authentic articles, debates, and analysis tasks",
            "preferred_topics": ["debates", "careers", "science", "social issues", "leadership"],
        },
    },
    "Adult": {
        "Beginner": {
            "content_tone": "practical and respectful",
            "sentence_length": "medium",
            "vocabulary_complexity": "simple",
            "translation_support": "high",
            "grammar_depth": "light",
            "question_complexity": "simple",
            "example_style": "practical everyday examples for real-world use",
            "preferred_topics": ["travel", "work", "shopping", "daily communication", "family"],
        },
        "Intermediate": {
            "content_tone": "clear and practical",
            "sentence_length": "long",
            "vocabulary_complexity": "mixed",
            "translation_support": "medium",
            "grammar_depth": "moderate",
            "question_complexity": "mixed",
            "example_style": "workplace, home, and community scenarios",
            "preferred_topics": ["workplace", "home", "health", "finance", "technology"],
        },
        "Advanced": {
            "content_tone": "professional and analytical",
            "sentence_length": "long",
            "vocabulary_complexity": "advanced",
            "translation_support": "minimal",
            "grammar_depth": "deep",
            "question_complexity": "complex",
            "example_style": "authentic target-language content and professional scenarios",
            "preferred_topics": ["professional writing", "civic life", "analysis", "negotiation", "policy"],
        },
    },
}

SKILL_TOPIC_EXTRAS = {
    "reading": ["comprehension passages", "everyday texts"],
    "grammar": ["sentence patterns", "word order", "punctuation"],
    "vocabulary": ["word families", "topic word banks", "synonyms"],
    "listening": ["short dialogues", "instructions", "directions"],
    "speaking": ["introductions", "requests", "role plays"],
    "writing": ["sentences", "notes", "messages"],
}

SKILL_PROXY_MAP = {
    "reading": ("reading",),
    "grammar": ("writing", "comprehension"),
    "vocabulary": ("reading", "comprehension"),
    "listening": ("comprehension",),
    "speaking": ("writing",),
    "writing": ("writing",),
}


@dataclass(frozen=True)
class PerformanceSummary:
    total_lessons: int
    completed_lessons: int
    in_progress_lessons: int
    questions_attempted: int
    correct_answers: int
    incorrect_answers: int
    average_score: float
    best_score: float
    recent_score: float
    current_difficulty: str
    last_accessed_at: datetime | None


def _validate_user_inputs(user: models.User) -> tuple[str, str, ExperienceLevel, str]:
    if user.age < 6:
        raise HTTPException(status_code=422, detail="Age must be at least 6 for personalization")

    age_group = _age_group(user.age)
    try:
        comfortable_language = normalize_language(user.comfortable_language)
        learning_language = normalize_language(user.learning_language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid language value") from exc

    if comfortable_language == learning_language:
        raise HTTPException(status_code=422, detail="Comfortable language and learning language must be different")

    experience_level = user.experience_level
    if experience_level not in EXPERIENCE_TO_DIFFICULTY:
        raise HTTPException(status_code=422, detail="Invalid experience level")

    return age_group, comfortable_language, experience_level, learning_language


def _age_group(age: int) -> str:
    for age_group, age_range in AGE_GROUPS.items():
        if age in age_range:
            return age_group
    raise HTTPException(status_code=422, detail="Age must be at least 6 for personalization")


def _ordered_progress(records: Iterable[models.LearnerProgress]) -> list[models.LearnerProgress]:
    fallback_time = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        records,
        key=lambda record: (
            record.last_accessed_at or record.completed_at or fallback_time,
            record.id,
        ),
    )


def _record_score(record: models.LearnerProgress) -> float:
    if record.best_quiz_score is not None:
        return float(record.best_quiz_score)
    return float(record.score or 0)


def _difficulty_from_score(score: float) -> str:
    if score >= 75:
        return "advanced"
    if score >= 45:
        return "intermediate"
    return "beginner"


def _valid_difficulty(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    lowered = value.strip().lower()
    if lowered not in VALID_DIFFICULTIES:
        return fallback
    return lowered


def _step_up_difficulty(level: str) -> str:
    if level == "beginner":
        return "intermediate"
    if level == "intermediate":
        return "advanced"
    return "advanced"


def _step_down_difficulty(level: str) -> str:
    if level == "advanced":
        return "intermediate"
    if level == "intermediate":
        return "beginner"
    return "beginner"


def _summarize_progress(records: list[models.LearnerProgress], fallback_difficulty: str) -> PerformanceSummary:
    ordered = _ordered_progress(records)
    scores = [_record_score(record) for record in ordered]
    total_questions = sum(record.questions_attempted for record in ordered)
    completed = sum(1 for record in ordered if record.status == "completed")
    in_progress = sum(1 for record in ordered if record.status == "in_progress")
    correct_answers = sum(record.correct_answers for record in ordered)
    incorrect_answers = sum(record.incorrect_answers for record in ordered)
    best_score = max(scores, default=0.0)
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    recent_record = ordered[-1] if ordered else None
    recent_score = _record_score(recent_record) if recent_record else 0.0
    current_difficulty = _valid_difficulty(
        recent_record.current_difficulty if recent_record else None,
        _difficulty_from_score(recent_score) if recent_record else fallback_difficulty,
    )
    last_accessed_at = recent_record.last_accessed_at if recent_record else None
    return PerformanceSummary(
        total_lessons=len(ordered),
        completed_lessons=completed,
        in_progress_lessons=in_progress,
        questions_attempted=total_questions,
        correct_answers=correct_answers,
        incorrect_answers=incorrect_answers,
        average_score=average_score,
        best_score=round(best_score, 2),
        recent_score=round(recent_score, 2),
        current_difficulty=current_difficulty,
        last_accessed_at=last_accessed_at,
    )


def _base_rules(age_group: str, experience_level: ExperienceLevel) -> dict[str, object]:
    return dict(BASE_RULES[age_group][experience_level])


def _topics_for_skill(base_topics: list[str], skill: str) -> list[str]:
    combined = list(base_topics)
    combined.extend(SKILL_TOPIC_EXTRAS.get(skill, []))
    seen: set[str] = set()
    ordered_topics: list[str] = []
    for topic in combined:
        if topic not in seen:
            ordered_topics.append(topic)
            seen.add(topic)
    return ordered_topics


def _progress_for_skill(
    records: list[models.LearnerProgress],
    skill: str,
) -> list[models.LearnerProgress]:
    matched: list[models.LearnerProgress] = []
    for record in records:
        lesson_skill = getattr(record.lesson, "skill_type", None) or getattr(record.lesson, "skill", None)
        if lesson_skill in SKILL_PROXY_MAP.get(skill, (skill,)):
            matched.append(record)
    return matched


def _skill_level_from_records(
    records: list[models.LearnerProgress],
    fallback_level: str,
) -> str:
    if not records:
        return fallback_level
    score = _summarize_progress(records, fallback_level).average_score
    return _difficulty_from_score(score)


def _skill_current_difficulty(
    records: list[models.LearnerProgress],
    fallback_level: str,
) -> str:
    if not records:
        return fallback_level
    summary = _summarize_progress(records, fallback_level)
    if summary.current_difficulty in VALID_DIFFICULTIES:
        return summary.current_difficulty
    return fallback_level


def _adjust_difficulty_from_performance(level: str, score: float) -> str:
    if score >= 85:
        return _step_up_difficulty(level)
    if score < 35:
        return _step_down_difficulty(level)
    return level


def build_personalization_profile(
    user: models.User,
    progress_records: list[models.LearnerProgress],
) -> dict:
    age_group, comfortable_language, experience_level, learning_language = _validate_user_inputs(user)
    base_difficulty = EXPERIENCE_TO_DIFFICULTY[experience_level]
    base_rules = _base_rules(age_group, experience_level)
    overall_summary = _summarize_progress(progress_records, base_difficulty)
    current_skill = _skill_level_from_records(progress_records, base_difficulty)
    current_difficulty = _valid_difficulty(overall_summary.current_difficulty, base_difficulty)
    if overall_summary.total_lessons:
        current_difficulty = _adjust_difficulty_from_performance(current_difficulty, overall_summary.recent_score)

    skill_profiles = {}
    for skill in SKILL_ORDER:
        skill_records = _progress_for_skill(progress_records, skill)
        skill_summary = _summarize_progress(skill_records, base_difficulty)
        skill_level = _skill_level_from_records(skill_records, current_skill)
        skill_difficulty = _skill_current_difficulty(skill_records, current_difficulty)
        if skill_summary.total_lessons:
            skill_difficulty = _adjust_difficulty_from_performance(skill_difficulty, skill_summary.recent_score)
        skill_rules = _base_rules(age_group, experience_level)
        skill_rules["preferred_topics"] = _topics_for_skill(list(skill_rules["preferred_topics"]), skill)
        skill_profiles[skill] = {
            "skill": skill,
            "current_skill": skill_level,
            "current_difficulty": skill_difficulty,
            "content_tone": skill_rules["content_tone"],
            "sentence_length": skill_rules["sentence_length"],
            "vocabulary_complexity": skill_rules["vocabulary_complexity"],
            "preferred_topics": skill_rules["preferred_topics"],
            "translation_support": skill_rules["translation_support"],
            "grammar_depth": skill_rules["grammar_depth"],
            "question_complexity": skill_rules["question_complexity"],
            "example_style": skill_rules["example_style"],
            "comfortable_language": comfortable_language,
            "learning_language": learning_language,
            "previous_performance": {
                "total_lessons": skill_summary.total_lessons,
                "completed_lessons": skill_summary.completed_lessons,
                "in_progress_lessons": skill_summary.in_progress_lessons,
                "questions_attempted": skill_summary.questions_attempted,
                "correct_answers": skill_summary.correct_answers,
                "incorrect_answers": skill_summary.incorrect_answers,
                "average_score": skill_summary.average_score,
                "best_score": skill_summary.best_score,
                "recent_score": skill_summary.recent_score,
                "current_difficulty": skill_summary.current_difficulty,
                "last_accessed_at": skill_summary.last_accessed_at,
            },
        }

    return {
        "age": user.age,
        "age_group": age_group,
        "experience_level": experience_level,
        "comfortable_language": comfortable_language,
        "learning_language": learning_language,
        "current_skill": current_skill,
        "current_difficulty": current_difficulty,
        "content_tone": base_rules["content_tone"],
        "sentence_length": base_rules["sentence_length"],
        "vocabulary_complexity": base_rules["vocabulary_complexity"],
        "preferred_topics": base_rules["preferred_topics"],
        "translation_support": base_rules["translation_support"],
        "grammar_depth": base_rules["grammar_depth"],
        "question_complexity": base_rules["question_complexity"],
        "example_style": base_rules["example_style"],
        "previous_performance": {
            "total_lessons": overall_summary.total_lessons,
            "completed_lessons": overall_summary.completed_lessons,
            "in_progress_lessons": overall_summary.in_progress_lessons,
            "questions_attempted": overall_summary.questions_attempted,
            "correct_answers": overall_summary.correct_answers,
            "incorrect_answers": overall_summary.incorrect_answers,
            "average_score": overall_summary.average_score,
            "best_score": overall_summary.best_score,
            "recent_score": overall_summary.recent_score,
            "current_difficulty": overall_summary.current_difficulty,
            "last_accessed_at": overall_summary.last_accessed_at,
        },
        "skill_profiles": skill_profiles,
    }
