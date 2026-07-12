import sys
import unittest
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


def user_payload(email="learner@example.com"):
    return {
        "full_name": "Learner One",
        "age": 20,
        "email": email,
        "password": "password123",
        "comfortable_language": "Hindi",
        "learning_language": "English",
        "experience_level": "Beginner",
        "education_level": "Primary",
        "role": "learner",
    }


class LessonPlayerApiTests(unittest.TestCase):
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
        self.seed_course()

    def tearDown(self):
        app.dependency_overrides.clear()

    def seed_course(self):
        db = self.Session()
        course = models.Course(
            title="Static Reading",
            description="Static seeded reading lessons.",
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
            description="First module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        self.lesson_ids = []
        for order, title in [(1, "First Lesson"), (2, "Second Lesson")]:
            lesson = models.Lesson(
                course_id=course.id,
                module_id=module.id,
                title=title,
                description=f"{title} description",
                content="Static lesson content",
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
                text_content="Read this short lesson.",
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
                correct_answer="this short lesson",
                explanation="The lesson says to read this short lesson.",
                sequence_order=1,
                points=1,
            )
            db.add(question)
            db.flush()
            db.add_all(
                [
                    models.QuestionOption(
                        question_id=question.id,
                        option_text="this short lesson",
                        is_correct=True,
                        sequence_order=1,
                    ),
                    models.QuestionOption(
                        question_id=question.id,
                        option_text="another lesson",
                        is_correct=False,
                        sequence_order=2,
                    ),
                ]
            )
        db.commit()
        db.close()

    def token(self, email="learner@example.com"):
        response = self.client.post("/register", json=user_payload(email=email))
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def test_lesson_player_loads_static_content_and_starts_progress(self):
        token = self.token()

        response = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertFalse(data["locked"])
        self.assertEqual(data["progress"]["status"], "in_progress")
        self.assertEqual(data["progress"]["completion_status"], "in_progress")
        self.assertEqual(data["progress"]["course_id"], data["course_id"])
        self.assertEqual(data["progress"]["module_id"], data["module_id"])
        self.assertEqual(data["content_blocks"][0]["title"], "Read")
        self.assertEqual(data["questions"][0]["options"][0]["option_text"], "this short lesson")
        self.assertNotIn("correct_answer", data["questions"][0])

    def test_lesson_progress_saves_resume_block(self):
        token = self.token()
        lesson = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        block_id = lesson["content_blocks"][0]["id"]

        response = self.client.patch(
            f"/lessons/{self.lesson_ids[0]}/progress",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "status": "in_progress",
                "progress_percentage": 50,
                "last_content_block_id": block_id,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["last_content_block_id"], block_id)
        self.assertEqual(response.json()["progress_percentage"], 50)
        self.assertGreaterEqual(response.json()["time_spent_seconds"], 0)

    def test_locked_lesson_requires_previous_completion(self):
        token = self.token()

        response = self.client.get(
            f"/lessons/{self.lesson_ids[1]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["locked"])
        self.assertEqual(data["content_blocks"], [])
        self.assertEqual(data["questions"], [])
        self.assertEqual(data["progress"]["completion_status"], "not_started")

    def test_quiz_submission_scores_and_completes_lesson(self):
        token = self.token()
        lesson = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        question_id = lesson["questions"][0]["id"]

        response = self.client.post(
            f"/lessons/{self.lesson_ids[0]}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"answers": {str(question_id): "this short lesson"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["score"], 100)
        self.assertTrue(data["passed"])
        self.assertEqual(data["progress"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
