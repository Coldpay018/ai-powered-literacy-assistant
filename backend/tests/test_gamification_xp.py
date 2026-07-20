import importlib
import json
import sys
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import assessment_flow_service as flow
import gamification_service
import models
from database import Base
from gamification_service import (
    APPLICATION_TIMEZONE_NAME,
    XP_FIRST_LESSON_COMPLETION,
    XP_INITIAL_ASSESSMENT_COMPLETION,
    XP_PERFECT_LESSON_QUIZ_BONUS,
    award_xp,
    evaluate_user_badges,
    get_user_badges,
    record_qualified_activity,
)
from main import app, get_db
from seed_assessment import seed_initial_assessment


def user_payload(email="learner@example.com"):
    return {
        "full_name": "Learner One",
        "age": 20,
        "email": email,
        "password": "password123",
        "comfortable_language": "Kannada",
        "learning_language": "English",
        "experience_level": "Beginner",
        "education_level": "Primary",
        "role": "learner",
    }


@contextmanager
def patched_single_question_assessment():
    with (
        patch.object(flow, "ASSESSMENT_SKILL_ORDER", ["reading"]),
        patch.object(flow, "ASSESSMENT_SKILL_TARGETS", {"reading": 1}),
        patch.object(flow, "MAX_TOTAL_QUESTIONS", 1),
    ):
        yield


class GamificationXPTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

        db = self.Session()
        seed_initial_assessment(db)
        self._seed_course(db)
        db.close()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _seed_course(self, db):
        course = models.Course(
            title="XP Reading",
            description="XP reading lessons.",
            skill="reading",
            difficulty_level="beginner",
            language="en",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="XP Module",
            description="XP module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        self.lesson_ids = []
        self.question_ids = []
        for order in [1, 2]:
            lesson = models.Lesson(
                course_id=course.id,
                module_id=module.id,
                title=f"XP Lesson {order}",
                description=f"XP Lesson {order} description",
                content="Read this lesson.",
                skill="reading",
                skill_type="reading",
                difficulty_level="beginner",
                proficiency_level="beginner",
                language="en",
                difficulty_order=order,
                estimated_minutes=10,
                estimated_duration_minutes=10,
                sequence_order=order,
            )
            db.add(lesson)
            db.flush()
            self.lesson_ids.append(lesson.id)
            block = models.LessonContent(
                lesson_id=lesson.id,
                content_type="text",
                title="Read",
                text_content="Read this lesson.",
                sequence_order=1,
            )
            quiz = models.LessonContent(
                lesson_id=lesson.id,
                content_type="quiz",
                title="Quiz",
                metadata_json='{"passing_score": 60}',
                sequence_order=2,
            )
            db.add_all([block, quiz])
            db.flush()
            question = models.LessonQuestion(
                lesson_id=lesson.id,
                content_block_id=quiz.id,
                question_text="What should you read?",
                question_type="mcq",
                skill="reading",
                difficulty_level="beginner",
                correct_answer="this lesson",
                explanation="Read this lesson.",
                sequence_order=1,
                points=1,
            )
            db.add(question)
            db.flush()
            self.question_ids.append(question.id)
            db.add_all(
                [
                    models.QuestionOption(
                        question_id=question.id,
                        option_text="this lesson",
                        is_correct=True,
                        sequence_order=1,
                    ),
                    models.QuestionOption(
                        question_id=question.id,
                        option_text="wrong answer",
                        is_correct=False,
                        sequence_order=2,
                    ),
                ]
            )
        db.commit()

    def _token(self, email="learner@example.com"):
        response = self.client.post("/register", json=user_payload(email=email))
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _xp(self, token):
        response = self.client.get("/gamification/xp", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _badges(self, token):
        response = self.client.get("/gamification/badges", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _submit_quiz(self, token, lesson_id, question_id, answer="this lesson", time_spent_seconds=0):
        return self.client.post(
            f"/lessons/{lesson_id}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"answers": {str(question_id): answer}, "time_spent_seconds": time_spent_seconds},
        )

    def _assessment_answer_for_question(self, question_id):
        db = self.Session()
        question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == question_id).first()
        self.assertIsNotNone(question)
        payload = json.loads(question.correct_answer_json)
        db.close()
        if question.question_type in {"reading_mcq", "mcq"}:
            return {"selected_option_id": payload["correct_option_id"]}
        if "reference_text" in payload:
            return {"text": payload["reference_text"]}
        if payload.get("accepted_answers"):
            return {"text": payload["accepted_answers"][0]}
        return {"text": "answer"}

    def test_xp_endpoint_requires_authentication(self):
        response = self.client.get("/gamification/xp")
        self.assertIn(response.status_code, {401, 403})

    def test_badges_endpoint_requires_authentication(self):
        response = self.client.get("/gamification/badges")
        self.assertIn(response.status_code, {401, 403})

    def test_opening_lesson_awards_no_xp_and_dashboard_handles_zero(self):
        token = self._token("zero@example.com")
        response = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        summary = self._xp(token)
        self.assertEqual(summary["total_xp"], 0)
        self.assertEqual(summary["xp_earned_this_week"], 0)
        self.assertEqual(summary["recent_transactions"], [])
        self.assertEqual(summary["current_streak"], 0)
        self.assertEqual(summary["longest_streak"], 0)
        self.assertFalse(summary["completed_today"])
        self.assertEqual(summary["streak_timezone"], APPLICATION_TIMEZONE_NAME)
        badges = self._badges(token)
        self.assertEqual(badges["earned_count"], 0)
        self.assertEqual(badges["total_count"], 7)
        self.assertEqual(len(badges["locked_badges"]), 7)

    def test_first_lesson_completion_and_perfect_quiz_award_once(self):
        token = self._token("perfect@example.com")
        response = self._submit_quiz(token, self.lesson_ids[0], self.question_ids[0])
        self.assertEqual(response.status_code, 200, response.text)
        summary = self._xp(token)
        self.assertEqual(summary["total_xp"], XP_FIRST_LESSON_COMPLETION + XP_PERFECT_LESSON_QUIZ_BONUS)
        self.assertEqual(summary["current_streak"], 1)
        self.assertEqual(summary["longest_streak"], 1)
        self.assertTrue(summary["completed_today"])

        duplicate = self._submit_quiz(token, self.lesson_ids[0], self.question_ids[0])
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        duplicate_summary = self._xp(token)
        self.assertEqual(duplicate_summary["total_xp"], XP_FIRST_LESSON_COMPLETION + XP_PERFECT_LESSON_QUIZ_BONUS)
        self.assertEqual(duplicate_summary["current_streak"], 1)
        earned_keys = {badge["badge_key"] for badge in self._badges(token)["earned_badges"]}
        self.assertIn("first_lesson", earned_keys)
        self.assertIn("perfect_quiz", earned_keys)

    def test_repeated_progress_completion_awards_no_extra_xp(self):
        token = self._token("progress-complete@example.com")
        first = self.client.patch(
            f"/lessons/{self.lesson_ids[0]}/progress",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "completed", "progress_percentage": 100},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.patch(
            f"/lessons/{self.lesson_ids[0]}/progress",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "completed", "progress_percentage": 100},
        )
        self.assertEqual(second.status_code, 200, second.text)
        summary = self._xp(token)
        self.assertEqual(summary["total_xp"], XP_FIRST_LESSON_COMPLETION)
        self.assertEqual(summary["current_streak"], 1)
        badges = self._badges(token)
        self.assertEqual(
            [badge["badge_key"] for badge in badges["earned_badges"]].count("first_lesson"),
            1,
        )

    def test_incorrect_answers_do_not_reduce_xp_or_award_bonus(self):
        token = self._token("incorrect@example.com")
        response = self._submit_quiz(token, self.lesson_ids[0], self.question_ids[0], answer="wrong answer")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["score"], 0)
        self.assertEqual(self._xp(token)["total_xp"], XP_FIRST_LESSON_COMPLETION)

    def test_assessment_completion_awards_once(self):
        token = self._token("assessment-xp@example.com")
        with patched_single_question_assessment():
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(started.status_code, 200, started.text)
            question = started.json()["current_question"]
            submitted = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "attempt_question_id": question["attempt_question_id"],
                    "answer": self._assessment_answer_for_question(question["question_id"]),
                },
            )
            self.assertEqual(submitted.status_code, 200, submitted.text)
            self.assertTrue(submitted.json()["assessment_complete"])
            repeated = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/submit",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(repeated.status_code, 200, repeated.text)

        self.assertEqual(self._xp(token)["total_xp"], XP_INITIAL_ASSESSMENT_COMPLETION)
        self.assertEqual(self._xp(token)["current_streak"], 1)
        earned_keys = {badge["badge_key"] for badge in self._badges(token)["earned_badges"]}
        self.assertIn("initial_assessment", earned_keys)

    def test_total_xp_matches_transaction_sum_and_users_are_separate(self):
        first_token = self._token("sum-one@example.com")
        second_token = self._token("sum-two@example.com")
        self.assertEqual(self._submit_quiz(first_token, self.lesson_ids[0], self.question_ids[0]).status_code, 200)

        first_summary = self._xp(first_token)
        second_summary = self._xp(second_token)
        self.assertEqual(second_summary["total_xp"], 0)

        db = self.Session()
        first_user = db.query(models.User).filter(models.User.email == "sum-one@example.com").first()
        transaction_sum = (
            db.query(func.coalesce(func.sum(models.XPTransaction.amount), 0))
            .filter(models.XPTransaction.user_id == first_user.id)
            .scalar()
        )
        db.close()
        self.assertEqual(first_summary["total_xp"], transaction_sum)

    def test_xp_badges_are_awarded_from_backend_xp_totals(self):
        token = self._token("xp-badges@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "xp-badges@example.com").first()
        award_xp(
            db,
            user_id=user.id,
            amount=500,
            source_type="system",
            source_id=user.id,
            reward_key="test_backend_xp_award",
            description_key="gamification.description.lessonCompleted",
        )
        evaluate_user_badges(db, user.id)
        db.commit()
        db.close()

        earned_keys = {badge["badge_key"] for badge in self._badges(token)["earned_badges"]}
        self.assertIn("xp_100", earned_keys)
        self.assertIn("xp_500", earned_keys)

    def test_streak_badges_are_awarded_after_streak_updates(self):
        token = self._token("streak-badges@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "streak-badges@example.com").first()
        for offset in range(7):
            record_qualified_activity(
                db,
                user_id=user.id,
                source_type="lesson",
                source_id=offset + 1,
                occurred_at=datetime(2026, 7, 19 + offset, 4, 0, tzinfo=timezone.utc),
            )
        db.commit()
        db.close()

        earned_keys = {badge["badge_key"] for badge in self._badges(token)["earned_badges"]}
        self.assertIn("streak_3", earned_keys)
        self.assertIn("streak_7", earned_keys)

    def test_badges_can_use_existing_stored_progress_without_duplicate_awards(self):
        token = self._token("existing-progress-badge@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "existing-progress-badge@example.com").first()
        progress = models.LearnerProgress(
            user_id=user.id,
            course_id=1,
            module_id=1,
            lesson_id=self.lesson_ids[0],
            status="completed",
            completion_status="completed",
            progress_percentage=100,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(progress)
        first_awards = evaluate_user_badges(db, user.id)
        second_awards = evaluate_user_badges(db, user.id)
        db.commit()
        summary = get_user_badges(db, user.id)
        db.close()

        self.assertIn("first_lesson", {badge["badge_key"] for badge in summary["earned_badges"]})
        self.assertEqual(len([award for award in first_awards if award.badge.badge_key == "first_lesson"]), 1)
        self.assertEqual(second_awards, [])

    def test_badges_are_separate_by_user(self):
        first_token = self._token("badge-one@example.com")
        second_token = self._token("badge-two@example.com")
        response = self._submit_quiz(first_token, self.lesson_ids[0], self.question_ids[0])
        self.assertEqual(response.status_code, 200, response.text)

        first_earned = {badge["badge_key"] for badge in self._badges(first_token)["earned_badges"]}
        second_earned = {badge["badge_key"] for badge in self._badges(second_token)["earned_badges"]}
        self.assertIn("first_lesson", first_earned)
        self.assertNotIn("first_lesson", second_earned)

    def test_next_day_activity_increases_and_missed_day_resets_streak(self):
        token = self._token("streak-reset@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "streak-reset@example.com").first()

        record_qualified_activity(
            db,
            user_id=user.id,
            source_type="lesson",
            source_id=1,
            occurred_at=datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc),
        )
        record_qualified_activity(
            db,
            user_id=user.id,
            source_type="lesson",
            source_id=2,
            occurred_at=datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc),
        )
        db.flush()
        summary = db.query(models.StreakSummary).filter(models.StreakSummary.user_id == user.id).first()
        self.assertEqual(summary.current_streak, 2)
        self.assertEqual(summary.longest_streak, 2)

        record_qualified_activity(
            db,
            user_id=user.id,
            source_type="assessment",
            source_id=user.id,
            occurred_at=datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc),
        )
        db.flush()
        self.assertEqual(summary.current_streak, 1)
        self.assertEqual(summary.longest_streak, 2)
        db.close()

    def test_same_local_day_and_timezone_boundary_do_not_increment_twice(self):
        self._token("streak-boundary@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "streak-boundary@example.com").first()

        record_qualified_activity(
            db,
            user_id=user.id,
            source_type="lesson",
            source_id=1,
            occurred_at=datetime(2026, 7, 18, 20, 0, tzinfo=timezone.utc),
        )
        record_qualified_activity(
            db,
            user_id=user.id,
            source_type="lesson",
            source_id=2,
            occurred_at=datetime(2026, 7, 19, 1, 0, tzinfo=timezone.utc),
        )
        db.flush()
        summary = db.query(models.StreakSummary).filter(models.StreakSummary.user_id == user.id).first()
        activity_count = (
            db.query(models.DailyStreakActivity)
            .filter(models.DailyStreakActivity.user_id == user.id)
            .count()
        )
        self.assertEqual(summary.current_streak, 1)
        self.assertEqual(activity_count, 1)
        db.close()


class GamificationTimezoneTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(gamification_service)

    def test_normal_application_timezone_uses_zoneinfo(self):
        resolved_timezone = gamification_service.get_application_timezone()

        self.assertIsInstance(resolved_timezone, ZoneInfo)
        self.assertEqual(getattr(resolved_timezone, "key", None), APPLICATION_TIMEZONE_NAME)

    def test_missing_zoneinfo_uses_fixed_india_offset_and_logs_once(self):
        gamification_service._timezone_fallback_warning_logged = False
        with patch.object(gamification_service, "ZoneInfo", side_effect=ZoneInfoNotFoundError):
            with self.assertLogs("gamification_service", level="WARNING") as logs:
                resolved_timezone = gamification_service.get_application_timezone()
            second_resolved_timezone = gamification_service.get_application_timezone()

        self.assertEqual(
            resolved_timezone.utcoffset(datetime(2026, 7, 20, tzinfo=timezone.utc)),
            timedelta(hours=5, minutes=30),
        )
        self.assertEqual(
            second_resolved_timezone.utcoffset(datetime(2026, 7, 20, tzinfo=timezone.utc)),
            timedelta(hours=5, minutes=30),
        )
        self.assertEqual(len(logs.output), 1)
        self.assertIn("fixed UTC+05:30 fallback", logs.output[0])

    def test_fallback_local_date_calculation_uses_india_offset(self):
        with patch.object(
            gamification_service,
            "APPLICATION_TIMEZONE",
            timezone(timedelta(hours=5, minutes=30)),
        ):
            activity_date = gamification_service.activity_date_for(
                datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc)
            )

        self.assertEqual(activity_date.isoformat(), "2026-07-20")

    def test_importing_gamification_service_does_not_fail_without_zoneinfo_database(self):
        with patch("zoneinfo.ZoneInfo", side_effect=ZoneInfoNotFoundError):
            with self.assertLogs("gamification_service", level="WARNING") as logs:
                reloaded_module = importlib.reload(gamification_service)

        self.assertEqual(
            reloaded_module.APPLICATION_TIMEZONE.utcoffset(datetime(2026, 7, 20, tzinfo=timezone.utc)),
            timedelta(hours=5, minutes=30),
        )
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()
