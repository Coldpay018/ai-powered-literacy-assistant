import json
import random
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from language_utils import normalize_language
from seed_assessment import ASSESSMENT_VERSION


SECTION_ORDER = ["reading", "typing", "mcq"]
DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]
BLUEPRINT = {
    "reading": {"beginner": 2, "intermediate": 2, "advanced": 1},
    "typing": {"beginner": 1, "intermediate": 1, "advanced": 1},
    "mcq": {"beginner": 2, "intermediate": 2, "advanced": 1},
}
SECTION_TITLES = {"reading": "Reading", "typing": "Typing", "mcq": "MCQs"}


def _loads(value, fallback):
    if not value:
        return fallback
    return json.loads(value)


def _dumps(value):
    return json.dumps(value, ensure_ascii=False)


def get_initial_assessment(db: Session):
    assessment = (
        db.query(models.Assessment)
        .filter(models.Assessment.version == ASSESSMENT_VERSION, models.Assessment.is_active == True)
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def get_status(db: Session, user: models.User):
    if user.role != "learner":
        return {
            "required": False,
            "completed": False,
            "has_in_progress_attempt": False,
            "attempt_id": None,
            "proficiency_level": None,
            "reason": "role_not_learner",
        }

    result = (
        db.query(models.AssessmentResult)
        .filter(
            models.AssessmentResult.user_id == user.id,
            models.AssessmentResult.assessment_version == ASSESSMENT_VERSION,
        )
        .first()
    )
    if result:
        return {
            "required": False,
            "completed": True,
            "has_in_progress_attempt": False,
            "attempt_id": result.attempt_id,
            "proficiency_level": result.proficiency_level,
            "reason": None,
        }

    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    return {
        "required": True,
        "completed": False,
        "has_in_progress_attempt": attempt is not None,
        "attempt_id": attempt.id if attempt else None,
        "proficiency_level": None,
        "reason": None,
    }


def _select_questions(db: Session, language: str):
    selected = []
    rng = random.SystemRandom()
    for section in SECTION_ORDER:
        for difficulty in DIFFICULTY_ORDER:
            count = BLUEPRINT[section][difficulty]
            query = (
                db.query(models.AssessmentQuestion)
                .filter(
                    models.AssessmentQuestion.assessment_version == ASSESSMENT_VERSION,
                    models.AssessmentQuestion.language == language,
                    models.AssessmentQuestion.section == section,
                    models.AssessmentQuestion.difficulty == difficulty,
                    models.AssessmentQuestion.is_active == True,
                )
                .all()
            )
            if len(query) < count:
                raise HTTPException(status_code=500, detail="Question pool is incomplete")
            picked = rng.sample(query, count)
            rng.shuffle(picked)
            selected.extend(picked)
    return selected


def _shuffle_options(question: models.AssessmentQuestion):
    options = _loads(question.options_json, [])
    if not options:
        return None
    shuffled = list(options)
    random.SystemRandom().shuffle(shuffled)
    return shuffled


def start_or_resume(db: Session, user: models.User):
    if user.role != "learner":
        raise HTTPException(status_code=403, detail="Assessment is required only for learners")

    completed = (
        db.query(models.AssessmentResult)
        .filter(
            models.AssessmentResult.user_id == user.id,
            models.AssessmentResult.assessment_version == ASSESSMENT_VERSION,
        )
        .first()
    )
    if completed:
        raise HTTPException(status_code=409, detail="Assessment already completed")

    existing = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    if existing:
        return serialize_attempt(db, existing)

    assessment = get_initial_assessment(db)
    language = normalize_language(user.preferred_language)
    attempt = models.AssessmentAttempt(
        user_id=user.id,
        assessment_id=assessment.id,
        assessment_version=assessment.version,
        preferred_language=language,
        status="in_progress",
    )
    db.add(attempt)
    db.flush()

    display_order = 1
    for question in _select_questions(db, language):
        db.add(
            models.AssessmentAttemptQuestion(
                attempt_id=attempt.id,
                question_id=question.id,
                section=question.section,
                display_order=display_order,
                shuffled_options_json=_dumps(_shuffle_options(question)) if question.options_json else None,
                maximum_marks=question.marks,
            )
        )
        display_order += 1

    db.commit()
    db.refresh(attempt)
    return serialize_attempt(db, attempt)


def _get_attempt_for_user(db: Session, attempt_id: int, user: models.User):
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt_id, models.AssessmentAttempt.user_id == user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


def current_attempt(db: Session, user: models.User):
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return serialize_attempt(db, attempt)


def serialize_attempt(db: Session, attempt: models.AssessmentAttempt):
    rows = (
        db.query(models.AssessmentAttemptQuestion, models.AssessmentQuestion)
        .join(models.AssessmentQuestion, models.AssessmentAttemptQuestion.question_id == models.AssessmentQuestion.id)
        .filter(models.AssessmentAttemptQuestion.attempt_id == attempt.id)
        .order_by(models.AssessmentAttemptQuestion.display_order)
        .all()
    )
    answer_rows = (
        db.query(models.AssessmentAnswer)
        .filter(models.AssessmentAnswer.attempt_id == attempt.id)
        .all()
    )
    answers = {str(answer.attempt_question_id): _loads(answer.answer_json, {}) for answer in answer_rows}
    sections = []
    for section in SECTION_ORDER:
        questions = []
        for attempt_question, question in rows:
            if attempt_question.section != section:
                continue
            questions.append({
                "attempt_question_id": attempt_question.id,
                "section": section,
                "display_order": attempt_question.display_order,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "passage": question.passage,
                "prompt": question.prompt,
                "options": _loads(attempt_question.shuffled_options_json, None),
                "marks": attempt_question.maximum_marks,
                "skill_tag": question.skill_tag,
            })
        sections.append({"section": section, "title": SECTION_TITLES[section], "questions": questions})
    return {
        "attempt_id": attempt.id,
        "assessment_title": "Initial Literacy Assessment",
        "assessment_version": attempt.assessment_version,
        "language": attempt.preferred_language,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "sections": sections,
        "answers": answers,
    }


def _validate_answer(question: models.AssessmentQuestion, attempt_question: models.AssessmentAttemptQuestion, answer: dict):
    if question.question_type in {"reading_mcq", "mcq"}:
        selected = answer.get("selected_option_id")
        options = _loads(attempt_question.shuffled_options_json, [])
        valid_ids = {option["id"] for option in options}
        if selected not in valid_ids:
            raise HTTPException(status_code=422, detail="Invalid answer")
    else:
        text = answer.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=422, detail="Required answer missing")
        max_len = 1000 if question.question_type == "short_response" else 300
        if len(text) > max_len:
            raise HTTPException(status_code=422, detail="Invalid answer")


