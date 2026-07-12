import unittest
from pathlib import Path
import sys

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models
import recommendation_service
from database import Base
from recommendation_service import generate_recommendations, learning_plan
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
        self.assertEqual(recommendations[0]["skill_type"], "writing")
        self.assertIn("lowest-scoring skill", recommendations[0]["recommendation_reason"])

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
