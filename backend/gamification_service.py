import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

import models


logger = logging.getLogger(__name__)

XP_FIRST_LESSON_COMPLETION = 50
XP_PERFECT_LESSON_QUIZ_BONUS = 20
XP_INITIAL_ASSESSMENT_COMPLETION = 25
XP_FLASHCARD_REVIEW_SESSION = 10
XP_PUZZLE_SET_COMPLETION = 15
XP_REPEATED_LESSON_REVIEW = 0
XP_FAILED_OR_ABANDONED_ACTIVITY = 0

REWARD_FIRST_LESSON_COMPLETION = "first_lesson_completion"
REWARD_PERFECT_LESSON_QUIZ = "perfect_lesson_quiz"
REWARD_INITIAL_ASSESSMENT_COMPLETION = "initial_assessment_completion"
REWARD_FLASHCARD_REVIEW_SESSION = "flashcard_review_session"
REWARD_PUZZLE_SET_COMPLETION = "puzzle_set_completion"

DESCRIPTION_LESSON_COMPLETED = "gamification.description.lessonCompleted"
DESCRIPTION_PERFECT_QUIZ_BONUS = "gamification.description.perfectQuizBonus"
DESCRIPTION_ASSESSMENT_COMPLETED = "gamification.description.assessmentCompleted"
DESCRIPTION_FLASHCARD_SESSION_COMPLETED = "gamification.description.flashcardSessionCompleted"
DESCRIPTION_PUZZLE_SET_COMPLETED = "gamification.description.puzzleSetCompleted"

APPLICATION_TIMEZONE_NAME = "Asia/Kolkata"
_timezone_fallback_warning_logged = False


def get_application_timezone():
    global _timezone_fallback_warning_logged
    try:
        return ZoneInfo(APPLICATION_TIMEZONE_NAME)
    except ZoneInfoNotFoundError:
        if not _timezone_fallback_warning_logged:
            logger.warning(
                "IANA timezone %s is unavailable; using fixed UTC+05:30 fallback for streak dates.",
                APPLICATION_TIMEZONE_NAME,
            )
            _timezone_fallback_warning_logged = True
        return timezone(timedelta(hours=5, minutes=30))


APPLICATION_TIMEZONE = get_application_timezone()

STREAK_SOURCE_LESSON = "lesson"
STREAK_SOURCE_ASSESSMENT = "assessment"
STREAK_SOURCE_PUZZLE_SET = "puzzle_set"

STREAK_MESSAGE_START_TODAY = "gamification.streak.startToday"
STREAK_MESSAGE_TODAY_COMPLETED = "gamification.streak.todayCompleted"
STREAK_MESSAGE_CONTINUE_TOMORROW = "gamification.streak.continueTomorrow"
STREAK_MESSAGE_RESTARTED = "gamification.streak.restarted"

BADGE_DEFINITIONS = [
    {
        "badge_key": "initial_assessment",
        "name_key": "gamification.badge.initialAssessment.name",
        "description_key": "gamification.badge.initialAssessment.description",
        "category": "assessment",
        "icon_key": "clipboard",
        "requirement_type": "initial_assessment",
        "requirement_value": 1,
    },
    {
        "badge_key": "first_lesson",
        "name_key": "gamification.badge.firstLesson.name",
        "description_key": "gamification.badge.firstLesson.description",
        "category": "lesson",
        "icon_key": "book",
        "requirement_type": "first_lesson",
        "requirement_value": 1,
    },
    {
        "badge_key": "perfect_quiz",
        "name_key": "gamification.badge.perfectQuiz.name",
        "description_key": "gamification.badge.perfectQuiz.description",
        "category": "quiz",
        "icon_key": "sparkle",
        "requirement_type": "perfect_quiz",
        "requirement_value": 1,
    },
    {
        "badge_key": "streak_3",
        "name_key": "gamification.badge.streak3.name",
        "description_key": "gamification.badge.streak3.description",
        "category": "streak",
        "icon_key": "flame",
        "requirement_type": "streak_days",
        "requirement_value": 3,
    },
    {
        "badge_key": "streak_7",
        "name_key": "gamification.badge.streak7.name",
        "description_key": "gamification.badge.streak7.description",
        "category": "streak",
        "icon_key": "flame",
        "requirement_type": "streak_days",
        "requirement_value": 7,
    },
    {
        "badge_key": "xp_100",
        "name_key": "gamification.badge.xp100.name",
        "description_key": "gamification.badge.xp100.description",
        "category": "xp",
        "icon_key": "star",
        "requirement_type": "total_xp",
        "requirement_value": 100,
    },
    {
        "badge_key": "xp_500",
        "name_key": "gamification.badge.xp500.name",
        "description_key": "gamification.badge.xp500.description",
        "category": "xp",
        "icon_key": "trophy",
        "requirement_type": "total_xp",
        "requirement_value": 500,
    },
]


