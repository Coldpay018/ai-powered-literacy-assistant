from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from assessment_flow_service import submit_assessment_answer
from assessment_question_utils import normalize_sentence_text
from assessment_service import _dumps, _score_answer
from question_taxonomy import normalize_question_skill


VOICE_QUESTION_TYPES = {
    "speaking",
    "spoken_answer",
    "reading_aloud",
    "sentence_repetition",
    "pronunciation",
    "spoken_fill_blank",
}


def _feedback_from_scoring(maximum_marks: int, marks_awarded: float, is_correct: bool | None) -> str:
    if marks_awarded >= maximum_marks:
        return "Correct"
    if marks_awarded > 0:
        return "Close match"
    return "Try again"


def submit_spoken_assessment_answer(
    db: Session,
    user: models.User,
    attempt_id: int,
    attempt_question_id: int,
    spoken_text: str,
):
    recognized_text = normalize_sentence_text(
        spoken_text,
        case_sensitive=False,
        allow_terminal_punctuation=True,
    )
    if not recognized_text:
        raise HTTPException(status_code=422, detail="Spoken answer is required")

    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt_id, models.AssessmentAttempt.user_id == user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    attempt_question = (
        db.query(models.AssessmentAttemptQuestion)
        .filter(
            models.AssessmentAttemptQuestion.id == attempt_question_id,
            models.AssessmentAttemptQuestion.attempt_id == attempt.id,
        )
        .first()
    )
    if not attempt_question:
        raise HTTPException(status_code=404, detail="Attempt question not found")

    question = (
        db.query(models.AssessmentQuestion)
        .filter(models.AssessmentQuestion.id == attempt_question.question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        normalize_question_skill(question.skill or question.skill_tag)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported question for spoken answers") from exc

    if question.question_type not in VOICE_QUESTION_TYPES:
        raise HTTPException(status_code=422, detail="Spoken answers are not supported for this question")

    temp_answer = SimpleNamespace(answer_json=_dumps({"text": recognized_text}))
    marks_awarded, is_correct, details = _score_answer(question, attempt_question, temp_answer)
    feedback = _feedback_from_scoring(attempt_question.maximum_marks, float(marks_awarded), is_correct)

    submitted = submit_assessment_answer(
        db,
        user,
        attempt.id,
        attempt_question.id,
        {"text": recognized_text},
    )
    submitted["feedback"] = feedback
    submitted["model_used"] = "browser-speech-recognition"

    refreshed_attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt.id)
        .first()
    )
    submitted["attempt_status"] = refreshed_attempt.status if refreshed_attempt else attempt.status

    answer_row = (
        db.query(models.AssessmentAnswer)
        .filter(
            models.AssessmentAnswer.attempt_id == attempt.id,
            models.AssessmentAnswer.attempt_question_id == attempt_question.id,
        )
        .first()
    )
    if answer_row is not None:
        answer_row.feedback = feedback
        answer_row.normalized_answer_json = _dumps({"normalized": details.get("normalized_answer")})
        answer_row.updated_at = datetime.now(timezone.utc)
        db.add(answer_row)
        db.commit()

    return submitted
