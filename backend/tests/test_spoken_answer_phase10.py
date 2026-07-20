import json
import json
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import assessment_flow_service as flow
import models
from database import Base
from main import app, get_db
from seed_assessment import seed_initial_assessment


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


class SpokenAnswerPhase10Tests(unittest.TestCase):
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

    def _register_and_token(self, email="learner@example.com"):
        response = self.client.post("/register", json=user_payload(email=email))
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _create_voice_attempt(self, question_type: str, email: str = "voice@example.com", language: str = "en"):
        token = self._register_and_token(email)
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == email).first()
        assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()
        question = (
            db.query(models.AssessmentQuestion)
            .filter(
                models.AssessmentQuestion.assessment_version == assessment.version,
                models.AssessmentQuestion.question_type == question_type,
                models.AssessmentQuestion.language == language,
                models.AssessmentQuestion.is_active == True,
            )
            .first()
        )
        self.assertIsNotNone(question)
        attempt = models.AssessmentAttempt(
            user_id=user.id,
            assessment_id=assessment.id,
            assessment_version=assessment.version,
            preferred_language="en",
            status="in_progress",
        )
        db.add(attempt)
        db.flush()
        flow._create_attempt_question(db, attempt, question, translation_language="hi" if language == "en" else "en")
        db.commit()
        attempt_question = (
            db.query(models.AssessmentAttemptQuestion)
            .filter(models.AssessmentAttemptQuestion.attempt_id == attempt.id)
            .first()
        )
        db.close()
        return token, attempt.id, attempt_question.id, question

    def test_spoken_fill_blank_accepts_school_and_rejects_unrelated_words(self):
        token, attempt_id, attempt_question_id, question = self._create_voice_attempt(
            "spoken_fill_blank",
            "fill-blank@example.com",
            language="hi",
        )

        accepted = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": attempt_question_id,
                "spoken_text": "स्कूल",
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertTrue(accepted.json()["correct"])
        self.assertNotIn("स्कूल", json.dumps(accepted.json()))

        token, attempt_id, attempt_question_id, question = self._create_voice_attempt(
            "spoken_fill_blank",
            "fill-blank-wrong@example.com",
            language="hi",
        )
        rejected = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": attempt_question_id,
                "spoken_text": "बाजार",
            },
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertFalse(rejected.json()["correct"])

    def test_spoken_answer_endpoint_grades_recognized_text(self):
        token, attempt_id, attempt_question_id, question = self._create_voice_attempt("spoken_answer", "spoken-answer@example.com")

        response = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": attempt_question_id,
                "spoken_text": "school",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["correct"])
        self.assertEqual(data["feedback"], "Correct")
        self.assertEqual(data["model_used"], "browser-speech-recognition")
        self.assertEqual(data["attempt_status"], "in_progress")
        self.assertNotIn("school", json.dumps(data))

    def test_spoken_answer_endpoint_normalizes_case_and_punctuation(self):
        token, attempt_id, attempt_question_id, question = self._create_voice_attempt("sentence_repetition", "normalize@example.com")

        response = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": attempt_question_id,
                "spoken_text": "  The child keeps the pencil on the table.  ",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["correct"])
        self.assertIn(data["feedback"], {"Correct", "Close match"})

    def test_spoken_answer_endpoint_rejects_blank_text(self):
        token, attempt_id, attempt_question_id, question = self._create_voice_attempt("pronunciation", "blank@example.com")

        response = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": attempt_question_id,
                "spoken_text": "   ",
            },
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("required", response.text.lower())

    def test_spoken_answer_duplicate_submission_is_safe(self):
        token, attempt_id, attempt_question_id, question = self._create_voice_attempt("spoken_answer", "duplicate@example.com")

        payload = {
            "attempt_question_id": attempt_question_id,
            "spoken_text": "school",
        }
        first = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        self.assertEqual(first.status_code, 200, first.text)

        second = self.client.post(
            f"/assessment/attempts/{attempt_id}/spoken-answer",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(second.json()["duplicate_submission"])


if __name__ == "__main__":
    unittest.main()