def _serialize_metadata(metadata: dict[str, Any] | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)


def get_or_create_summary(db: Session, user_id: int) -> models.GamificationSummary:
    summary = (
        db.query(models.GamificationSummary)
        .filter(models.GamificationSummary.user_id == user_id)
        .first()
    )
    if summary:
        return summary

    summary = models.GamificationSummary(user_id=user_id, total_xp=0)
    db.add(summary)
    db.flush()
    return summary


def award_xp(
    db: Session,
    *,
    user_id: int,
    amount: int,
    source_type: str,
    source_id: int,
    reward_key: str,
    description_key: str,
    metadata: dict[str, Any] | None = None,
) -> models.XPTransaction | None:
    if amount <= 0:
        return None

    existing = (
        db.query(models.XPTransaction)
        .filter(
            models.XPTransaction.user_id == user_id,
            models.XPTransaction.source_type == source_type,
            models.XPTransaction.source_id == source_id,
            models.XPTransaction.reward_key == reward_key,
        )
        .first()
    )
    if existing:
        return None

    transaction = models.XPTransaction(
        user_id=user_id,
        amount=amount,
        source_type=source_type,
        source_id=source_id,
        reward_key=reward_key,
        description_key=description_key,
        metadata_json=_serialize_metadata(metadata),
    )
    db.add(transaction)

    summary = get_or_create_summary(db, user_id)
    summary.total_xp += amount
    summary.updated_at = datetime.now(timezone.utc)
    db.flush()
    return transaction


def award_lesson_completion_xp(
    db: Session,
    *,
    user_id: int,
    lesson_id: int,
) -> models.XPTransaction | None:
    transaction = award_xp(
        db,
        user_id=user_id,
        amount=XP_FIRST_LESSON_COMPLETION,
        source_type="lesson",
        source_id=lesson_id,
        reward_key=REWARD_FIRST_LESSON_COMPLETION,
        description_key=DESCRIPTION_LESSON_COMPLETED,
        metadata={"lesson_id": lesson_id},
    )
    if transaction:
        record_qualified_activity(
            db,
            user_id=user_id,
            source_type=STREAK_SOURCE_LESSON,
            source_id=lesson_id,
        )
    return transaction


def award_perfect_quiz_xp(
    db: Session,
    *,
    user_id: int,
    lesson_id: int,
    score: float,
) -> models.XPTransaction | None:
    if score < 100:
        return None
    transaction = award_xp(
        db,
        user_id=user_id,
        amount=XP_PERFECT_LESSON_QUIZ_BONUS,
        source_type="lesson",
        source_id=lesson_id,
        reward_key=REWARD_PERFECT_LESSON_QUIZ,
        description_key=DESCRIPTION_PERFECT_QUIZ_BONUS,
        metadata={"lesson_id": lesson_id, "score": score},
    )
    if transaction:
        evaluate_user_badges(db, user_id)
    return transaction


def award_initial_assessment_xp(
    db: Session,
    *,
    user_id: int,
) -> models.XPTransaction | None:
    transaction = award_xp(
        db,
        user_id=user_id,
        amount=XP_INITIAL_ASSESSMENT_COMPLETION,
        source_type="assessment",
        source_id=user_id,
        reward_key=REWARD_INITIAL_ASSESSMENT_COMPLETION,
        description_key=DESCRIPTION_ASSESSMENT_COMPLETED,
        metadata={"user_id": user_id},
    )
    if transaction:
        record_qualified_activity(
            db,
            user_id=user_id,
            source_type=STREAK_SOURCE_ASSESSMENT,
            source_id=user_id,
        )
    return transaction