def save_answers(db: Session, user: models.User, attempt_id: int, answers: list):
    attempt = _get_attempt_for_user(db, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")

    saved = 0
    for item in answers:
        attempt_question = (
            db.query(models.AssessmentAttemptQuestion)
            .filter(
                models.AssessmentAttemptQuestion.id == item.attempt_question_id,
                models.AssessmentAttemptQuestion.attempt_id == attempt.id,
            )
            .first()
        )
        if not attempt_question:
            raise HTTPException(status_code=422, detail="Invalid answer")
        question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == attempt_question.question_id).first()
        _validate_answer(question, attempt_question, item.answer)
        existing = (
            db.query(models.AssessmentAnswer)
            .filter(
                models.AssessmentAnswer.attempt_id == attempt.id,
                models.AssessmentAnswer.attempt_question_id == attempt_question.id,
            )
            .first()
        )
        if existing:
            existing.answer_json = _dumps(item.answer)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(models.AssessmentAnswer(
                attempt_id=attempt.id,
                attempt_question_id=attempt_question.id,
                question_id=question.id,
                answer_json=_dumps(item.answer),
                maximum_marks=attempt_question.maximum_marks,
            ))
        saved += 1
    db.commit()
    return {"saved": True, "saved_count": saved}


def normalize_text(value: str):
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[.!?।॥。]+$", "", text).strip()
    return text


