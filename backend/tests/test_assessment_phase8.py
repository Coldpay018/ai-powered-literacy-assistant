import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import assessment_flow_service as flow
import models
from database import Base
from main import app, get_db
from seed_assessment import ASSESSMENT_VERSION, seed_initial_assessment


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


@contextmanager
def patched_plan(order, targets):
    with (
        patch.object(flow, "ASSESSMENT_SKILL_ORDER", order),
        patch.object(flow, "ASSESSMENT_SKILL_TARGETS", targets),
        patch.object(flow, "MAX_TOTAL_QUESTIONS", sum(targets.values())),
    ):
        yield


class AssessmentPhase8FlowTests(unittest.TestCase):
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

    def _answer_for_question(self, db, question_id: int):
        question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == question_id).first()
        self.assertIsNotNone(question)
        if question.question_type in {"reading_mcq", "mcq"}:
            payload = json.loads(question.correct_answer_json)
            return {"selected_option_id": payload["correct_option_id"]}
        payload = json.loads(question.correct_answer_json)
        if "reference_text" in payload:
            return {"text": payload["reference_text"]}
        if "accepted_answers" in payload and payload["accepted_answers"]:
            return {"text": payload["accepted_answers"][0]}
        if "required_keywords" in payload and payload["required_keywords"]:
            return {"text": " ".join(payload["required_keywords"])}
        return {"text": "answer"}

    def test_start_returns_single_question(self):
        token = self._register_and_token()
        with patched_plan(["reading"], {"reading": 2}):
            response = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["current_question"])
        self.assertEqual(data["answered_questions"], 0)
        self.assertEqual(data["total_questions"], 2)
        self.assertFalse(data["assessment_complete"])

    def test_exact_and_fallback_question_matching(self):
        db = self.Session()
        assessment = models.Assessment(
            stable_key="phase8-manual",
            title="Manual Assessment",
            version="phase8-v1",
            is_active=True,
        )
        db.add(assessment)
        db.flush()
        user = models.User(
            full_name="Learner One",
            age=20,
            email="match@example.com",
            hashed_password="x",
            comfortable_language="hi",
            learning_language="en",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        db.add(user)
        db.flush()
        attempt = models.AssessmentAttempt(
            user_id=user.id,
            assessment_id=assessment.id,
            assessment_version=assessment.version,
            preferred_language="en",
            status="in_progress",
        )
        db.add(attempt)
        db.flush()

        exact = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="exact",
            assessment_version=assessment.version,
            section="mcq",
            language="en",
            difficulty="beginner",
            difficulty_rating=2,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            skill="reading",
            question_type="reading_mcq",
            prompt="Exact question",
            marks=2,
            skill_tag="literal comprehension",
            options_json='[{"id":"option_1","text":"answer"},{"id":"option_2","text":"distractor"},{"id":"option_3","text":"other"}]',
            correct_answer_json='{"correct_option_id": "option_1"}',
        )
        fallback = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="fallback",
            assessment_version=assessment.version,
            section="mcq",
            language="en",
            difficulty="advanced",
            difficulty_rating=4,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            skill="reading",
            question_type="reading_mcq",
            prompt="Fallback question",
            marks=2,
            skill_tag="passage comprehension",
            options_json='[{"id":"option_1","text":"answer"},{"id":"option_2","text":"distractor"},{"id":"option_3","text":"other"}]',
            correct_answer_json='{"correct_option_id": "option_1"}',
        )
        db.add_all([exact, fallback])
        db.flush()

        selected = flow._select_question_for_skill(db, user, attempt.id, "reading", 2)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, exact.id)

        db.delete(exact)
        db.commit()
        selected = flow._select_question_for_skill(db, user, attempt.id, "reading", 2)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, fallback.id)
        db.close()

    def test_one_question_at_a_time_flow_and_resume(self):
        token = self._register_and_token("flow@example.com")
        with patched_plan(["reading"], {"reading": 2}):
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(started.status_code, 200, started.text)
            first = started.json()["current_question"]

            db = self.Session()
            answer = self._answer_for_question(db, first["question_id"])
            db.close()

            submitted = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "attempt_question_id": first["attempt_question_id"],
                    "answer": answer,
                },
            )
            self.assertEqual(submitted.status_code, 200, submitted.text)
            submitted_data = submitted.json()
            self.assertFalse(submitted_data["assessment_complete"])
            self.assertIsNotNone(submitted_data["next_question"])
            self.assertNotEqual(
                submitted_data["next_question"]["attempt_question_id"],
                first["attempt_question_id"],
            )

            resumed = self.client.get("/assessment/current", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resumed.status_code, 200, resumed.text)
            self.assertEqual(
                resumed.json()["current_question"]["attempt_question_id"],
                submitted_data["next_question"]["attempt_question_id"],
            )

    def test_duplicate_submission_safety(self):
        token = self._register_and_token("dup@example.com")
        with patched_plan(["reading"], {"reading": 2}):
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            first = started.json()["current_question"]

            db = self.Session()
            answer = self._answer_for_question(db, first["question_id"])
            db.close()

            submitted = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "attempt_question_id": first["attempt_question_id"],
                    "answer": answer,
                },
            )
            self.assertEqual(submitted.status_code, 200, submitted.text)

            duplicate = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "attempt_question_id": first["attempt_question_id"],
                    "answer": answer,
                },
            )
            self.assertEqual(duplicate.status_code, 200, duplicate.text)
            duplicate_data = duplicate.json()
            self.assertTrue(duplicate_data["duplicate_submission"])
            self.assertEqual(duplicate_data["answered_questions"], submitted.json()["answered_questions"])

    def test_independent_skill_progression(self):
        token = self._register_and_token("skills@example.com")
        with patched_plan(["reading", "writing"], {"reading": 1, "writing": 1}):
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            first = started.json()["current_question"]
            db = self.Session()
            first_answer = self._answer_for_question(db, first["question_id"])
            db.close()

            first_response = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"attempt_question_id": first["attempt_question_id"], "answer": first_answer},
            )
            self.assertEqual(first_response.status_code, 200, first_response.text)
            next_question = first_response.json()["next_question"]
            self.assertEqual(next_question["skill"], "writing")

            db = self.Session()
            writing_state = (
                db.query(models.LearnerSkillDifficulty)
                .filter(
                    models.LearnerSkillDifficulty.user_id == db.query(models.User).filter(models.User.email == "skills@example.com").first().id,
                    models.LearnerSkillDifficulty.skill == "writing",
                )
                .first()
            )
            self.assertIsNone(writing_state)
            db.close()

    def test_completion_rules_and_final_profile(self):
        token = self._register_and_token("complete@example.com")
        with patched_plan(["reading"], {"reading": 1}):
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            question = started.json()["current_question"]
            db = self.Session()
            answer = self._answer_for_question(db, question["question_id"])
            db.close()

            submitted = self.client.post(
                f"/assessment/attempts/{started.json()['attempt_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"attempt_question_id": question["attempt_question_id"], "answer": answer},
            )
            self.assertEqual(submitted.status_code, 200, submitted.text)
            data = submitted.json()
            self.assertTrue(data["assessment_complete"])
            self.assertIsNotNone(data["result"])
            self.assertIn("reading", data["final_skill_profile"])
            self.assertIn("reading", data["result"]["final_skill_profile"])

    def test_unauthorized_access_is_blocked(self):
        response = self.client.post("/assessment/start")
        self.assertEqual(response.status_code, 401)

    def test_empty_or_insufficient_question_bank_is_rejected(self):
        token = self._register_and_token("empty@example.com")
        with patched_plan(["listening"], {"listening": 1}):
            response = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("No suitable assessment questions available", response.text)


if __name__ == "__main__":
    unittest.main()
