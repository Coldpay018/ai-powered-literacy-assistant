from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from question_taxonomy import (
    QUESTION_SKILLS,
    clamp_difficulty,
    derive_age_group,
    experience_level_to_starting_difficulty,
    normalize_age_group,
    normalize_difficulty_value,
    normalize_experience_level,
    normalize_question_language,
    normalize_question_skill,
    normalize_question_type,
    question_types_for_filter,
    score_to_difficulty,
)


SUPPORTED_SKILL_PROFILES = QUESTION_SKILLS
SKILL_SCORE_FIELDS = {
    "reading": "reading_score",
    "writing": "typing_score",
    "grammar": "mcq_score",
    "vocabulary": "mcq_score",
    "listening": "overall_score",
    "speaking": "overall_score",
    "comprehension": "reading_score",
}

SKILL_PROGRESS_ALIASES = {
    "reading": {"reading"},
    "writing": {"writing"},
    "grammar": {"writing", "comprehension"},
    "vocabulary": {"reading", "comprehension"},
    "listening": {"comprehension"},
    "speaking": {"writing"},
    "comprehension": {"comprehension"},
}


def _ensure_valid_user_profile(user: models.User) -> tuple[str, str]:
    if user.age < 6:
        raise HTTPException(status_code=422, detail="Age must be at least 6")

    try:
        comfortable_language = normalize_question_language(user.comfortable_language)
        learning_language = normalize_question_language(user.learning_language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid language value") from exc

    if comfortable_language and learning_language and comfortable_language == learning_language:
        raise HTTPException(
            status_code=422,
            detail="Comfortable language and learning language must be different",
        )

    if user.experience_level is None:
        raise HTTPException(status_code=422, detail="Invalid experience level")
    try:
        normalize_experience_level(user.experience_level)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid experience level") from exc

    return comfortable_language or "en", learning_language or "en"


def _assessment_result_score(assessment_result: models.AssessmentResult | None, skill: str | None) -> float | None:
    if assessment_result is None:
        return None

    if skill and skill in SKILL_SCORE_FIELDS:
        field_name = SKILL_SCORE_FIELDS[skill]
        score = getattr(assessment_result, field_name, None)
        if score is not None:
            return float(score)

    return float(getattr(assessment_result, "overall_score", 0) or 0)


def _progress_skill_matches(requested_skill: str, record: models.LearnerProgress) -> bool:
    lesson = getattr(record, "lesson", None)
    lesson_skill = getattr(lesson, "skill_type", None) or getattr(lesson, "skill", None)
    if lesson_skill is None:
        return False
    normalized_lesson_skill = normalize_question_skill(str(lesson_skill))
    if normalized_lesson_skill == requested_skill:
        return True
    return normalized_lesson_skill in SKILL_PROGRESS_ALIASES.get(requested_skill, {requested_skill})


def _record_score(record: models.LearnerProgress) -> float | None:
    score = getattr(record, "best_quiz_score", None)
    if score is not None:
        return float(score)
    score = getattr(record, "score", None)
    if score is not None:
        return float(score)
    return None


def _record_difficulty(record: models.LearnerProgress) -> int | None:
    current_difficulty = getattr(record, "current_difficulty", None)
    if current_difficulty is None:
        return None
    try:
        return normalize_difficulty_value(current_difficulty)
    except ValueError:
        return None


def _latest_progress_for_skill(
    progress_records: Iterable[models.LearnerProgress] | None,
    skill: str | None,
) -> models.LearnerProgress | None:
    if not progress_records or not skill:
        return None

    fallback = datetime.min.replace(tzinfo=timezone.utc)
    relevant = [
        record
        for record in progress_records
        if _progress_skill_matches(skill, record)
    ]
    if not relevant:
        return None

    return sorted(
        relevant,
        key=lambda record: (
            record.last_accessed_at or record.completed_at or fallback,
            record.id,
        ),
    )[-1]


def _starting_difficulty_from_progress(record: models.LearnerProgress | None) -> int | None:
    if record is None:
        return None
    score = _record_score(record)
    if score is not None:
        return clamp_difficulty(score_to_difficulty(score))
    difficulty = _record_difficulty(record)
    if difficulty is not None:
        return clamp_difficulty(difficulty)
    return None


def determine_starting_difficulty(
    user: models.User,
    assessment_result: models.AssessmentResult | None = None,
    skill: str | None = None,
    progress_records: Iterable[models.LearnerProgress] | None = None,
) -> int:
    _ensure_valid_user_profile(user)
    normalized_skill = normalize_question_skill(skill) if skill else None

    latest_progress = _latest_progress_for_skill(progress_records, normalized_skill)
    progress_difficulty = _starting_difficulty_from_progress(latest_progress)
    if progress_difficulty is not None:
        return progress_difficulty

    assessment_score = _assessment_result_score(assessment_result, normalized_skill)
    if assessment_score is not None:
        return clamp_difficulty(score_to_difficulty(assessment_score))

    try:
        experience_level = normalize_experience_level(user.experience_level)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid experience level") from exc
    return clamp_difficulty(experience_level_to_starting_difficulty(experience_level))


def build_starting_difficulty_profile(
    db: Session,
    user: models.User,
    skill: str | None = None,
) -> dict:
    if skill is not None:
        skill = normalize_question_skill(skill)
        if skill is None:
            raise HTTPException(status_code=422, detail="Invalid skill filter")

    try:
        age_group = derive_age_group(user.age)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Age must be at least 6") from exc

    comfortable_language, learning_language = _ensure_valid_user_profile(user)

    assessment_result = (
        db.query(models.AssessmentResult)
        .filter(models.AssessmentResult.user_id == user.id)
        .order_by(models.AssessmentResult.completed_at.desc(), models.AssessmentResult.id.desc())
        .first()
    )
    progress_records = (
        db.query(models.LearnerProgress)
        .options(joinedload(models.LearnerProgress.lesson))
        .filter(models.LearnerProgress.user_id == user.id)
        .all()
    )

    skill_profiles: dict[str, dict] = {}
    for item in SUPPORTED_SKILL_PROFILES:
        adaptive_state = (
            db.query(models.LearnerSkillDifficulty)
            .filter(
                models.LearnerSkillDifficulty.user_id == user.id,
                models.LearnerSkillDifficulty.skill == item,
            )
            .first()
        )
        if adaptive_state is not None:
            skill_difficulty = clamp_difficulty(adaptive_state.current_difficulty)
        else:
            skill_difficulty = determine_starting_difficulty(
                user,
                assessment_result=assessment_result,
                skill=item,
                progress_records=progress_records,
            )
        skill_profiles[item] = {
            "skill": item,
            "starting_difficulty": skill_difficulty,
        }

    requested_skill = skill or "overall"
    if skill:
        adaptive_state = (
            db.query(models.LearnerSkillDifficulty)
            .filter(
                models.LearnerSkillDifficulty.user_id == user.id,
                models.LearnerSkillDifficulty.skill == skill,
            )
            .first()
        )
        if adaptive_state is not None:
            starting_difficulty = clamp_difficulty(adaptive_state.current_difficulty)
        else:
            starting_difficulty = skill_profiles[skill]["starting_difficulty"]
    else:
        starting_difficulty = determine_starting_difficulty(
            user,
            assessment_result=assessment_result,
            skill=None,
            progress_records=progress_records,
        )

    source = "experience_level"
    if progress_records and any(_starting_difficulty_from_progress(record) is not None for record in progress_records):
        source = "progress"
    elif assessment_result is not None:
        source = "assessment_result"

    return {
        "user_id": user.id,
        "age": user.age,
        "age_group": age_group,
        "experience_level": normalize_experience_level(user.experience_level),
        "comfortable_language": comfortable_language,
        "learning_language": learning_language,
        "requested_skill": requested_skill if requested_skill != "overall" else None,
        "starting_difficulty": starting_difficulty,
        "skill_difficulties": {
            item: profile["starting_difficulty"]
            for item, profile in skill_profiles.items()
        },
        "source": source,
    }


def filter_question_query(
    query,
    question_model,
    *,
    skill: str | None = None,
    difficulty: int | str | None = None,
    age_group: str | None = None,
    experience_level: str | None = None,
    comfortable_language: str | None = None,
    learning_language: str | None = None,
    question_type: str | None = None,
):
    if skill is not None:
        try:
            normalized_skill = normalize_question_skill(skill)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid skill filter") from exc
        if normalized_skill is None:
            raise HTTPException(status_code=422, detail="Invalid skill filter")
        query = query.filter(question_model.skill == normalized_skill)
    if difficulty is not None:
        try:
            normalized_difficulty = normalize_difficulty_value(difficulty)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid difficulty filter") from exc
        if normalized_difficulty is None:
            raise HTTPException(status_code=422, detail="Invalid difficulty filter")
        difficulty_column = getattr(question_model, "difficulty_rating", None)
        if difficulty_column is not None:
            query = query.filter(difficulty_column == normalized_difficulty)
        else:
            legacy_difficulty_column = getattr(question_model, "difficulty", None)
            if legacy_difficulty_column is None:
                legacy_difficulty_column = getattr(question_model, "difficulty_level", None)
            if legacy_difficulty_column is not None:
                legacy_difficulty = "beginner" if normalized_difficulty <= 2 else "intermediate" if normalized_difficulty == 3 else "advanced"
                query = query.filter(legacy_difficulty_column == legacy_difficulty)
    if age_group is not None:
        try:
            normalized_age_group = normalize_age_group(age_group)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid age group filter") from exc
        query = query.filter(question_model.age_group == normalized_age_group)
    if experience_level is not None:
        try:
            normalized_experience = normalize_experience_level(experience_level)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid experience level filter") from exc
        query = query.filter(question_model.experience_level == normalized_experience)
    if comfortable_language is not None:
        try:
            normalized_language = normalize_question_language(comfortable_language)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid language filter") from exc
        query = query.filter(question_model.comfortable_language == normalized_language)
    if learning_language is not None:
        try:
            normalized_language = normalize_question_language(learning_language)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid language filter") from exc
        query = query.filter(question_model.learning_language == normalized_language)
    if question_type is not None:
        try:
            normalized_type = normalize_question_type(question_type)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid question type filter") from exc
        if normalized_type is None:
            raise HTTPException(status_code=422, detail="Invalid question type filter")
        query = query.filter(question_model.question_type.in_(question_types_for_filter(normalized_type)))
    return query
