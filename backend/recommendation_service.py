from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models


EmbeddingFn = Callable[[list[str]], list[list[float]]]
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SKILL_LABELS = {"reading": "reading", "writing": "writing", "comprehension": "comprehension"}

_model = None
_lesson_embedding_cache: dict[tuple[int, str], list[float]] = {}
_embedding_fn_override: EmbeddingFn | None = None


@dataclass(frozen=True)
class SkillProfile:
    weakest_skill: str
    scores: dict[str, float]


def set_embedding_function_for_tests(embedding_fn: EmbeddingFn | None) -> None:
    global _embedding_fn_override
    _embedding_fn_override = embedding_fn
    _lesson_embedding_cache.clear()


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Embedding model dependency is not installed. Install backend requirements.",
            ) from exc
        try:
            _model = SentenceTransformer(MODEL_NAME)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Embedding model could not be loaded: {exc}") from exc
    return _model


def _embed(texts: list[str]) -> list[list[float]]:
    if _embedding_fn_override:
        return _embedding_fn_override(texts)
    vectors = _get_model().encode(texts, normalize_embeddings=True)
    return [list(map(float, vector)) for vector in vectors]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _latest_result(db: Session, user: models.User) -> models.AssessmentResult:
    result = (
        db.query(models.AssessmentResult)
        .filter(models.AssessmentResult.user_id == user.id)
        .order_by(models.AssessmentResult.completed_at.desc(), models.AssessmentResult.id.desc())
        .first()
    )
    if not result:
        raise HTTPException(status_code=409, detail="Initial assessment is incomplete or no assessment result exists")
    return result


def get_skill_profile(result: models.AssessmentResult) -> SkillProfile:
    scores = {
        "reading": float(result.reading_score),
        "writing": float(result.typing_score),
        "comprehension": float(result.mcq_score),
    }
    return SkillProfile(weakest_skill=min(scores, key=scores.get), scores=scores)


def _learner_needs_text(result: models.AssessmentResult, user: models.User, skill_profile: SkillProfile) -> str:
    sorted_skills = sorted(skill_profile.scores.items(), key=lambda item: item[1])
    weak_descriptions = ", ".join(f"{skill} score {score:g}" for skill, score in sorted_skills)
    return (
        f"An {result.proficiency_level} learner with weakest skill in {skill_profile.weakest_skill}. "
        f"Needs lessons for {weak_descriptions}. "
        f"Reading score: {result.reading_score:g}, writing score: {result.typing_score:g}, "
        f"comprehension score: {result.mcq_score:g}. Learning language: {user.learning_language}."
    )


def _lesson_text(lesson: models.Lesson) -> str:
    return (
        f"{lesson.title}. {lesson.description} Skill: {lesson.skill_type}. "
        f"Level: {lesson.proficiency_level}. Language: {lesson.language}."
    )


def _progress_by_lesson(db: Session, user_id: int) -> dict[int, models.LearnerProgress]:
    rows = db.query(models.LearnerProgress).filter(models.LearnerProgress.user_id == user_id).all()
    return {row.lesson_id: row for row in rows}


def _available_lessons(db: Session, result: models.AssessmentResult, language: str) -> list[models.Lesson]:
    query = db.query(models.Lesson).filter(models.Lesson.is_active == True)
    language_matches = query.filter(models.Lesson.language == language).all()
    candidates = language_matches or query.filter(models.Lesson.language == "en").all()
    exact_level = [lesson for lesson in candidates if lesson.proficiency_level == result.proficiency_level]
    return exact_level or candidates


def _lesson_embeddings(lessons: Iterable[models.Lesson]) -> dict[int, list[float]]:
    missing: list[models.Lesson] = []
    embeddings: dict[int, list[float]] = {}
    for lesson in lessons:
        cache_key = (lesson.id, lesson.description)
        cached = _lesson_embedding_cache.get(cache_key)
        if cached is None:
            missing.append(lesson)
        else:
            embeddings[lesson.id] = cached

    if missing:
        vectors = _embed([_lesson_text(lesson) for lesson in missing])
        for lesson, vector in zip(missing, vectors):
            cache_key = (lesson.id, lesson.description)
            _lesson_embedding_cache[cache_key] = vector
            embeddings[lesson.id] = vector
    return embeddings


def _reason(lesson: models.Lesson, skill_profile: SkillProfile, result: models.AssessmentResult) -> str:
    if lesson.skill_type == skill_profile.weakest_skill:
        return (
            f"Recommended because {lesson.skill_type} is currently your lowest-scoring skill "
            f"and this lesson focuses on {lesson.title.lower()} at the {result.proficiency_level} level."
        )
    return (
        f"Recommended as supporting practice because {lesson.skill_type} is another area to strengthen "
        f"for your {result.proficiency_level} learning path."
    )