def award_flashcard_review_session_xp(
    db: Session,
    *,
    user_id: int,
    deck_id: int,
    activity_date: date,
) -> models.XPTransaction | None:
    reward_key = f"{REWARD_FLASHCARD_REVIEW_SESSION}:{activity_date.isoformat()}"
    transaction = award_xp(
        db,
        user_id=user_id,
        amount=XP_FLASHCARD_REVIEW_SESSION,
        source_type="flashcard_deck",
        source_id=deck_id,
        reward_key=reward_key,
        description_key=DESCRIPTION_FLASHCARD_SESSION_COMPLETED,
        metadata={"deck_id": deck_id, "activity_date": activity_date.isoformat()},
    )
    if transaction:
        evaluate_user_badges(db, user_id)
    return transaction


def award_puzzle_set_completion_xp(
    db: Session,
    *,
    user_id: int,
    puzzle_set_id: int,
    activity_date: date,
) -> models.XPTransaction | None:
    reward_key = f"{REWARD_PUZZLE_SET_COMPLETION}:{activity_date.isoformat()}"
    transaction = award_xp(
        db,
        user_id=user_id,
        amount=XP_PUZZLE_SET_COMPLETION,
        source_type="puzzle_set",
        source_id=puzzle_set_id,
        reward_key=reward_key,
        description_key=DESCRIPTION_PUZZLE_SET_COMPLETED,
        metadata={"puzzle_set_id": puzzle_set_id, "activity_date": activity_date.isoformat()},
    )
    if transaction:
        evaluate_user_badges(db, user_id)
    return transaction


def get_total_xp(db: Session, user_id: int) -> int:
    summary = (
        db.query(models.GamificationSummary)
        .filter(models.GamificationSummary.user_id == user_id)
        .first()
    )
    if summary:
        return int(summary.total_xp)
    return int(
        db.query(func.coalesce(func.sum(models.XPTransaction.amount), 0))
        .filter(models.XPTransaction.user_id == user_id)
        .scalar()
        or 0
    )


def get_recent_xp_transactions(
    db: Session,
    user_id: int,
    *,
    limit: int = 10,
) -> list[models.XPTransaction]:
    return (
        db.query(models.XPTransaction)
        .filter(models.XPTransaction.user_id == user_id)
        .order_by(models.XPTransaction.created_at.desc(), models.XPTransaction.id.desc())
        .limit(limit)
        .all()
    )


def get_xp_earned_since(db: Session, user_id: int, timestamp: datetime) -> int:
    return int(
        db.query(func.coalesce(func.sum(models.XPTransaction.amount), 0))
        .filter(
            models.XPTransaction.user_id == user_id,
            models.XPTransaction.created_at >= timestamp,
        )
        .scalar()
        or 0
    )


def get_week_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current - timedelta(days=7)


def activity_date_for(occurred_at: datetime | None = None) -> date:
    current = occurred_at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(APPLICATION_TIMEZONE).date()


def get_or_create_streak_summary(db: Session, user_id: int) -> models.StreakSummary:
    summary = (
        db.query(models.StreakSummary)
        .filter(models.StreakSummary.user_id == user_id)
        .first()
    )
    if summary:
        return summary

    summary = models.StreakSummary(
        user_id=user_id,
        current_streak=0,
        longest_streak=0,
    )
    db.add(summary)
    db.flush()
    return summary


def calculate_streak_state(
    *,
    current_streak: int,
    longest_streak: int,
    last_activity_date: date | None,
    activity_date: date,
) -> tuple[int, int, bool]:
    if last_activity_date is None:
        next_current = 1
        return next_current, max(longest_streak, next_current), True

    if activity_date <= last_activity_date:
        return current_streak, longest_streak, False

    if activity_date == last_activity_date + timedelta(days=1):
        next_current = current_streak + 1
        return next_current, max(longest_streak, next_current), False

    next_current = 1
    return next_current, max(longest_streak, next_current), True


