import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import models
from database import Base
from main import app, get_db


def user_payload(**overrides):
    payload = {
        "full_name": "Learner One",
        "age": 20,
        "email": "learner@example.com",
        "password": "password123",
        "comfortable_language": "Hindi",
        "learning_language": "English",
        "experience_level": "Beginner",
        "education_level": "Primary",
        "role": "learner",
    }
    payload.update(overrides)
    return payload


class PersonalizationApiTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self._seed_content()

    def tearDown(self):
        app.dependency_overrides.clear()

    def _seed_content(self):
        db = self.Session()
        course = models.Course(
            title="Personalization Course",
            description="Content used to seed learner progress.",
            skill="reading",
            difficulty_level="beginner",
            language="en",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="Module One",
            description="Module used for personalization tests",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        self.lesson_ids = {}
        for index, (title, skill_type, difficulty) in enumerate(
            [
                ("Reading Start", "reading", "beginner"),
                ("Writing Start", "writing", "intermediate"),
                ("Comprehension Start", "comprehension", "intermediate"),
            ],
            start=1,
        ):
            lesson = models.Lesson(
                course_id=course.id,
                module_id=module.id,
                title=title,
                description=f"{title} description",
                content="Static lesson content",
                skill=skill_type,
                skill_type=skill_type,
                difficulty_level=difficulty,
                proficiency_level=difficulty,
                language="en",
                difficulty_order=index,
                estimated_minutes=10,
                estimated_duration_minutes=10,
                sequence_order=index,
            )
            db.add(lesson)
            db.flush()
            self.lesson_ids[skill_type] = lesson.id
        db.commit()
        db.close()

    def _register_and_token(self, *, age: int, experience_level: str, email: str) -> str:
        response = self.client.post(
            "/register",
            json=user_payload(age=age, experience_level=experience_level, email=email),
        )
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _attach_progress(self, email: str, entries: list[tuple[str, float, str, str]]):
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == email).first()
        self.assertIsNotNone(user)
        base_time = datetime.now(timezone.utc)
        for offset, (skill_type, score, status, current_difficulty) in enumerate(entries):
            db.add(
                models.LearnerProgress(
                    user_id=user.id,
                    course_id=1,
                    module_id=1,
                    lesson_id=self.lesson_ids[skill_type],
                    status=status,
                    completion_status=status,
                    progress_percentage=100 if status == "completed" else 45,
                    questions_attempted=10 + offset,
                    correct_answers=8 + offset,
                    incorrect_answers=2,
                    current_difficulty=current_difficulty,
                    score=score,
                    best_quiz_score=score,
                    time_spent_seconds=900 + (offset * 60),
                    time_spent=900 + (offset * 60),
                    started_at=base_time - timedelta(days=2 - offset),
                    completed_at=base_time - timedelta(days=1 - offset) if status == "completed" else None,
                    last_accessed_at=base_time + timedelta(minutes=offset),
                )
            )
        db.commit()
        db.close()

    def test_child_beginner_profile_uses_child_beginners_rules(self):
        token = self._register_and_token(age=8, experience_level="Beginner", email="child@example.com")

        response = self.client.get("/personalization/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["age_group"], "Child")
        self.assertEqual(data["sentence_length"], "short")
        self.assertEqual(data["translation_support"], "high")
        self.assertIn("animals", data["preferred_topics"])
        self.assertIn("school", data["preferred_topics"])
        self.assertEqual(data["previous_performance"]["total_lessons"], 0)
        self.assertEqual(data["current_skill"], "beginner")
        self.assertEqual(data["current_difficulty"], "beginner")

    def test_teen_beginner_profile_uses_teen_topics(self):
        token = self._register_and_token(age=15, experience_level="Beginner", email="teen@example.com")

        response = self.client.get("/personalization/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["age_group"], "Teenager")
        self.assertEqual(data["sentence_length"], "medium")
        self.assertIn("hobbies", data["preferred_topics"])
        self.assertIn("school life", data["preferred_topics"])
        self.assertIn("technology", data["preferred_topics"])
        self.assertEqual(data["content_tone"], "friendly and relatable")

    def test_adult_intermediate_profile_uses_practical_longer_content(self):
        token = self._register_and_token(age=31, experience_level="Intermediate", email="adult@example.com")

        response = self.client.get("/personalization/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["age_group"], "Adult")
        self.assertEqual(data["sentence_length"], "long")
        self.assertEqual(data["translation_support"], "medium")
        self.assertEqual(data["grammar_depth"], "moderate")
        self.assertIn("workplace", data["preferred_topics"])
        self.assertIn("finance", data["preferred_topics"])
        self.assertEqual(data["current_skill"], "intermediate")

    def test_missing_progress_uses_safe_defaults(self):
        token = self._register_and_token(age=26, experience_level="Advanced", email="noprog@example.com")

        response = self.client.get("/personalization/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["current_skill"], "advanced")
        self.assertEqual(data["current_difficulty"], "advanced")
        self.assertEqual(data["previous_performance"]["average_score"], 0)
        self.assertEqual(data["previous_performance"]["completed_lessons"], 0)
        self.assertEqual(data["skill_profiles"]["writing"]["current_skill"], "advanced")

    def test_different_skill_levels_generate_separate_skill_profiles(self):
        email = "mixed@example.com"
        token = self._register_and_token(age=29, experience_level="Beginner", email=email)
        self._attach_progress(
            email,
            [
                ("reading", 92, "completed", "advanced"),
                ("writing", 28, "in_progress", "beginner"),
                ("comprehension", 64, "completed", "intermediate"),
            ],
        )

        response = self.client.get("/personalization/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["current_skill"], "intermediate")
        self.assertEqual(data["current_difficulty"], "intermediate")
        self.assertEqual(data["skill_profiles"]["reading"]["current_skill"], "advanced")
        self.assertEqual(data["skill_profiles"]["writing"]["current_skill"], "beginner")
        self.assertEqual(data["skill_profiles"]["listening"]["current_skill"], "intermediate")
        self.assertEqual(data["skill_profiles"]["speaking"]["current_skill"], "beginner")
        self.assertEqual(data["skill_profiles"]["vocabulary"]["current_skill"], "advanced")
        self.assertEqual(data["skill_profiles"]["grammar"]["current_skill"], "intermediate")


if __name__ == "__main__":
    unittest.main()