def _score_copy(answer: str, reference: str, marks: int):
    normalized_answer = normalize_text(answer)
    normalized_reference = normalize_text(reference)
    if not normalized_answer and not normalized_reference:
        similarity = 1.0
    elif not normalized_answer or not normalized_reference:
        similarity = 0.0
    else:
        similarity = SequenceMatcher(None, normalized_answer, normalized_reference).ratio()
    if similarity >= 0.9:
        awarded = marks
    elif similarity >= 0.75:
        awarded = marks * 0.75
    elif similarity >= 0.5:
        awarded = marks * 0.5
    elif similarity >= 0.25:
        awarded = marks * 0.25
    else:
        awarded = 0
    return awarded, {"similarity": round(similarity * 100, 2), "normalized_answer": normalized_answer}


def _score_completion(answer: str, correct: dict, marks: int):
    normalized = normalize_text(answer).lower()
    accepted = [normalize_text(item).lower() for item in correct.get("accepted_answers", [])]
    keywords = [normalize_text(item).lower() for item in correct.get("required_keywords", [])]
    if normalized in accepted:
        return marks, {"match": "exact", "normalized_answer": normalized}
    matched = [keyword for keyword in keywords if keyword and keyword in normalized]
    if keywords and len(matched) == len(keywords):
        return marks * 0.75, {"match": "all_keywords", "matched_keywords": matched}
    if matched:
        return marks * (0.5 * len(matched) / len(keywords)), {"match": "partial_keywords", "matched_keywords": matched}
    return 0, {"match": "none", "normalized_answer": normalized}


def _score_short(answer: str, correct: dict, marks: int):
    normalized = normalize_text(answer)
    lowered = normalized.lower()
    keywords = [normalize_text(item).lower() for item in correct.get("required_keywords", [])]
    word_count = len(re.findall(r"\S+", normalized))
    sentences = [part for part in re.split(r"[.!?।॥。]+", answer) if part.strip()]
    keyword_matches = [keyword for keyword in keywords if keyword and keyword in lowered]
    points = 0
    points += 2 if normalized else 0
    points += 2 if word_count >= int(correct.get("minimum_words", 6)) else 0
    points += 2 if keyword_matches else 0
    points += 2 if sentences else 0
    points += 2 if len(normalized) >= 20 else 0
    return marks * (points / 10), {
        "rubric_points": points,
        "word_count": word_count,
        "matched_keywords": keyword_matches,
        "normalized_answer": normalized,
    }


def _score_answer(question, attempt_question, answer_row):
    answer = _loads(answer_row.answer_json, {})
    correct = _loads(question.correct_answer_json, {})
    if question.question_type in {"reading_mcq", "mcq"}:
        is_correct = answer.get("selected_option_id") == correct.get("correct_option_id")
        return (attempt_question.maximum_marks if is_correct else 0), is_correct, {"selected_option_id": answer.get("selected_option_id")}
    if question.question_type == "copy_typing":
        marks, details = _score_copy(answer.get("text", ""), correct.get("reference_text", ""), attempt_question.maximum_marks)
        return marks, None, details
    if question.question_type == "sentence_completion":
        marks, details = _score_completion(answer.get("text", ""), correct, attempt_question.maximum_marks)
        return marks, None, details
    marks, details = _score_short(answer.get("text", ""), correct, attempt_question.maximum_marks)
    return marks, None, details


def _percentage(obtained, total):
    if total <= 0:
        return 0.0
    return round((obtained / total) * 100, 2)


