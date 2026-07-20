from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from gamification_service import activity_date_for, award_flashcard_review_session_xp
from language_utils import normalize_language


MASTERY_MIN = 0
MASTERY_MAX = 5
FLASHCARD_SESSION_MINIMUM_DISTINCT_REVIEWS = 5


def _strip_required(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _clamp_mastery(value: int) -> int:
    return min(MASTERY_MAX, max(MASTERY_MIN, value))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _require_owned_deck(db: Session, user_id: int, deck_id: int) -> models.FlashcardDeck:
    deck = (
        db.query(models.FlashcardDeck)
        .options(joinedload(models.FlashcardDeck.flashcards))
        .filter(
            models.FlashcardDeck.id == deck_id,
            models.FlashcardDeck.user_id == user_id,
            models.FlashcardDeck.is_active == True,
        )
        .first()
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Flashcard deck not found")
    return deck


def _progress_for_card(
    db: Session,
    *,
    user_id: int,
    flashcard_id: int,
) -> models.FlashcardProgress:
    progress = (
        db.query(models.FlashcardProgress)
        .filter(
            models.FlashcardProgress.user_id == user_id,
            models.FlashcardProgress.flashcard_id == flashcard_id,
        )
        .first()
    )
    if progress:
        return progress

    progress = models.FlashcardProgress(
        user_id=user_id,
        flashcard_id=flashcard_id,
        review_count=0,
        correct_count=0,
        incorrect_count=0,
        mastery_level=0,
        review_interval_days=1,
    )
    db.add(progress)
    db.flush()
    return progress


def create_flashcard_deck(
    db: Session,
    *,
    user_id: int,
    title: str,
    skill: str,
    learning_language: str,
    comfortable_language: str,
    lesson_id: int | None = None,
    generated_lesson_plan_id: int | None = None,
) -> models.FlashcardDeck:
    if lesson_id is None and generated_lesson_plan_id is None:
        raise ValueError("A flashcard deck must be linked to a lesson or generated lesson plan")

    if lesson_id is not None:
        lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
        if not lesson:
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

    deck = models.FlashcardDeck(
        user_id=user_id,
        lesson_id=lesson_id,
        generated_lesson_plan_id=generated_lesson_plan_id,
        title=_strip_required(title, "title"),
        skill=_strip_required(skill, "skill"),
        learning_language=normalize_language(learning_language),
        comfortable_language=normalize_language(comfortable_language),
        is_active=True,
    )
    db.add(deck)
    db.flush()
    return deck


def create_flashcards(
    db: Session,
    *,
    deck_id: int,
    cards: Iterable[dict[str, Any]],
) -> list[models.Flashcard]:
    deck = db.query(models.FlashcardDeck).filter(models.FlashcardDeck.id == deck_id).first()
    if not deck:
        raise ValueError("Flashcard deck not found")

    created_cards: list[models.Flashcard] = []
    for index, card in enumerate(cards, start=1):
        sequence_order = int(card.get("sequence_order") or index)
        flashcard = models.Flashcard(
            deck_id=deck.id,
            front_text=_strip_required(str(card.get("front_text") or ""), "front_text"),
            back_text=_strip_required(str(card.get("back_text") or ""), "back_text"),
            example_text=(card.get("example_text") or None),
            example_translation=(card.get("example_translation") or None),
            pronunciation_text=(card.get("pronunciation_text") or None),
            sequence_order=sequence_order,
        )
        db.add(flashcard)
        created_cards.append(flashcard)

    db.flush()
    return created_cards


def list_flashcard_decks(db: Session, user_id: int) -> list[dict[str, Any]]:
    decks = (
        db.query(models.FlashcardDeck)
        .options(joinedload(models.FlashcardDeck.flashcards))
        .filter(models.FlashcardDeck.user_id == user_id, models.FlashcardDeck.is_active == True)
        .order_by(models.FlashcardDeck.created_at.desc(), models.FlashcardDeck.id.desc())
        .all()
    )
    return [serialize_deck(deck, get_flashcard_deck_progress(db, user_id, deck.id)) for deck in decks]


def get_flashcard_deck(db: Session, user_id: int, deck_id: int) -> dict[str, Any]:
    deck = _require_owned_deck(db, user_id, deck_id)
    return serialize_deck(deck, get_flashcard_deck_progress(db, user_id, deck.id), include_cards=True, user_id=user_id, db=db)


def _is_due(progress: models.FlashcardProgress | None, now: datetime) -> bool:
    return progress is None or progress.next_review_at is None or _as_utc(progress.next_review_at) <= _as_utc(now)


def get_due_flashcards(
    db: Session,
    *,
    user_id: int,
    deck_id: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    deck = _require_owned_deck(db, user_id, deck_id)
    resolved_now = now or datetime.now(timezone.utc)
    progress_by_card = {
        progress.flashcard_id: progress
        for progress in db.query(models.FlashcardProgress)
        .filter(
            models.FlashcardProgress.user_id == user_id,
            models.FlashcardProgress.flashcard_id.in_([card.id for card in deck.flashcards] or [0]),
        )
        .all()
    }
    return [
        serialize_card(card, progress_by_card.get(card.id))
        for card in sorted(deck.flashcards, key=lambda item: item.sequence_order)
        if _is_due(progress_by_card.get(card.id), resolved_now)
    ]


def _reviewed_card_ids_for_activity_date(
    db: Session,
    *,
    user_id: int,
    deck: models.FlashcardDeck,
    activity_date,
) -> set[int]:
    card_ids = [card.id for card in deck.flashcards]
    if not card_ids:
        return set()
    progress_records = (
        db.query(models.FlashcardProgress)
        .filter(
            models.FlashcardProgress.user_id == user_id,
            models.FlashcardProgress.flashcard_id.in_(card_ids),
            models.FlashcardProgress.last_reviewed_at.isnot(None),
        )
        .all()
    )
    return {
        progress.flashcard_id
        for progress in progress_records
        if progress.last_reviewed_at and activity_date_for(progress.last_reviewed_at) == activity_date
    }


def _qualifies_for_session_xp(db: Session, *, user_id: int, deck: models.FlashcardDeck, activity_date) -> bool:
    total_cards = len(deck.flashcards)
    if total_cards <= 0:
        return False
    required_reviews = min(FLASHCARD_SESSION_MINIMUM_DISTINCT_REVIEWS, total_cards)
    reviewed_card_ids = _reviewed_card_ids_for_activity_date(
        db,
        user_id=user_id,
        deck=deck,
        activity_date=activity_date,
    )
    return len(reviewed_card_ids) >= required_reviews


def record_flashcard_review(
    db: Session,
    *,
    user_id: int,
    flashcard_id: int,
    outcome: str,
    reviewed_at: datetime | None = None,
) -> dict[str, Any]:
    if outcome not in {"need_practice", "know"}:
        raise HTTPException(status_code=422, detail="Invalid flashcard review outcome")

    flashcard = (
        db.query(models.Flashcard)
        .options(joinedload(models.Flashcard.deck).joinedload(models.FlashcardDeck.flashcards))
        .filter(models.Flashcard.id == flashcard_id)
        .first()
    )
    if not flashcard or not flashcard.deck or flashcard.deck.user_id != user_id or not flashcard.deck.is_active:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    now = reviewed_at or datetime.now(timezone.utc)
    progress = _progress_for_card(db, user_id=user_id, flashcard_id=flashcard.id)
    progress.review_count += 1
    progress.updated_at = now
    progress.last_reviewed_at = now

    if outcome == "know":
        progress.correct_count += 1
        progress.mastery_level = _clamp_mastery(progress.mastery_level + 1)
        progress.review_interval_days = min(30, max(1, progress.review_interval_days * 2))
    else:
        progress.incorrect_count += 1
        progress.mastery_level = _clamp_mastery(progress.mastery_level - 1)
        progress.review_interval_days = 1

    progress.next_review_at = now + timedelta(days=progress.review_interval_days)
    db.flush()

    activity_date = activity_date_for(now)
    xp_transaction = None
    if _qualifies_for_session_xp(db, user_id=user_id, deck=flashcard.deck, activity_date=activity_date):
        xp_transaction = award_flashcard_review_session_xp(
            db,
            user_id=user_id,
            deck_id=flashcard.deck_id,
            activity_date=activity_date,
        )

    return {
        "flashcard": serialize_card(flashcard, progress),
        "progress": serialize_progress(progress),
        "deck_progress": get_flashcard_deck_progress(db, user_id, flashcard.deck_id),
        "xp_earned": xp_transaction.amount if xp_transaction else 0,
        "xp_transaction_id": xp_transaction.id if xp_transaction else None,
    }


def get_flashcard_deck_progress(db: Session, user_id: int, deck_id: int) -> dict[str, Any]:
    deck = _require_owned_deck(db, user_id, deck_id)
    card_ids = [card.id for card in deck.flashcards]
    progress_records = []
    if card_ids:
        progress_records = (
            db.query(models.FlashcardProgress)
            .filter(
                models.FlashcardProgress.user_id == user_id,
                models.FlashcardProgress.flashcard_id.in_(card_ids),
            )
            .all()
        )
    progress_by_card = {progress.flashcard_id: progress for progress in progress_records}
    now = datetime.now(timezone.utc)
    due_count = sum(1 for card in deck.flashcards if _is_due(progress_by_card.get(card.id), now))
    mastered_count = sum(1 for progress in progress_records if progress.mastery_level >= MASTERY_MAX)
    reviewed_count = sum(1 for progress in progress_records if progress.review_count > 0)
    return {
        "total_cards": len(deck.flashcards),
        "due_cards": due_count,
        "reviewed_cards": reviewed_count,
        "mastered_cards": mastered_count,
    }


def serialize_progress(progress: models.FlashcardProgress | None) -> dict[str, Any] | None:
    if progress is None:
        return None
    return {
        "id": progress.id,
        "user_id": progress.user_id,
        "flashcard_id": progress.flashcard_id,
        "review_count": progress.review_count,
        "correct_count": progress.correct_count,
        "incorrect_count": progress.incorrect_count,
        "mastery_level": progress.mastery_level,
        "review_interval_days": progress.review_interval_days,
        "next_review_at": progress.next_review_at,
        "last_reviewed_at": progress.last_reviewed_at,
        "created_at": progress.created_at,
        "updated_at": progress.updated_at,
    }


def serialize_card(card: models.Flashcard, progress: models.FlashcardProgress | None = None) -> dict[str, Any]:
    return {
        "id": card.id,
        "deck_id": card.deck_id,
        "front_text": card.front_text,
        "back_text": card.back_text,
        "example_text": card.example_text,
        "example_translation": card.example_translation,
        "pronunciation_text": card.pronunciation_text,
        "sequence_order": card.sequence_order,
        "created_at": card.created_at,
        "progress": serialize_progress(progress),
    }


def serialize_deck(
    deck: models.FlashcardDeck,
    progress: dict[str, Any],
    *,
    include_cards: bool = False,
    user_id: int | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    response = {
        "id": deck.id,
        "user_id": deck.user_id,
        "lesson_id": deck.lesson_id,
        "generated_lesson_plan_id": deck.generated_lesson_plan_id,
        "title": deck.title,
        "skill": deck.skill,
        "learning_language": deck.learning_language,
        "comfortable_language": deck.comfortable_language,
        "is_active": deck.is_active,
        "created_at": deck.created_at,
        "updated_at": deck.updated_at,
        "progress": progress,
    }
    if include_cards:
        progress_by_card = {}
        if user_id is not None and db is not None and deck.flashcards:
            progress_by_card = {
                item.flashcard_id: item
                for item in db.query(models.FlashcardProgress)
                .filter(
                    models.FlashcardProgress.user_id == user_id,
                    models.FlashcardProgress.flashcard_id.in_([card.id for card in deck.flashcards]),
                )
                .all()
            }
        response["cards"] = [
            serialize_card(card, progress_by_card.get(card.id))
            for card in sorted(deck.flashcards, key=lambda item: item.sequence_order)
        ]
    return response
