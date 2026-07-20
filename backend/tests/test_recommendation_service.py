import unittest
from pathlib import Path
import sys
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models
import recommendation_service
from database import Base
from recommendation_service import current_recommendations, generate_recommendations, learning_plan
from schemas import LessonProgressUpdate
from seed_learning_content import seed_learning_content


def fake_embeddings(texts):
    vectors = []
    for text in texts:
        lowered = text.lower()
        vectors.append([
            1.0 if "reading" in lowered else 0.0,
            1.0 if "writing" in lowered or "grammar" in lowered or "sentence" in lowered else 0.0,
            1.0 if "comprehension" in lowered or "questions" in lowered else 0.0,
            1.0 if "intermediate" in lowered else 0.0,
        ])
    return vectors


class RecommendationServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        recommendation_service.set_embedding_function_for_tests(fake_embeddings)
        seed_learning_content(self.db)
        self.user = models.User(
            full_name="Learner One",
            age=20,
            email="learner@example.com",
            hashed_password="hash",
            comfortable_language="hi",
            learning_language="en",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
        )
        self.db.add(self.user)
        self.db.flush()
        self.result = models.AssessmentResult(
            attempt_id=1,
            user_id=self.user.id,
            assessment_version="test",
            reading_score=72,
            typing_score=25,
            mcq_score=60,
            overall_score=48,
            proficiency_level="intermediate",
        )
        self.db.add(self.result)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        recommendation_service.set_embedding_function_for_tests(None)

    def test_recommendation_generation_prioritizes_weakest_skill(self):
        recommendations = generate_recommendations(self.db, self.user)

        self.assertGreaterEqual(len(recommendations), 4)
        self.assertTrue(any(item["skill_type"] == "writing" for item in recommendations))
        self.assertTrue(any("lowest-scoring skill" in item["recommendation_reason"] for item in recommendations))

    def test_completed_lessons_are_excluded(self):
        lesson = self.db.query(models.Lesson).filter(models.Lesson.skill_type == "writing").first()
        self.db.add(
            models.LearnerProgress(
                user_id=self.user.id,
                lesson_id=lesson.id,
                status="completed",
                progress_percentage=100,
            )
        )
        self.db.commit()

        recommendations = generate_recommendations(self.db, self.user)

        self.assertNotIn(lesson.id, [item["lesson_id"] for item in recommendations])

    def test_proficiency_and_language_filtering(self):
        recommendations = generate_recommendations(self.db, self.user)

        self.assertTrue(all(item["proficiency_level"] == "intermediate" for item in recommendations))
        self.assertTrue(all(item["language"] == "en" for item in recommendations))

    def test_missing_assessment_result_returns_clear_error(self):
        other_user = models.User(
            full_name="No Result",
            age=22,
            email="noresult@example.com",
            hashed_password="hash",
            comfortable_language="hi",
            learning_language="en",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
        )
        self.db.add(other_user)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            generate_recommendations(self.db, other_user)

        self.assertEqual(raised.exception.status_code, 409)

    def test_duplicate_active_recommendations_are_prevented(self):
        first = generate_recommendations(self.db, self.user)
        second = generate_recommendations(self.db, self.user)
        active_count = (
            self.db.query(models.LessonRecommendation)
            .filter(
                models.LessonRecommendation.user_id == self.user.id,
                models.LessonRecommendation.is_active == True,
            )
            .count()
        )

        self.assertEqual(active_count, len(second))
        self.assertEqual(len(first), len(second))

    def test_current_recommendations_include_unlock_and_sequence_metadata(self):
        recommendations = generate_recommendations(self.db, self.user)

        self.assertTrue(recommendations)
        first = recommendations[0]
        self.assertIn("module_id", first)
        self.assertIn("module_order", first)
        self.assertIn("sequence_order", first)
        self.assertIn("is_unlocked", first)
        self.assertIn("completion_status", first)
        self.assertEqual(first["completion_status"], first["current_progress_status"])
        self.assertTrue(any(item["is_unlocked"] for item in recommendations))

    def test_recommendations_include_actual_first_unlocked_lesson_for_new_user(self):
        recommendations = generate_recommendations(self.db, self.user)
        course = (
            self.db.query(models.Course)
            .filter(
                models.Course.language == self.user.learning_language,
                models.Course.proficiency_level == self.result.proficiency_level,
            )
            .first()
        )
        first_lesson = min(course.lessons, key=lambda lesson: (lesson.sequence_order, lesson.id))

        self.assertEqual(recommendations[0]["lesson_id"], first_lesson.id)
        self.assertTrue(recommendations[0]["is_unlocked"])
        self.assertEqual(recommendations[0]["completion_status"], "not_started")

    def test_broken_user_progress_is_repaired_without_unlocking_everything(self):
        course = (
            self.db.query(models.Course)
            .filter(
                models.Course.language == self.user.learning_language,
                models.Course.proficiency_level == self.result.proficiency_level,
            )
            .first()
        )
        ordered_lessons = sorted(course.lessons, key=lambda lesson: (lesson.sequence_order, lesson.id))
        self.db.add(
            models.LearnerProgress(
                user_id=self.user.id,
                course_id=ordered_lessons[1].course_id,
                module_id=ordered_lessons[1].module_id,
                lesson_id=ordered_lessons[1].id,
                status="in_progress",
                completion_status="in_progress",
                progress_percentage=45,
            )
        )
        self.db.commit()

        recommendations = generate_recommendations(self.db, self.user)
        progress_rows = (
            self.db.query(models.LearnerProgress)
            .filter(models.LearnerProgress.user_id == self.user.id)
            .all()
        )
        unlocked_ids = [item["lesson_id"] for item in recommendations if item["is_unlocked"]]

        self.assertIn(ordered_lessons[0].id, unlocked_ids)
        self.assertNotIn(ordered_lessons[1].id, unlocked_ids)
        repaired_later = (
            self.db.query(models.LearnerProgress)
            .filter(
                models.LearnerProgress.user_id == self.user.id,
                models.LearnerProgress.lesson_id == ordered_lessons[1].id,
            )
            .first()
        )
        self.assertEqual(repaired_later.status, "not_started")
        self.assertEqual(repaired_later.progress_percentage, 0)
        self.assertEqual(
            self.db.query(models.LearnerProgress)
            .filter(
                models.LearnerProgress.user_id == self.user.id,
                models.LearnerProgress.lesson_id == ordered_lessons[0].id,
            )
            .count(),
            1,
        )
        self.assertLess(len([row for row in progress_rows if row.status in {"in_progress", "completed"}]), len(ordered_lessons))

    def test_current_recommendations_deduplicate_duplicate_lesson_rows(self):
        lesson = self.db.query(models.Lesson).filter(models.Lesson.skill_type == "writing").first()
        first_generated_at = datetime.now(timezone.utc)
        recommendation = models.LessonRecommendation(
            user_id=self.user.id,
            lesson_id=lesson.id,
            recommendation_score=0.99,
            recommendation_reason="Duplicate test row",
            generated_at=first_generated_at,
            is_active=True,
        )
        duplicate = models.LessonRecommendation(
            user_id=self.user.id,
            lesson_id=lesson.id,
            recommendation_score=0.88,
            recommendation_reason="Duplicate test row 2",
            generated_at=first_generated_at.replace(microsecond=min(first_generated_at.microsecond + 1, 999999)),
            is_active=True,
        )
        self.db.add(recommendation)
        self.db.add(duplicate)
        self.db.commit()

        rows = current_recommendations(self.db, self.user)
        lesson_ids = [item["lesson_id"] for item in rows]

        self.assertEqual(len(lesson_ids), len(set(lesson_ids)))
        self.assertEqual(lesson_ids.count(lesson.id), 1)

    def test_learning_plan_contains_completion_summary(self):
        plan = learning_plan(self.db, self.user)

        self.assertEqual(plan["weakest_skill"], "writing")
        self.assertEqual(plan["completion_summary"]["total_recommended_lessons"], len(plan["recommended_lessons"]))
        self.assertIsNotNone(plan["suggested_next_lesson"])

    def test_progress_update_validation_rejects_invalid_percentage(self):
        with self.assertRaises(ValidationError):
            LessonProgressUpdate(status="in_progress", progress_percentage=120)


if __name__ == "__main__":
    unittest.main()
