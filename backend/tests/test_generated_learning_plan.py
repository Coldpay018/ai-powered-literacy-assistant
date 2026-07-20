import sys
import unittest
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models
from database import Base
from generated_learning_plan_service import (
    create_learning_plan_from_ai_output,
    get_active_learning_plan,
    learning_plan_to_response,
)
from schema_updates import apply_sqlite_schema_updates
from schemas import LearningPlanAIOutput, LearningPlanResponse


def valid_plan_payload() -> dict:
    return {
        "status": "ready",
        "comfortable_language": "Hindi",
        "learning_language": "ta-IN",
        "learner_summary": "Learner recognizes familiar words and needs sentence practice.",
        "weakest_skills": ["grammar", "writing"],
        "strongest_skills": ["reading"],
        "generation_model": "test-model",
        "generation_version": "personalized-plan-v1",
        "courses": [
            {
                "title": "Tamil Sentence Foundations",
                "description": "Practice simple sentence patterns.",
                "primary_skill": "grammar",
                "difficulty": 2,
                "sequence_order": 1,
                "is_unlocked": True,
                "completion_status": "not_started",
                "modules": [
                    {
                        "title": "Everyday Sentences",
                        "description": "Build sentences used in daily routines.",
                        "sequence_order": 1,
                        "lesson_plans": [
                            {
                                "title": "Subject and Verb Order",
                                "learning_objective": "Arrange familiar words into complete Tamil sentences.",
                                "skill": "grammar",
                                "difficulty": 2,
                                "sequence_order": 1,
                                "content_status": "not_generated",
                            }
                        ],
                    }
                ],
            },
            {
                "title": "Tamil Reading Practice",
                "description": "Read short passages with support.",
                "primary_skill": "reading",
                "difficulty": 2,
                "sequence_order": 2,
                "is_unlocked": False,
                "completion_status": "not_started",
                "modules": [
                    {
                        "title": "Short Passages",
                        "description": "Practice supported reading.",
                        "sequence_order": 1,
                        "lesson_plans": [
                            {
                                "title": "Read a Short Passage",
                                "learning_objective": "Read and answer a short Tamil passage.",
                                "skill": "reading",
                                "difficulty": 2,
                                "sequence_order": 1,
                            }
                        ],
                    }
                ],
            },
        ],
    }


class GeneratedLearningPlanTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.user = models.User(
            full_name="Learner One",
            age=20,
            email="learner@example.com",
            hashed_password="hash",
            comfortable_language="hi",
            learning_language="ta",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_ai_schema_normalizes_languages_and_accepts_valid_plan(self):
        plan = LearningPlanAIOutput.model_validate(valid_plan_payload())

        self.assertEqual(plan.comfortable_language, "hi")
        self.assertEqual(plan.learning_language, "ta")
        self.assertEqual(plan.courses[0].sequence_order, 1)
        self.assertTrue(plan.courses[0].is_unlocked)

    def test_ai_schema_rejects_invalid_difficulty_and_sequence(self):
        payload = valid_plan_payload()
        payload["courses"][0]["difficulty"] = 6
        payload["courses"][0]["modules"][0]["lesson_plans"][0]["sequence_order"] = 0

        with self.assertRaises(ValidationError):
            LearningPlanAIOutput.model_validate(payload)

    def test_ai_schema_requires_first_course_to_be_only_unlocked_course(self):
        payload = valid_plan_payload()
        payload["courses"][0]["is_unlocked"] = False
        payload["courses"][1]["is_unlocked"] = True

        with self.assertRaises(ValidationError):
            LearningPlanAIOutput.model_validate(payload)

        payload = valid_plan_payload()
        payload["courses"][1]["is_unlocked"] = True

        with self.assertRaises(ValidationError):
            LearningPlanAIOutput.model_validate(payload)

    def test_service_creates_and_fetches_active_plan(self):
        plan_output = LearningPlanAIOutput.model_validate(valid_plan_payload())
        plan = create_learning_plan_from_ai_output(self.db, self.user.id, plan_output)
        self.db.commit()

        active_plan = get_active_learning_plan(self.db, self.user.id)
        response = LearningPlanResponse.model_validate(learning_plan_to_response(active_plan))

        self.assertEqual(active_plan.id, plan.id)
        self.assertEqual(response.weakest_skills, ["grammar", "writing"])
        self.assertEqual(response.courses[0].modules[0].lesson_plans[0].skill, "grammar")

    def test_duplicate_active_learning_plan_is_rejected(self):
        plan_output = LearningPlanAIOutput.model_validate(valid_plan_payload())
        create_learning_plan_from_ai_output(self.db, self.user.id, plan_output)
        self.db.commit()

        with self.assertRaises(ValueError):
            create_learning_plan_from_ai_output(self.db, self.user.id, plan_output)

    def test_database_rejects_duplicate_active_learning_plans(self):
        for version in ("v1", "v2"):
            self.db.add(
                models.LearningPlan(
                    user_id=self.user.id,
                    status="ready",
                    comfortable_language="hi",
                    learning_language="ta",
                    learner_summary="summary",
                    weakest_skills='["grammar"]',
                    strongest_skills='["reading"]',
                    generation_version=version,
                    is_active=True,
                )
            )

        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_schema_updates_create_generated_plan_tables(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)

        table_names = set(inspect(engine).get_table_names())
        self.assertIn("learning_plans", table_names)
        self.assertIn("generated_courses", table_names)
        self.assertIn("generated_modules", table_names)
        self.assertIn("generated_lesson_plans", table_names)