def classify_proficiency(overall, reading, typing):
    if overall >= 70:
        level = "advanced"
    elif overall >= 40:
        level = "intermediate"
    else:
        level = "beginner"
    if overall >= 70 and (reading < 50 or typing < 50):
        level = "intermediate"
    if overall >= 40 and (reading < 25 or typing < 25):
        level = "beginner"
    return level


def submit_attempt(db: Session, user: models.User, attempt_id: int):
    attempt = _get_attempt_for_user(db, attempt_id, user)
    if user.role != "learner":
        raise HTTPException(status_code=403, detail="User role not allowed")
    if attempt.status != "in_progress":
        existing = db.query(models.AssessmentResult).filter(models.AssessmentResult.attempt_id == attempt.id).first()
        if existing:
            return result_response(existing)
        raise HTTPException(status_code=409, detail="Attempt already submitted")

    rows = (
        db.query(models.AssessmentAttemptQuestion, models.AssessmentQuestion)
        .join(models.AssessmentQuestion, models.AssessmentAttemptQuestion.question_id == models.AssessmentQuestion.id)
        .filter(models.AssessmentAttemptQuestion.attempt_id == attempt.id)
        .all()
    )
    answers = {
        answer.attempt_question_id: answer
        for answer in db.query(models.AssessmentAnswer).filter(models.AssessmentAnswer.attempt_id == attempt.id).all()
    }
    if len(answers) != len(rows):
        raise HTTPException(status_code=422, detail="Required answer missing")

    totals = {section: {"awarded": 0.0, "max": 0.0} for section in SECTION_ORDER}
    for attempt_question, question in rows:
        answer_row = answers.get(attempt_question.id)
        if not answer_row:
            raise HTTPException(status_code=422, detail="Required answer missing")
        _validate_answer(question, attempt_question, _loads(answer_row.answer_json, {}))
        marks, is_correct, details = _score_answer(question, attempt_question, answer_row)
        answer_row.marks_awarded = round(float(marks), 2)
        answer_row.is_correct = is_correct
        answer_row.scoring_details_json = _dumps(details)
        answer_row.normalized_answer_json = _dumps({"normalized": details.get("normalized_answer")})
        answer_row.updated_at = datetime.now(timezone.utc)
        totals[attempt_question.section]["awarded"] += float(marks)
        totals[attempt_question.section]["max"] += attempt_question.maximum_marks

    reading_score = _percentage(totals["reading"]["awarded"], totals["reading"]["max"])
    typing_score = _percentage(totals["typing"]["awarded"], totals["typing"]["max"])
    mcq_score = _percentage(totals["mcq"]["awarded"], totals["mcq"]["max"])
    overall_score = round((reading_score * 0.35) + (typing_score * 0.35) + (mcq_score * 0.30), 2)
    level = classify_proficiency(overall_score, reading_score, typing_score)
    now = datetime.now(timezone.utc)
    attempt.status = "evaluated"
    attempt.submitted_at = now
    attempt.evaluated_at = now
    attempt.updated_at = now
    result = models.AssessmentResult(
        attempt_id=attempt.id,
        user_id=user.id,
        assessment_version=attempt.assessment_version,
        reading_score=reading_score,
        typing_score=typing_score,
        mcq_score=mcq_score,
        overall_score=overall_score,
        proficiency_level=level,
        completed_at=now,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result_response(result)


def result_response(result: models.AssessmentResult):
    return {
        "completed": True,
        "assessment_version": result.assessment_version,
        "completed_at": result.completed_at,
        "reading_score": result.reading_score,
        "typing_score": result.typing_score,
        "mcq_score": result.mcq_score,
        "overall_score": result.overall_score,
        "proficiency_level": result.proficiency_level,
    }


def get_result(db: Session, user: models.User):
    result = (
        db.query(models.AssessmentResult)
        .filter(
            models.AssessmentResult.user_id == user.id,
            models.AssessmentResult.assessment_version == ASSESSMENT_VERSION,
        )
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result_response(result)