def _serialize_recommendation(
    recommendation: models.LessonRecommendation,
    progress: models.LearnerProgress | None,
) -> dict:
    lesson = recommendation.lesson
    return {
        "lesson_id": lesson.id,
        "title": lesson.title,
        "description": lesson.description,
        "skill_type": lesson.skill_type,
        "proficiency_level": lesson.proficiency_level,
        "language": lesson.language,
        "estimated_duration_minutes": lesson.estimated_duration_minutes,
        "recommendation_score": round(float(recommendation.recommendation_score), 4),
        "recommendation_reason": recommendation.recommendation_reason,
        "current_progress_status": progress.status if progress else "not_started",
    }


def current_recommendations(db: Session, user: models.User) -> list[dict]:
    recommendations = (
        db.query(models.LessonRecommendation)
        .filter(models.LessonRecommendation.user_id == user.id, models.LessonRecommendation.is_active == True)
        .join(models.Lesson)
        .order_by(models.LessonRecommendation.recommendation_score.desc())
        .all()
    )
    progress = _progress_by_lesson(db, user.id)
    return [_serialize_recommendation(item, progress.get(item.lesson_id)) for item in recommendations]


def generate_recommendations(db: Session, user: models.User, limit: int = 6) -> list[dict]:
    result = _latest_result(db, user)
    skill_profile = get_skill_profile(result)
    progress = _progress_by_lesson(db, user.id)
    completed_lesson_ids = {lesson_id for lesson_id, row in progress.items() if row.status == "completed"}
    lessons = [lesson for lesson in _available_lessons(db, result, user.learning_language) if lesson.id not in completed_lesson_ids]
    if not lessons:
        raise HTTPException(status_code=404, detail="No suitable lessons are available")

    learner_vector = _embed([_learner_needs_text(result, user, skill_profile)])[0]
    lesson_vectors = _lesson_embeddings(lessons)
    scored = []
    for lesson in lessons:
        similarity = _cosine_similarity(learner_vector, lesson_vectors[lesson.id])
        skill_gap = (100.0 - skill_profile.scores[lesson.skill_type]) / 100.0
        skill_bonus = 0.18 if lesson.skill_type == skill_profile.weakest_skill else 0.07 * skill_gap
        level_bonus = 0.10 if lesson.proficiency_level == result.proficiency_level else 0.0
        language_bonus = 0.05 if lesson.language == user.learning_language else 0.0
        progress_penalty = 0.08 if progress.get(lesson.id) and progress[lesson.id].status == "in_progress" else 0.0
        # Ranking formula: semantic similarity from MiniLM is the base signal.
        # Small deterministic modifiers then prioritize the learner's weakest skill,
        # exact proficiency/language matches, and lessons not already in progress.
        final_score = similarity + skill_bonus + level_bonus + language_bonus - progress_penalty
        scored.append((final_score, lesson))

    scored.sort(key=lambda item: (item[0], -item[1].difficulty_order), reverse=True)
    selected: list[tuple[float, models.Lesson]] = []
    seen_skills: set[str] = set()
    for score, lesson in scored:
        if len(selected) >= limit:
            break
        if lesson.skill_type == skill_profile.weakest_skill or len(selected) >= 3 or lesson.skill_type not in seen_skills:
            selected.append((score, lesson))
            seen_skills.add(lesson.skill_type)

    if not selected:
        raise HTTPException(status_code=404, detail="No suitable lessons are available")

    db.query(models.LessonRecommendation).filter(
        models.LessonRecommendation.user_id == user.id,
        models.LessonRecommendation.is_active == True,
    ).update({"is_active": False})

    generated_at = datetime.now(timezone.utc)
    for score, lesson in selected:
        db.add(
            models.LessonRecommendation(
                user_id=user.id,
                lesson_id=lesson.id,
                recommendation_score=round(float(score), 4),
                recommendation_reason=_reason(lesson, skill_profile, result),
                generated_at=generated_at,
                is_active=True,
            )
        )
    db.commit()
    return current_recommendations(db, user)


def learning_plan(db: Session, user: models.User) -> dict:
    result = _latest_result(db, user)
    recommendations = current_recommendations(db, user)
    if not recommendations:
        recommendations = generate_recommendations(db, user)
    skill_profile = get_skill_profile(result)
    progress_rows = _progress_by_lesson(db, user.id)
    recommended_ids = {item["lesson_id"] for item in recommendations}
    completed = sum(1 for lesson_id in recommended_ids if progress_rows.get(lesson_id) and progress_rows[lesson_id].status == "completed")
    in_progress = sum(1 for lesson_id in recommended_ids if progress_rows.get(lesson_id) and progress_rows[lesson_id].status == "in_progress")
    suggested = next((item for item in recommendations if item["current_progress_status"] != "completed"), None)
    return {
        "learner_proficiency_level": result.proficiency_level,
        "reading_score": result.reading_score,
        "writing_score": result.typing_score,
        "comprehension_score": result.mcq_score,
        "weakest_skill": skill_profile.weakest_skill,
        "recommended_lessons": recommendations,
        "completion_summary": {
            "completed_lessons_count": completed,
            "in_progress_lessons_count": in_progress,
            "total_recommended_lessons": len(recommendations),
        },
        "suggested_next_lesson": suggested,
    }
