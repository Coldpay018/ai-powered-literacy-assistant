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
        self.course_id = course.id
        module = models.CourseModule(
            course_id=course.id,
            title="Module One",
            description="First module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        self.lesson_ids = []
        self.question_ids = []
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
            self.question_ids.append(question.id)
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

        second_module = models.CourseModule(
            course_id=course.id,
            title="Module Two",
            description="Second module",
            sequence_order=2,
        )
        db.add(second_module)
        db.flush()
        lesson = models.Lesson(
            course_id=course.id,
            module_id=second_module.id,
            title="Third Lesson",
            description="Third lesson description",
            content="Static lesson content",
            skill="reading",
            skill_type="reading",
            difficulty_level="beginner",
            proficiency_level="beginner",
            language="en",
            difficulty_order=3,
            estimated_minutes=10,
            estimated_duration_minutes=10,
            sequence_order=1,
        )
        db.add(lesson)
        db.flush()
        self.module_two_lesson_id = lesson.id
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
        self.question_ids.append(question.id)
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
        self.assertTrue(data["is_unlocked"])
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

        self.assertEqual(response.status_code, 423, response.text)
        self.assertEqual(response.json()["detail"], "Lesson is locked")

    def test_second_lesson_unlocks_after_first_completion(self):
        token = self.token()
        first_lesson = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        first_question_id = first_lesson["questions"][0]["id"]

        complete_first = self.client.post(
            f"/lessons/{self.lesson_ids[0]}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"answers": {str(first_question_id): "this short lesson"}},
        )
        self.assertEqual(complete_first.status_code, 200, complete_first.text)

        response = self.client.get(
            f"/lessons/{self.lesson_ids[1]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["is_unlocked"])
        self.assertFalse(data["locked"])
        self.assertGreater(len(data["content_blocks"]), 0)

    def test_next_module_unlocks_after_previous_module_completion(self):
        token = self.token()
        first_question_id = self.question_ids[0]
        second_lesson = self.client.get(
            f"/lessons/{self.lesson_ids[1]}/player",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        second_question_id = self.question_ids[1]

        locked_before = self.client.get(
            f"/lessons/{self.module_two_lesson_id}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(locked_before.status_code, 423, locked_before.text)

        complete_first = self.client.post(
            f"/lessons/{self.lesson_ids[0]}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"answers": {str(first_question_id): "this short lesson"}},
        )
        self.assertEqual(complete_first.status_code, 200, complete_first.text)

        still_locked = self.client.get(
            f"/lessons/{self.module_two_lesson_id}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(still_locked.status_code, 423, still_locked.text)

        complete_second = self.client.post(
            f"/lessons/{self.lesson_ids[1]}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"answers": {str(second_question_id): "this short lesson"}},
        )
        self.assertEqual(complete_second.status_code, 200, complete_second.text)

        unlocked_next_module = self.client.get(
            f"/lessons/{self.module_two_lesson_id}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(unlocked_next_module.status_code, 200, unlocked_next_module.text)
        self.assertTrue(unlocked_next_module.json()["is_unlocked"])

    def test_locked_lesson_writes_are_blocked(self):
        token = self.token()

        response = self.client.patch(
            f"/lessons/{self.lesson_ids[1]}/progress",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "status": "in_progress",
                "progress_percentage": 10,
            },
        )

        self.assertEqual(response.status_code, 423, response.text)

    def test_locked_lesson_detail_is_blocked(self):
        token = self.token("locked-detail@example.com")

        response = self.client.get(
            f"/lessons/{self.lesson_ids[1]}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 423, response.text)

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

    def test_flattened_course_sequence_diagnostic(self):
        db = self.Session()
        course = db.query(models.Course).filter(models.Course.id == self.course_id).first()
        self.assertIsNotNone(course)
        flattened = []
        for module_order, module in enumerate(sorted(course.modules, key=lambda item: item.sequence_order), start=1):
            for lesson_order, lesson in enumerate(sorted(module.lessons, key=lambda item: item.sequence_order), start=1):
                print(f"{module_order}, {lesson_order}, {lesson.id}, {lesson.title}")
                flattened.append((module_order, lesson_order, lesson.id, lesson.title))
        self.assertEqual(flattened[0][1], 1)
        db.close()

    def test_dashboard_entry_uses_first_unlocked_lesson_for_new_user(self):
        token = self.token()
        course_response = self.client.get(f"/courses/{self.course_id}")
        self.assertEqual(course_response.status_code, 200, course_response.text)
        course = course_response.json()
        first_module = course["modules"][0]
        first_lesson_id = first_module["lessons"][0]["id"]

        self.assertEqual(
            [lesson["id"] for lesson in course["lessons"]],
            [self.lesson_ids[0], self.lesson_ids[1], self.module_two_lesson_id],
        )

        lesson_response = self.client.get(
            f"/lessons/{first_lesson_id}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(lesson_response.status_code, 200, lesson_response.text)
        self.assertTrue(lesson_response.json()["is_unlocked"])

        locked_lesson = self.client.get(
            f"/lessons/{self.lesson_ids[1]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(locked_lesson.status_code, 423, locked_lesson.text)

    def test_new_learner_has_exactly_first_lesson_unlocked(self):
        token = self.token("first-only@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "first-only@example.com").first()
        course = db.query(models.Course).filter(models.Course.id == self.course_id).first()
        from learning_content_service import is_lesson_unlocked, ordered_course_lessons, progress_status_map, repair_initial_unlock_state

        lessons = ordered_course_lessons(course)
        progress = progress_status_map(db, user.id, lessons)
        repair_initial_unlock_state(db, user.id, lessons, progress)
        unlocked_ids = [lesson.id for lesson in lessons if is_lesson_unlocked(lesson, lessons, progress)]
        self.assertEqual(unlocked_ids, [self.lesson_ids[0]])
        db.commit()
        db.close()

        first = self.client.get(
            f"/lessons/{self.lesson_ids[0]}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(first.status_code, 200, first.text)


if __name__ == "__main__":
    unittest.main()
