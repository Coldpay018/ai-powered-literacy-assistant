from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from question_taxonomy import clamp_difficulty, normalize_difficulty_value, normalize_question_skill


RECENT_HISTORY_LIMIT = 20
ROLLING_WINDOW_SIZE = 5
VALID_SKILLS = {
    "reading",
    "writing",
    "vocabulary",
    "grammar",
    "listening",
    "speaking",
    "comprehension",
}


def _loads(value: str | None, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not value:
        return list(fallback)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return list(fallback)
    return parsed if isinstance(parsed, list) else list(fallback)


def _dumps(value: list[dict[str, Any]]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _event_id(context: dict[str, Any] | None, skill: str, is_correct: bool) -> str:
    payload = {
        "skill": skill,
        "is_correct": bool(is_correct),
        "source": (context or {}).get("source"),
        "event_id": (context or {}).get("event_id"),
        "question_id": (context or {}).get("question_id"),
        "attempt_id": (context or {}).get("attempt_id"),
        "lesson_id": (context or {}).get("lesson_id"),
        "answer_hash": (context or {}).get("answer_hash"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_skill(skill: str) -> str:
    try:
        normalized = normalize_question_skill(skill)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid skill") from exc
    if normalized not in VALID_SKILLS:
        raise HTTPException(status_code=422, detail="Invalid skill")
    return normalized


def _starting_difficulty(db: Session, user: models.User, skill: str) -> int:
    from question_difficulty_service import determine_starting_difficulty

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
    return determine_starting_difficulty(
        user,
        assessment_result=assessment_result,
        skill=skill,
        progress_records=progress_records,
    )


def _get_state(db: Session, user_id: int, skill: str) -> models.LearnerSkillDifficulty | None:
    return (
        db.query(models.LearnerSkillDifficulty)
        .filter(
            models.LearnerSkillDifficulty.user_id == user_id,
            models.LearnerSkillDifficulty.skill == skill,
        )
        .first()
    )


def _create_state(db: Session, user: models.User, skill: str) -> models.LearnerSkillDifficulty:
    state = models.LearnerSkillDifficulty(
        user_id=user.id,
        skill=skill,
        current_difficulty=_starting_difficulty(db, user, skill),
        correct_streak=0,
        incorrect_streak=0,
        recent_response_history_json="[]",
        rolling_accuracy=0,
        last_adjustment_reason="starting_difficulty",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(state)
    db.flush()
    return state


def _current_history(state: models.LearnerSkillDifficulty) -> list[dict[str, Any]]:
    return _loads(state.recent_response_history_json, [])


def _rolling_accuracy(history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    window = history[-ROLLING_WINDOW_SIZE:]
    correct = sum(1 for item in window if item.get("is_correct"))
    return round(correct / len(window), 2)


def _decision_reason(
    *,
    previous_difficulty: int,
    current_difficulty: int,
    adjusted: bool,
    reason: str,
) -> str:
    if adjusted:
        return reason
    if reason == "three_consecutive_correct" and previous_difficulty >= 5:
        return "already_at_max_level"
    if reason == "three_consecutive_incorrect" and previous_difficulty <= 1:
        return "already_at_min_level"
    if reason == "rolling_accuracy_high" and previous_difficulty >= 5:
        return "already_at_max_level"
    if reason == "rolling_accuracy_low" and previous_difficulty <= 1:
        return "already_at_min_level"
    return "maintained"


def _trim_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return history[-RECENT_HISTORY_LIMIT:]


def evaluate_difficulty(
    db: Session,
    user_id: int,
    skill: str,
    is_correct: bool,
    context: dict[str, Any] | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    normalized_skill = _normalize_skill(skill)
    event_id = _event_id(context, normalized_skill, is_correct)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    state = _get_state(db, user_id, normalized_skill)
    if state is None:
        state = _create_state(db, user, normalized_skill)

    history = _current_history(state)
    if any(entry.get("event_id") == event_id for entry in history):
        rolling_accuracy = _rolling_accuracy(history)
        return {
            "skill": normalized_skill,
            "previous_difficulty": state.current_difficulty,
            "new_difficulty": state.current_difficulty,
            "correct_streak": state.correct_streak,
            "incorrect_streak": state.incorrect_streak,
            "rolling_accuracy": rolling_accuracy,
            "adjusted": False,
            "reason": "duplicate_submission",
            "updated_at": state.updated_at,
        }

    previous_difficulty = state.current_difficulty
    correct_streak = state.correct_streak
    incorrect_streak = state.incorrect_streak
    reason = "maintained"
    adjusted = False

    if is_correct:
        correct_streak += 1
        incorrect_streak = 0
    else:
        incorrect_streak += 1
        correct_streak = 0

    next_difficulty = previous_difficulty

    if correct_streak >= 3:
        reason = "three_consecutive_correct"
        next_difficulty = clamp_difficulty(previous_difficulty + 1)
        adjusted = next_difficulty != previous_difficulty
    elif incorrect_streak >= 3:
        reason = "three_consecutive_incorrect"
        next_difficulty = clamp_difficulty(previous_difficulty - 1)
        adjusted = next_difficulty != previous_difficulty
    else:
        history_with_current = [
            *history,
            {
                "event_id": event_id,
                "is_correct": bool(is_correct),
                "source": (context or {}).get("source"),
                "question_id": (context or {}).get("question_id"),
                "attempt_id": (context or {}).get("attempt_id"),
                "lesson_id": (context or {}).get("lesson_id"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        rolling_accuracy = _rolling_accuracy(history_with_current)
        if len(history_with_current[-ROLLING_WINDOW_SIZE:]) == ROLLING_WINDOW_SIZE:
            if rolling_accuracy >= 0.8:
                reason = "rolling_accuracy_high"
                next_difficulty = clamp_difficulty(previous_difficulty + 1)
                adjusted = next_difficulty != previous_difficulty
            elif rolling_accuracy <= 0.4:
                reason = "rolling_accuracy_low"
                next_difficulty = clamp_difficulty(previous_difficulty - 1)
                adjusted = next_difficulty != previous_difficulty
    if reason in {"three_consecutive_correct", "three_consecutive_incorrect"} and adjusted:
        correct_streak = 0
        incorrect_streak = 0
    elif reason in {"rolling_accuracy_high", "rolling_accuracy_low"} and adjusted:
        correct_streak = 0
        incorrect_streak = 0

    history.append(
        {
            "event_id": event_id,
            "is_correct": bool(is_correct),
            "source": (context or {}).get("source"),
            "question_id": (context or {}).get("question_id"),
            "attempt_id": (context or {}).get("attempt_id"),
            "lesson_id": (context or {}).get("lesson_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    history = _trim_history(history)
    rolling_accuracy = _rolling_accuracy(history)

    state.current_difficulty = next_difficulty
    state.correct_streak = correct_streak
    state.incorrect_streak = incorrect_streak
    state.recent_response_history_json = _dumps(history)
    state.rolling_accuracy = rolling_accuracy
    state.last_adjustment_reason = _decision_reason(
        previous_difficulty=previous_difficulty,
        current_difficulty=next_difficulty,
        adjusted=adjusted,
        reason=reason,
    )
    state.updated_at = datetime.now(timezone.utc)

    db.add(state)
    if commit:
        db.commit()
        db.refresh(state)
    else:
        db.flush()

    return {
        "skill": normalized_skill,
        "previous_difficulty": previous_difficulty,
        "new_difficulty": state.current_difficulty,
        "correct_streak": state.correct_streak,
        "incorrect_streak": state.incorrect_streak,
        "rolling_accuracy": state.rolling_accuracy,
        "adjusted": adjusted,
        "reason": state.last_adjustment_reason,
        "updated_at": state.updated_at,
    }


def get_skill_difficulty(
    db: Session,
    user_id: int,
    skill: str,
) -> models.LearnerSkillDifficulty | None:
    normalized_skill = _normalize_skill(skill)
    return _get_state(db, user_id, normalized_skill)


def get_or_create_skill_difficulty(
    db: Session,
    user: models.User,
    skill: str,
) -> models.LearnerSkillDifficulty:
    normalized_skill = _normalize_skill(skill)
    state = _get_state(db, user.id, normalized_skill)
    if state is not None:
        return state
    return _create_state(db, user, normalized_skill)