def record_qualified_activity(
    db: Session,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    occurred_at: datetime | None = None,
) -> models.StreakSummary:
    qualified_at = occurred_at or datetime.now(timezone.utc)
    if qualified_at.tzinfo is None:
        qualified_at = qualified_at.replace(tzinfo=timezone.utc)
    activity_date = activity_date_for(qualified_at)

    existing_daily_activity = (
        db.query(models.DailyStreakActivity)
        .filter(
            models.DailyStreakActivity.user_id == user_id,
            models.DailyStreakActivity.activity_date == activity_date,
        )
        .first()
    )
    summary = get_or_create_streak_summary(db, user_id)
    if existing_daily_activity:
        return summary

    daily_activity = models.DailyStreakActivity(
        user_id=user_id,
        activity_date=activity_date,
        first_qualified_at=qualified_at,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(daily_activity)

    current_streak, longest_streak, restarted = calculate_streak_state(
        current_streak=summary.current_streak,
        longest_streak=summary.longest_streak,
        last_activity_date=summary.last_activity_date,
        activity_date=activity_date,
    )
    summary.current_streak = current_streak
    summary.longest_streak = longest_streak
    summary.last_activity_date = activity_date
    if restarted:
        summary.streak_started_at = qualified_at
    summary.updated_at = datetime.now(timezone.utc)
    db.flush()
    evaluate_user_badges(db, user_id)
    return summary


def seed_badges(db: Session) -> list[models.Badge]:
    seeded_badges = []
    for definition in BADGE_DEFINITIONS:
        badge = (
            db.query(models.Badge)
            .filter(models.Badge.badge_key == definition["badge_key"])
            .first()
        )
        if badge is None:
            badge = models.Badge(**definition, is_active=True)
            db.add(badge)
            db.flush()
        else:
            for key, value in definition.items():
                setattr(badge, key, value)
            badge.is_active = True
        seeded_badges.append(badge)
    db.flush()
    return seeded_badges


def _first_xp_transaction(
    db: Session,
    user_id: int,
    reward_key: str,
) -> models.XPTransaction | None:
    return (
        db.query(models.XPTransaction)
        .filter(
            models.XPTransaction.user_id == user_id,
            models.XPTransaction.reward_key == reward_key,
        )
        .order_by(models.XPTransaction.created_at.asc(), models.XPTransaction.id.asc())
        .first()
    )


def _completed_lesson_source(db: Session, user_id: int) -> int | None:
    progress = (
        db.query(models.LearnerProgress)
        .filter(
            models.LearnerProgress.user_id == user_id,
            models.LearnerProgress.completion_status == "completed",
        )
        .order_by(models.LearnerProgress.completed_at.asc().nullslast(), models.LearnerProgress.id.asc())
        .first()
    )
    return progress.lesson_id if progress else None


def _assessment_source(db: Session, user_id: int) -> int | None:
    transaction = _first_xp_transaction(db, user_id, REWARD_INITIAL_ASSESSMENT_COMPLETION)
    if transaction:
        return transaction.source_id
    result = (
        db.query(models.AssessmentResult)
        .filter(models.AssessmentResult.user_id == user_id)
        .order_by(models.AssessmentResult.completed_at.asc(), models.AssessmentResult.id.asc())
        .first()
    )
    return result.id if result else None


def _perfect_quiz_source(db: Session, user_id: int) -> int | None:
    transaction = _first_xp_transaction(db, user_id, REWARD_PERFECT_LESSON_QUIZ)
    if transaction:
        return transaction.source_id
    attempt = (
        db.query(models.LessonAttempt)
        .filter(models.LessonAttempt.user_id == user_id, models.LessonAttempt.score >= 100)
        .order_by(models.LessonAttempt.completed_at.asc().nullslast(), models.LessonAttempt.id.asc())
        .first()
    )
    return attempt.lesson_id if attempt else None


def _badge_source_for_requirement(
    db: Session,
    user_id: int,
    badge: models.Badge,
) -> tuple[str, int] | None:
    if badge.requirement_type == "initial_assessment":
        source_id = _assessment_source(db, user_id)
        return ("assessment", source_id) if source_id is not None else None

    if badge.requirement_type == "first_lesson":
        transaction = _first_xp_transaction(db, user_id, REWARD_FIRST_LESSON_COMPLETION)
        source_id = transaction.source_id if transaction else _completed_lesson_source(db, user_id)
        return ("lesson", source_id) if source_id is not None else None

    if badge.requirement_type == "perfect_quiz":
        source_id = _perfect_quiz_source(db, user_id)
        return ("lesson", source_id) if source_id is not None else None

    if badge.requirement_type == "streak_days":
        summary = (
            db.query(models.StreakSummary)
            .filter(models.StreakSummary.user_id == user_id)
            .first()
        )
        if summary and summary.longest_streak >= badge.requirement_value:
            return ("streak", user_id)
        return None

    if badge.requirement_type == "total_xp":
        if get_total_xp(db, user_id) >= badge.requirement_value:
            return ("xp", user_id)
        return None

    return None


def award_badge(
    db: Session,
    *,
    user_id: int,
    badge: models.Badge,
    source_type: str,
    source_id: int,
) -> models.UserBadge | None:
    existing = (
        db.query(models.UserBadge)
        .filter(
            models.UserBadge.user_id == user_id,
            models.UserBadge.badge_id == badge.id,
        )
        .first()
    )
    if existing:
        return None

    user_badge = models.UserBadge(
        user_id=user_id,
        badge_id=badge.id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(user_badge)
    db.flush()
    return user_badge


def evaluate_user_badges(db: Session, user_id: int) -> list[models.UserBadge]:
    seed_badges(db)
    earned_badges = []
    badges = (
        db.query(models.Badge)
        .filter(models.Badge.is_active == True)
        .order_by(models.Badge.id.asc())
        .all()
    )
    for badge in badges:
        source = _badge_source_for_requirement(db, user_id, badge)
        if source is None:
            continue
        awarded = award_badge(
            db,
            user_id=user_id,
            badge=badge,
            source_type=source[0],
            source_id=source[1],
        )
        if awarded:
            earned_badges.append(awarded)
    return earned_badges


def _serialize_badge(
    badge: models.Badge,
    user_badge: models.UserBadge | None = None,
) -> dict[str, Any]:
    return {
        "badge_key": badge.badge_key,
        "name_key": badge.name_key,
        "description_key": badge.description_key,
        "category": badge.category,
        "icon_key": badge.icon_key,
        "requirement_type": badge.requirement_type,
        "requirement_value": badge.requirement_value,
        "is_active": badge.is_active,
        "earned_at": user_badge.earned_at if user_badge else None,
        "source_type": user_badge.source_type if user_badge else None,
        "source_id": user_badge.source_id if user_badge else None,
    }


def get_user_badges(db: Session, user_id: int) -> dict[str, Any]:
    evaluate_user_badges(db, user_id)
    badges = (
        db.query(models.Badge)
        .filter(models.Badge.is_active == True)
        .order_by(models.Badge.id.asc())
        .all()
    )
    user_badges = (
        db.query(models.UserBadge)
        .options(joinedload(models.UserBadge.badge))
        .filter(models.UserBadge.user_id == user_id)
        .all()
    )
    earned_by_badge_id = {user_badge.badge_id: user_badge for user_badge in user_badges}
    earned_badges = [
        _serialize_badge(badge, earned_by_badge_id[badge.id])
        for badge in badges
        if badge.id in earned_by_badge_id
    ]
    locked_badges = [
        _serialize_badge(badge)
        for badge in badges
        if badge.id not in earned_by_badge_id
    ]
    recently_earned_badges = [
        _serialize_badge(user_badge.badge, user_badge)
        for user_badge in sorted(user_badges, key=lambda item: (item.earned_at, item.id), reverse=True)[:5]
        if user_badge.badge and user_badge.badge.is_active
    ]
    return {
        "earned_badges": earned_badges,
        "locked_badges": locked_badges,
        "earned_count": len(earned_badges),
        "total_count": len(badges),
        "recently_earned_badges": recently_earned_badges,
    }


def has_completed_today(
    db: Session,
    user_id: int,
    *,
    now: datetime | None = None,
) -> bool:
    today = activity_date_for(now)
    return (
        db.query(models.DailyStreakActivity)
        .filter(
            models.DailyStreakActivity.user_id == user_id,
            models.DailyStreakActivity.activity_date == today,
        )
        .first()
        is not None
    )


def get_next_streak_message_key(summary: models.StreakSummary | None, completed_today: bool) -> str:
    if not summary or summary.current_streak == 0:
        return STREAK_MESSAGE_START_TODAY
    if completed_today and summary.current_streak == 1 and summary.longest_streak > 1:
        return STREAK_MESSAGE_RESTARTED
    if completed_today:
        return STREAK_MESSAGE_CONTINUE_TOMORROW
    return STREAK_MESSAGE_START_TODAY


def get_streak_summary(db: Session, user_id: int) -> dict[str, Any]:
    summary = (
        db.query(models.StreakSummary)
        .filter(models.StreakSummary.user_id == user_id)
        .first()
    )
    completed_today = has_completed_today(db, user_id)
    return {
        "current_streak": summary.current_streak if summary else 0,
        "longest_streak": summary.longest_streak if summary else 0,
        "last_activity_date": summary.last_activity_date if summary else None,
        "completed_today": completed_today,
        "next_streak_message_key": get_next_streak_message_key(summary, completed_today),
        "streak_timezone": APPLICATION_TIMEZONE_NAME,
    }
