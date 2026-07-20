import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

import models
from gamification_service import (
    STREAK_SOURCE_PUZZLE_SET,
    activity_date_for,
    award_puzzle_set_completion_xp,
    record_qualified_activity,
)
from language_utils import normalize_language


PUZZLE_COMPLETION_MINIMUM_ACCURACY = 60.0
VIRAMA_MARKS = {"\u094d", "\u0bcd", "\u0c4d", "\u0ccd"}


def _strip_required(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def split_graphemes(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text or "")
    clusters: list[str] = []
    current = ""
    for char in normalized:
        category = unicodedata.category(char)
        if not current:
            current = char
        elif (
            category.startswith("M")
            or char == "\u200d"
            or current.endswith("\u200d")
            or current[-1] in VIRAMA_MARKS
        ):
            current += char
        else:
            clusters.append(current)
            current = char
    if current:
        clusters.append(current)
    return clusters


def _normalize_answer_text(value: str) -> str:
    return "".join(unicodedata.normalize("NFC", value or "").split())


def _rotate_or_reverse_tiles(tiles: list[str], answer: str) -> list[str]:
    if len(tiles) <= 1:
        return tiles
    reversed_tiles = list(reversed(tiles))
    if "".join(reversed_tiles) != answer:
        return reversed_tiles
    for offset in range(1, len(tiles)):
        candidate = tiles[offset:] + tiles[:offset]
        if "".join(candidate) != answer:
            return candidate
    return tiles


def _validate_jumbled_word(
    puzzle_data: dict[str, Any],
    answer_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    accepted_answers = answer_data.get("accepted_answers")
    if not isinstance(accepted_answers, list) or not accepted_answers:
        raise ValueError("jumbled_word accepted_answers are required")
    accepted_answers = [_strip_required(str(answer), "accepted_answer") for answer in accepted_answers]
    target_word = _strip_required(str(answer_data.get("target_word") or accepted_answers[0]), "target_word")
    canonical = _normalize_answer_text(target_word)
    canonical_graphemes = split_graphemes(canonical)
    if not canonical_graphemes:
        raise ValueError("target_word must contain at least one grapheme")
    canonical_counter = Counter(canonical_graphemes)
    for answer in accepted_answers:
        if Counter(split_graphemes(_normalize_answer_text(answer))) != canonical_counter:
            raise ValueError("accepted_answers must use the same grapheme multiset as target_word")

    tiles = puzzle_data.get("tiles")
    if tiles is None:
        tiles = canonical_graphemes
    if not isinstance(tiles, list):
        raise ValueError("jumbled_word tiles must be a list")
    normalized_tiles = [_strip_required(str(tile), "tile") for tile in tiles]

    if Counter(normalized_tiles) != canonical_counter:
        raise ValueError("jumbled_word tiles must exactly match target graphemes")

    if "".join(normalized_tiles) == canonical and len(set(canonical_graphemes)) > 1:
        normalized_tiles = _rotate_or_reverse_tiles(normalized_tiles, canonical)

    return (
        {
            "tiles": normalized_tiles,
            **({"clue": str(puzzle_data["clue"])} if puzzle_data.get("clue") else {}),
        },
        {
            "target_word": target_word,
            "accepted_answers": accepted_answers,
        },
    )


def _validate_matching(
    puzzle_data: dict[str, Any],
    answer_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    left_items = puzzle_data.get("left_items")
    right_items = puzzle_data.get("right_items")
    pairs = answer_data.get("pairs")
    if not isinstance(left_items, list) or not isinstance(right_items, list) or not isinstance(pairs, list):
        raise ValueError("matching puzzles require left_items, right_items, and pairs")
    if not left_items or len(left_items) != len(right_items):
        raise ValueError("matching sides must be non-empty and equal length")

    def normalize_items(items: list[Any], side: str) -> list[dict[str, str]]:
        normalized_items: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        seen_text: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"{side} items must be objects")
            item_id = _strip_required(str(item.get("id") or ""), f"{side}_id")
            text = _strip_required(str(item.get("text") or ""), f"{side}_text")
            if item_id in seen_ids or text in seen_text:
                raise ValueError(f"{side} items must be unique")
            seen_ids.add(item_id)
            seen_text.add(text)
            normalized_items.append({"id": item_id, "text": text})
        return normalized_items

    normalized_left = normalize_items(left_items, "left")
    normalized_right = normalize_items(right_items, "right")
    left_ids = {item["id"] for item in normalized_left}
    right_ids = {item["id"] for item in normalized_right}
    normalized_pairs: list[dict[str, str]] = []
    used_left: set[str] = set()
    used_right: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("matching pairs must be objects")
        left_id = _strip_required(str(pair.get("left_id") or ""), "left_id")
        right_id = _strip_required(str(pair.get("right_id") or ""), "right_id")
        if left_id not in left_ids or right_id not in right_ids:
            raise ValueError("matching pairs must reference displayed items")
        if left_id in used_left or right_id in used_right:
            raise ValueError("matching pairs must be one-to-one")
        used_left.add(left_id)
        used_right.add(right_id)
        normalized_pairs.append({"left_id": left_id, "right_id": right_id})
    if used_left != left_ids or used_right != right_ids:
        raise ValueError("matching pairs must cover every item")
    return {"left_items": normalized_left, "right_items": normalized_right}, {"pairs": normalized_pairs}


def validate_puzzle(
    puzzle_type: str,
    puzzle_data: dict[str, Any],
    answer_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if puzzle_type == "jumbled_word":
        return _validate_jumbled_word(puzzle_data, answer_data)
    if puzzle_type == "matching":
        return _validate_matching(puzzle_data, answer_data)
    raise ValueError("Unsupported puzzle type")


def _require_owned_set(db: Session, user_id: int, puzzle_set_id: int) -> models.PuzzleSet:
    puzzle_set = (
        db.query(models.PuzzleSet)
        .options(joinedload(models.PuzzleSet.puzzles))
        .filter(
            models.PuzzleSet.id == puzzle_set_id,
            models.PuzzleSet.user_id == user_id,
            models.PuzzleSet.is_active == True,
        )
        .first()
    )
    if not puzzle_set:
        raise HTTPException(status_code=404, detail="Puzzle set not found")
    return puzzle_set


def create_puzzle_set(
    db: Session,
    *,
    user_id: int,
    title: str,
    skill: str,
    difficulty: int,
    learning_language: str,
    comfortable_language: str,
    lesson_id: int | None = None,
    generated_lesson_plan_id: int | None = None,
) -> models.PuzzleSet:
    if lesson_id is None and generated_lesson_plan_id is None:
        raise ValueError("A puzzle set must be linked to a lesson or generated lesson plan")
    if not 1 <= int(difficulty) <= 5:
        raise ValueError("difficulty must be between 1 and 5")
    if lesson_id is not None and not db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first():
        raise ValueError("Lesson not found")
    if generated_lesson_plan_id is not None:
        generated_lesson_plan = (
            db.query(models.GeneratedLessonPlan)
            .join(models.GeneratedModule)
            .join(models.GeneratedCourse)
            .join(models.LearningPlan)
            .filter(
                models.GeneratedLessonPlan.id == generated_lesson_plan_id,
                models.LearningPlan.user_id == user_id,
                models.LearningPlan.is_active == True,
            )
            .first()
        )
        if not generated_lesson_plan:
            raise ValueError("Generated lesson plan not found")

    puzzle_set = models.PuzzleSet(
        user_id=user_id,
        lesson_id=lesson_id,
        generated_lesson_plan_id=generated_lesson_plan_id,
        title=_strip_required(title, "title"),
        skill=_strip_required(skill, "skill"),
        difficulty=int(difficulty),
        learning_language=normalize_language(learning_language),
        comfortable_language=normalize_language(comfortable_language),
        is_active=True,
    )
    db.add(puzzle_set)
    db.flush()
    return puzzle_set


def create_puzzles(
    db: Session,
    *,
    puzzle_set_id: int,
    puzzles: Iterable[dict[str, Any]],
) -> list[models.Puzzle]:
    puzzle_set = db.query(models.PuzzleSet).filter(models.PuzzleSet.id == puzzle_set_id).first()
    if not puzzle_set:
        raise ValueError("Puzzle set not found")

    created: list[models.Puzzle] = []
    for index, item in enumerate(puzzles, start=1):
        puzzle_type = _strip_required(str(item.get("puzzle_type") or ""), "puzzle_type")
        puzzle_data, answer_data = validate_puzzle(
            puzzle_type,
            item.get("puzzle_data") or {},
            item.get("answer_data") or {},
        )
        puzzle = models.Puzzle(
            puzzle_set_id=puzzle_set.id,
            puzzle_type=puzzle_type,
            instruction_text=_strip_required(str(item.get("instruction_text") or ""), "instruction_text"),
            instruction_translation=item.get("instruction_translation") or None,
            prompt_text=item.get("prompt_text") or None,
            prompt_translation=item.get("prompt_translation") or None,
            puzzle_data_json=_json_dumps(puzzle_data),
            answer_data_json=_json_dumps(answer_data),
            sequence_order=int(item.get("sequence_order") or index),
        )
        db.add(puzzle)
        created.append(puzzle)
    db.flush()
    return created


def list_puzzle_sets(db: Session, user_id: int) -> list[dict[str, Any]]:
    puzzle_sets = (
        db.query(models.PuzzleSet)
        .options(joinedload(models.PuzzleSet.puzzles))
        .filter(models.PuzzleSet.user_id == user_id, models.PuzzleSet.is_active == True)
        .order_by(models.PuzzleSet.created_at.desc(), models.PuzzleSet.id.desc())
        .all()
    )
    return [serialize_puzzle_set(item, get_puzzle_set_progress(db, user_id, item.id)) for item in puzzle_sets]


def get_puzzle_set(db: Session, user_id: int, puzzle_set_id: int) -> dict[str, Any]:
    puzzle_set = _require_owned_set(db, user_id, puzzle_set_id)
    return serialize_puzzle_set(puzzle_set, get_puzzle_set_progress(db, user_id, puzzle_set.id), include_puzzles=True)


def _latest_attempts_by_puzzle(db: Session, user_id: int, puzzle_ids: list[int]) -> dict[int, models.PuzzleAttempt]:
    if not puzzle_ids:
        return {}
    attempts = (
        db.query(models.PuzzleAttempt)
        .filter(models.PuzzleAttempt.user_id == user_id, models.PuzzleAttempt.puzzle_id.in_(puzzle_ids))
        .order_by(models.PuzzleAttempt.puzzle_id.asc(), models.PuzzleAttempt.attempt_number.desc())
        .all()
    )
    latest: dict[int, models.PuzzleAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.puzzle_id, attempt)
    return latest


def get_puzzle_set_progress(db: Session, user_id: int, puzzle_set_id: int) -> dict[str, Any]:
    puzzle_set = _require_owned_set(db, user_id, puzzle_set_id)
    puzzle_ids = [puzzle.id for puzzle in puzzle_set.puzzles]
    latest = _latest_attempts_by_puzzle(db, user_id, puzzle_ids)
    attempted_count = len(latest)
    correct_count = sum(1 for attempt in latest.values() if attempt.is_correct)
    total_puzzles = len(puzzle_ids)
    accuracy = round((correct_count / attempted_count) * 100, 2) if attempted_count else 0.0
    return {
        "total_puzzles": total_puzzles,
        "attempted_puzzles": attempted_count,
        "correct_puzzles": correct_count,
        "accuracy_percentage": accuracy,
        "is_complete": total_puzzles > 0 and attempted_count == total_puzzles,
    }


def _answer_is_correct(puzzle: models.Puzzle, submitted_answer: Any) -> bool:
    answer_data = _json_loads(puzzle.answer_data_json, {})
    if puzzle.puzzle_type == "jumbled_word":
        accepted = {
            _normalize_answer_text(str(answer))
            for answer in answer_data.get("accepted_answers", [])
        }
        if isinstance(submitted_answer, dict):
            if isinstance(submitted_answer.get("tiles"), list):
                answer = "".join(str(tile) for tile in submitted_answer["tiles"])
            else:
                answer = str(submitted_answer.get("answer") or "")
        elif isinstance(submitted_answer, list):
            answer = "".join(str(tile) for tile in submitted_answer)
        else:
            answer = str(submitted_answer or "")
        return _normalize_answer_text(answer) in accepted

    if puzzle.puzzle_type == "matching":
        expected = {
            str(pair["left_id"]): str(pair["right_id"])
            for pair in answer_data.get("pairs", [])
            if isinstance(pair, dict) and "left_id" in pair and "right_id" in pair
        }
        if isinstance(submitted_answer, dict) and isinstance(submitted_answer.get("pairs"), list):
            pairs = submitted_answer["pairs"]
        elif isinstance(submitted_answer, list):
            pairs = submitted_answer
        elif isinstance(submitted_answer, dict):
            pairs = [{"left_id": left, "right_id": right} for left, right in submitted_answer.items()]
        else:
            return False
        submitted: dict[str, str] = {}
        for pair in pairs:
            if not isinstance(pair, dict):
                return False
            left_id = str(pair.get("left_id") or "")
            right_id = str(pair.get("right_id") or "")
            if not left_id or not right_id or left_id in submitted:
                return False
            submitted[left_id] = right_id
        return submitted == expected

    return False


def _validate_submitted_answer_structure(puzzle: models.Puzzle, submitted_answer: Any) -> None:
    puzzle_data = _json_loads(puzzle.puzzle_data_json, {})
    if puzzle.puzzle_type == "jumbled_word":
        expected_tiles = [str(tile) for tile in puzzle_data.get("tiles", [])]
        if isinstance(submitted_answer, dict):
            if isinstance(submitted_answer.get("tiles"), list):
                submitted_tiles = [str(tile) for tile in submitted_answer["tiles"]]
            else:
                submitted_tiles = split_graphemes(_normalize_answer_text(str(submitted_answer.get("answer") or "")))
        elif isinstance(submitted_answer, list):
            submitted_tiles = [str(tile) for tile in submitted_answer]
        elif isinstance(submitted_answer, str):
            submitted_tiles = split_graphemes(_normalize_answer_text(submitted_answer))
        else:
            raise HTTPException(status_code=400, detail="Invalid jumbled-word answer")
        if Counter(submitted_tiles) != Counter(expected_tiles):
            raise HTTPException(status_code=400, detail="Jumbled-word answer must use exactly the displayed tiles")
        return

    if puzzle.puzzle_type == "matching":
        left_ids = {str(item["id"]) for item in puzzle_data.get("left_items", []) if isinstance(item, dict) and "id" in item}
        right_ids = {str(item["id"]) for item in puzzle_data.get("right_items", []) if isinstance(item, dict) and "id" in item}
        if isinstance(submitted_answer, dict) and isinstance(submitted_answer.get("pairs"), list):
            pairs = submitted_answer["pairs"]
        elif isinstance(submitted_answer, list):
            pairs = submitted_answer
        elif isinstance(submitted_answer, dict):
            pairs = [{"left_id": left, "right_id": right} for left, right in submitted_answer.items()]
        else:
            raise HTTPException(status_code=400, detail="Invalid matching answer")
        submitted_left: set[str] = set()
        submitted_right: set[str] = set()
        for pair in pairs:
            if not isinstance(pair, dict):
                raise HTTPException(status_code=400, detail="Matching answer pairs must be objects")
            left_id = str(pair.get("left_id") or "")
            right_id = str(pair.get("right_id") or "")
            if left_id not in left_ids or right_id not in right_ids:
                raise HTTPException(status_code=400, detail="Matching answer references unknown items")
            if left_id in submitted_left or right_id in submitted_right:
                raise HTTPException(status_code=400, detail="Matching answer must be one-to-one")
            submitted_left.add(left_id)
            submitted_right.add(right_id)
        if submitted_left != left_ids or submitted_right != right_ids:
            raise HTTPException(status_code=400, detail="Matching answer must include every displayed item")
        return

    raise HTTPException(status_code=400, detail="Unsupported puzzle type")


def _next_attempt_number(db: Session, user_id: int, puzzle_id: int) -> int:
    current = (
        db.query(func.coalesce(func.max(models.PuzzleAttempt.attempt_number), 0))
        .filter(models.PuzzleAttempt.user_id == user_id, models.PuzzleAttempt.puzzle_id == puzzle_id)
        .scalar()
        or 0
    )
    return int(current) + 1


def _maybe_award_completion_xp(
    db: Session,
    *,
    user_id: int,
    puzzle_set: models.PuzzleSet,
    completed_at: datetime,
) -> models.XPTransaction | None:
    progress = get_puzzle_set_progress(db, user_id, puzzle_set.id)
    if not progress["is_complete"] or progress["accuracy_percentage"] < PUZZLE_COMPLETION_MINIMUM_ACCURACY:
        return None

    activity_date = activity_date_for(completed_at)
    transaction = award_puzzle_set_completion_xp(
        db,
        user_id=user_id,
        puzzle_set_id=puzzle_set.id,
        activity_date=activity_date,
    )
    if transaction:
        record_qualified_activity(
            db,
            user_id=user_id,
            source_type=STREAK_SOURCE_PUZZLE_SET,
            source_id=puzzle_set.id,
            occurred_at=completed_at,
        )
    return transaction


def submit_puzzle_attempt(
    db: Session,
    *,
    user_id: int,
    puzzle_id: int,
    submitted_answer: Any,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    puzzle = (
        db.query(models.Puzzle)
        .options(joinedload(models.Puzzle.puzzle_set).joinedload(models.PuzzleSet.puzzles))
        .filter(models.Puzzle.id == puzzle_id)
        .first()
    )
    if not puzzle or not puzzle.puzzle_set or puzzle.puzzle_set.user_id != user_id or not puzzle.puzzle_set.is_active:
        raise HTTPException(status_code=404, detail="Puzzle not found")

    now = completed_at or datetime.now(timezone.utc)
    _validate_submitted_answer_structure(puzzle, submitted_answer)
    is_correct = _answer_is_correct(puzzle, submitted_answer)
    attempt = models.PuzzleAttempt(
        user_id=user_id,
        puzzle_id=puzzle.id,
        submitted_answer_json=_json_dumps(submitted_answer),
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        attempt_number=_next_attempt_number(db, user_id, puzzle.id),
        completed_at=now,
    )
    db.add(attempt)
    db.flush()

    xp_transaction = _maybe_award_completion_xp(
        db,
        user_id=user_id,
        puzzle_set=puzzle.puzzle_set,
        completed_at=now,
    )
    return {
        "attempt": serialize_attempt(attempt),
        "puzzle_set_progress": get_puzzle_set_progress(db, user_id, puzzle.puzzle_set_id),
        "xp_earned": xp_transaction.amount if xp_transaction else 0,
        "xp_transaction_id": xp_transaction.id if xp_transaction else None,
    }


def serialize_puzzle(puzzle: models.Puzzle) -> dict[str, Any]:
    return {
        "id": puzzle.id,
        "puzzle_set_id": puzzle.puzzle_set_id,
        "puzzle_type": puzzle.puzzle_type,
        "instruction_text": puzzle.instruction_text,
        "instruction_translation": puzzle.instruction_translation,
        "prompt_text": puzzle.prompt_text,
        "prompt_translation": puzzle.prompt_translation,
        "puzzle_data": _json_loads(puzzle.puzzle_data_json, {}),
        "sequence_order": puzzle.sequence_order,
        "created_at": puzzle.created_at,
    }


def serialize_attempt(attempt: models.PuzzleAttempt) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "user_id": attempt.user_id,
        "puzzle_id": attempt.puzzle_id,
        "submitted_answer": _json_loads(attempt.submitted_answer_json, {}),
        "is_correct": attempt.is_correct,
        "score": attempt.score,
        "attempt_number": attempt.attempt_number,
        "completed_at": attempt.completed_at,
    }


def serialize_puzzle_set(
    puzzle_set: models.PuzzleSet,
    progress: dict[str, Any],
    *,
    include_puzzles: bool = False,
) -> dict[str, Any]:
    response = {
        "id": puzzle_set.id,
        "user_id": puzzle_set.user_id,
        "lesson_id": puzzle_set.lesson_id,
        "generated_lesson_plan_id": puzzle_set.generated_lesson_plan_id,
        "title": puzzle_set.title,
        "skill": puzzle_set.skill,
        "difficulty": puzzle_set.difficulty,
        "learning_language": puzzle_set.learning_language,
        "comfortable_language": puzzle_set.comfortable_language,
        "is_active": puzzle_set.is_active,
        "created_at": puzzle_set.created_at,
        "updated_at": puzzle_set.updated_at,
        "progress": progress,
    }
    if include_puzzles:
        response["puzzles"] = [
            serialize_puzzle(puzzle)
            for puzzle in sorted(puzzle_set.puzzles, key=lambda item: item.sequence_order)
        ]
    return response
