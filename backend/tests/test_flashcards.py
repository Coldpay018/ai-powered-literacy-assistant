import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import models
from database import Base
from flashcard_service import (
    create_flashcard_deck,
    create_flashcards,
    get_due_flashcards,
    record_flashcard_review,
)
from gamification_service import XP_FLASHCARD_REVIEW_SESSION
from main import app, get_db
from schema_updates import apply_sqlite_schema_updates


class FlashcardTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

        db = self.Session()
        self.user = self._create_user(db, "flash@example.com", comfortable_language="kn", learning_language="hi")
        self.other_user = self._create_user(db, "other-flash@example.com")
        self.lesson = self._create_lesson(db)
        self.deck = create_flashcard_deck(
            db,
            user_id=self.user.id,
            lesson_id=self.lesson.id,
            title="Kannada meanings",
            skill="reading",
            learning_language="kn-IN",
            comfortable_language="English",
        )
        self.cards = create_flashcards(
            db,
            deck_id=self.deck.id,
            cards=[
                {
                    "front_text": "ಮನೆ",
                    "back_text": "House",
                    "example_text": "ಇದು ನನ್ನ ಮನೆ.",
                    "example_translation": "This is my house.",
                    "pronunciation_text": "ಮನೆ",
                },
                {"front_text": "ನೀರು", "back_text": "Water", "example_text": "ನೀರು ಕುಡಿ.", "example_translation": "Drink water."},
                {"front_text": "ಪುಸ್ತಕ", "back_text": "Book", "example_text": "ಪುಸ್ತಕ ಓದಿ.", "example_translation": "Read a book."},
                {"front_text": "ಶಾಲೆ", "back_text": "School", "example_text": "ನಾನು ಶಾಲೆಗೆ ಹೋಗುತ್ತೇನೆ.", "example_translation": "I go to school."},
                {"front_text": "ಸ್ನೇಹಿತ", "back_text": "Friend", "example_text": "ಅವನು ನನ್ನ ಸ್ನೇಹಿತ.", "example_translation": "He is my friend."},
                {"front_text": "ಆಹಾರ", "back_text": "Food", "example_text": "ಆಹಾರ ತಿನ್ನಿ.", "example_translation": "Eat food."},
            ],
        )
        db.commit()
        db.close()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.token = auth.create_access_token(self.user.id)
        self.other_token = auth.create_access_token(self.other_user.id)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _create_user(self, db, email, comfortable_language="en", learning_language="kn"):
        user = models.User(
            full_name="Flash Learner",
            age=20,
            email=email,
            hashed_password=auth.hash_password("password123"),
            comfortable_language=comfortable_language,
            learning_language=learning_language,
            preferred_language=comfortable_language,
            experience_level="Beginner",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    def _create_lesson(self, db):
        course = models.Course(
            title="Flash Course",
            description="Flash course",
            skill="reading",
            difficulty_level="beginner",
            language="kn",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="Flash Module",
            description="Flash module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        lesson = models.Lesson(
            course_id=course.id,
            module_id=module.id,
            title="Flash Lesson",
            description="Flash lesson",
            content="Vocabulary",
            skill="reading",
            skill_type="reading",
            difficulty_level="beginner",
            proficiency_level="beginner",
            language="kn",
            difficulty_order=1,
            estimated_minutes=10,
            estimated_duration_minutes=10,
            sequence_order=1,
        )
        db.add(lesson)
        db.flush()
        return lesson

    def _auth_headers(self, token=None):
        return {"Authorization": f"Bearer {token or self.token}"}

    def _total_xp(self):
        db = self.Session()
        try:
            return db.query(func.coalesce(func.sum(models.XPTransaction.amount), 0)).scalar()
        finally:
            db.close()

    def test_deck_and_card_creation_preserves_language_fields_and_unicode(self):
        db = self.Session()
        try:
            deck = db.get(models.FlashcardDeck, self.deck.id)
            self.assertEqual(deck.learning_language, "kn")
            self.assertEqual(deck.comfortable_language, "en")
            self.assertEqual(deck.flashcards[0].front_text, "ಮನೆ")
            self.assertEqual(deck.flashcards[0].back_text, "House")
        finally:
            db.close()

    def test_generated_lesson_plan_deck_creation_is_supported(self):
        db = self.Session()
        try:
            plan = models.LearningPlan(
                user_id=self.user.id,
                status="ready",
                comfortable_language="en",
                learning_language="kn",
                learner_summary="Learner",
                weakest_skills='["vocabulary"]',
                strongest_skills="[]",
                generation_version="test",
                is_active=True,
            )
            db.add(plan)
            db.flush()
            course = models.GeneratedCourse(
                learning_plan_id=plan.id,
                title="Generated",
                description="Generated",
                primary_skill="vocabulary",
                difficulty=1,
                sequence_order=1,
                is_unlocked=True,
                completion_status="not_started",
            )
            db.add(course)
            db.flush()
            module = models.GeneratedModule(generated_course_id=course.id, title="Module", description="Module", sequence_order=1)
            db.add(module)
            db.flush()
            lesson_plan = models.GeneratedLessonPlan(
                generated_module_id=module.id,
                title="Generated lesson",
                learning_objective="Learn words",
                skill="vocabulary",
                difficulty=1,
                sequence_order=1,
                content_status="not_generated",
            )
            db.add(lesson_plan)
            db.flush()
            deck = create_flashcard_deck(
                db,
                user_id=self.user.id,
                generated_lesson_plan_id=lesson_plan.id,
                title="Generated deck",
                skill="vocabulary",
                learning_language="kn",
                comfortable_language="en",
            )
            self.assertEqual(deck.generated_lesson_plan_id, lesson_plan.id)
        finally:
            db.rollback()
            db.close()

    def test_user_access_isolation_and_unauthenticated_access(self):
        self.assertIn(self.client.get("/flashcards/decks").status_code, {401, 403})
        own = self.client.get("/flashcards/decks", headers=self._auth_headers())
        self.assertEqual(own.status_code, 200)
        self.assertEqual(len(own.json()), 1)

        denied = self.client.get(f"/flashcards/decks/{self.deck.id}", headers=self._auth_headers(self.other_token))
        self.assertEqual(denied.status_code, 404)
        denied_due = self.client.get(f"/flashcards/decks/{self.deck.id}/due", headers=self._auth_headers(self.other_token))
        self.assertEqual(denied_due.status_code, 404)

    def test_opening_or_revealing_cards_awards_no_xp(self):
        self.assertEqual(self._total_xp(), 0)
        self.assertEqual(self.client.get(f"/flashcards/decks/{self.deck.id}", headers=self._auth_headers()).status_code, 200)
        self.assertEqual(self.client.get(f"/flashcards/decks/{self.deck.id}/due", headers=self._auth_headers()).status_code, 200)
        self.assertEqual(self._total_xp(), 0)

    def test_need_practice_review_behavior_and_due_scheduling(self):
        db = self.Session()
        try:
            result = record_flashcard_review(
                db,
                user_id=self.user.id,
                flashcard_id=self.cards[0].id,
                outcome="need_practice",
                reviewed_at=datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc),
            )
            progress = result["progress"]
            self.assertEqual(progress["review_count"], 1)
            self.assertEqual(progress["incorrect_count"], 1)
            self.assertEqual(progress["correct_count"], 0)
            self.assertEqual(progress["mastery_level"], 0)
            self.assertEqual(progress["review_interval_days"], 1)
            self.assertEqual(progress["next_review_at"], datetime(2026, 7, 21, 4, 0, tzinfo=timezone.utc))
        finally:
            db.rollback()
            db.close()

    def test_know_review_behavior_mastery_clamping_and_due_filtering(self):
        db = self.Session()
        try:
            now = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
            for _ in range(8):
                record_flashcard_review(db, user_id=self.user.id, flashcard_id=self.cards[0].id, outcome="know", reviewed_at=now)
            progress = (
                db.query(models.FlashcardProgress)
                .filter(
                    models.FlashcardProgress.user_id == self.user.id,
                    models.FlashcardProgress.flashcard_id == self.cards[0].id,
                )
                .one()
            )
            self.assertEqual(progress.correct_count, 8)
            self.assertEqual(progress.mastery_level, 5)
            self.assertLessEqual(progress.review_interval_days, 30)
            due = get_due_flashcards(db, user_id=self.user.id, deck_id=self.deck.id, now=now)
            self.assertEqual({card["id"] for card in due}, {card.id for card in self.cards[1:]})
        finally:
            db.rollback()
            db.close()

    def test_duplicate_progress_records_are_prevented(self):
        db = self.Session()
        try:
            first = models.FlashcardProgress(user_id=self.user.id, flashcard_id=self.cards[0].id)
            second = models.FlashcardProgress(user_id=self.user.id, flashcard_id=self.cards[0].id)
            db.add_all([first, second])
            with self.assertRaises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()

    def test_meaningful_session_awards_xp_once_per_deck_day(self):
        db = self.Session()
        try:
            now = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
            xp_earned = []
            for card in self.cards[:5]:
                result = record_flashcard_review(db, user_id=self.user.id, flashcard_id=card.id, outcome="know", reviewed_at=now)
                xp_earned.append(result["xp_earned"])
            db.commit()
            self.assertEqual(xp_earned[-1], XP_FLASHCARD_REVIEW_SESSION)
            self.assertEqual(sum(xp_earned), XP_FLASHCARD_REVIEW_SESSION)
            repeat = record_flashcard_review(db, user_id=self.user.id, flashcard_id=self.cards[5].id, outcome="know", reviewed_at=now)
            db.commit()
            self.assertEqual(repeat["xp_earned"], 0)
            self.assertEqual(self._total_xp(), XP_FLASHCARD_REVIEW_SESSION)
        finally:
            db.close()

    def test_fewer_than_required_reviews_award_no_xp(self):
        db = self.Session()
        try:
            now = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
            for card in self.cards[:4]:
                result = record_flashcard_review(db, user_id=self.user.id, flashcard_id=card.id, outcome="know", reviewed_at=now)
                self.assertEqual(result["xp_earned"], 0)
            db.commit()
            self.assertEqual(self._total_xp(), 0)
        finally:
            db.close()

    def test_small_deck_can_qualify_when_every_card_reviewed(self):
        db = self.Session()
        try:
            small_deck = create_flashcard_deck(
                db,
                user_id=self.other_user.id,
                lesson_id=self.lesson.id,
                title="Small deck",
                skill="vocabulary",
                learning_language="kn",
                comfortable_language="en",
            )
            small_cards = create_flashcards(
                db,
                deck_id=small_deck.id,
                cards=[
                    {"front_text": "ಒಂದು", "back_text": "One"},
                    {"front_text": "ಎರಡು", "back_text": "Two"},
                    {"front_text": "ಮೂರು", "back_text": "Three"},
                ],
            )
            now = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
            xp_earned = [
                record_flashcard_review(db, user_id=self.other_user.id, flashcard_id=card.id, outcome="know", reviewed_at=now)["xp_earned"]
                for card in small_cards
            ]
            db.commit()
            self.assertEqual(sum(xp_earned), XP_FLASHCARD_REVIEW_SESSION)
        finally:
            db.close()

    def test_review_endpoint_does_not_accept_client_controlled_progress_values(self):
        response = self.client.post(
            f"/flashcards/{self.cards[0].id}/review",
            headers=self._auth_headers(),
            json={"outcome": "know", "mastery_level": 5, "correct_count": 100},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["progress"]["mastery_level"], 1)
        self.assertEqual(data["progress"]["correct_count"], 1)


if __name__ == "__main__":
    unittest.main()
