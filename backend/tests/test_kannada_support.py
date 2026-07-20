import json
import sys
import unittest
from collections import Counter
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
from assessment_question_utils import build_letter_tiles, grapheme_clusters, ordered_words_match_sentence, word_tiles_match_sentence
from database import Base
from language_utils import normalize_language
from main import app, get_db
from seed_assessment import seed_initial_assessment
from schemas import LearningPlanAIOutput


KANNADA_RANGE = (0x0C80, 0x0CFF)
OTHER_INDIC_RANGES = {
    "hi": (0x0900, 0x097F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
}


def has_kannada(text: str) -> bool:
    return any(KANNADA_RANGE[0] <= ord(character) <= KANNADA_RANGE[1] for character in text)


def has_other_indic(text: str) -> bool:
    return any(
        start <= ord(character) <= end
        for character in text
        for start, end in OTHER_INDIC_RANGES.values()
    )


@contextmanager
def patched_plan(order, targets):
    with (
        patch.object(flow, "ASSESSMENT_SKILL_ORDER", order),
        patch.object(flow, "ASSESSMENT_SKILL_TARGETS", targets),
        patch.object(flow, "MAX_TOTAL_QUESTIONS", sum(targets.values())),
    ):
        yield


class KannadaSupportTests(unittest.TestCase):
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

    def _register_and_token(self, email="kn@example.com"):
        payload = {
            "full_name": "Kannada Learner",
            "age": 20,
            "email": email,
            "password": "password123",
            "comfortable_language": "English",
            "learning_language": "Kannada",
            "experience_level": "Beginner",
            "education_level": "Primary",
            "role": "learner",
        }
        response = self.client.post("/register", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _answer_for_question(self, db, question_id: int):
        question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == question_id).first()
        payload = json.loads(question.correct_answer_json)
        if question.question_type in {"reading_mcq", "mcq"}:
            return {"selected_option_id": payload["correct_option_id"]}
        if question.question_type == "sentence_rearrange":
            return {"text": payload["reference_text"]}
        if "accepted_answers" in payload and payload["accepted_answers"]:
            return {"text": payload["accepted_answers"][0]}
        if "reference_text" in payload:
            return {"text": payload["reference_text"]}
        if "required_keywords" in payload:
            return {"text": " ".join(payload["required_keywords"])}
        return {"text": "ಉತ್ತರ"}

    def test_language_normalization_accepts_kannada(self):
        self.assertEqual(normalize_language("kn-IN"), "kn")
        self.assertEqual(normalize_language("Kannada"), "kn")
        self.assertEqual(normalize_language("ಕನ್ನಡ"), "kn")

    def test_profile_values_save_and_reload_as_kn(self):
        token = self._register_and_token("profile-kn@example.com")
        response = self.client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["learning_language"], "kn")

        update = self.client.patch(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"comfortable_language": "Kannada", "learning_language": "English"},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["comfortable_language"], "kn")
        self.assertEqual(update.json()["learning_language"], "en")

    def test_kannada_question_bank_has_required_coverage(self):
        db = self.Session()
        questions = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.language == "kn").all()
        counts = Counter((question.section, question.difficulty) for question in questions)
        types = Counter(question.question_type for question in questions)

        self.assertEqual(len(questions), 55)
        self.assertGreaterEqual(counts[("reading", "beginner")], 5)
        self.assertGreaterEqual(counts[("reading", "intermediate")], 5)
        self.assertGreaterEqual(counts[("reading", "advanced")], 3)
        self.assertGreaterEqual(counts[("typing", "beginner")], 13)
        self.assertGreaterEqual(counts[("typing", "intermediate")], 4)
        self.assertGreaterEqual(counts[("typing", "advanced")], 4)
        self.assertGreaterEqual(counts[("mcq", "beginner")], 8)
        self.assertGreaterEqual(counts[("mcq", "intermediate")], 8)
        self.assertGreaterEqual(counts[("mcq", "advanced")], 5)
        for question_type in {
            "reading_mcq",
            "mcq",
            "copy_typing",
            "sentence_rearrange",
            "sentence_completion",
            "short_response",
            "spoken_answer",
            "spoken_fill_blank",
            "reading_aloud",
            "sentence_repetition",
            "pronunciation",
        }:
            self.assertGreater(types[question_type], 0)
        db.close()

    def test_kannada_questions_have_valid_hidden_answers_and_no_language_leakage(self):
        db = self.Session()
        questions = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.language == "kn").all()
        self.assertTrue(questions)

        for question in questions:
            self.assertEqual(question.learning_language, "kn")
            self.assertTrue(flow._is_valid_assessment_question(question), question.stable_key)
            payload_text = " ".join(flow._question_language_payload_text(question))
            self.assertTrue(has_kannada(payload_text), question.stable_key)
            self.assertFalse(has_other_indic(payload_text), question.stable_key)

            correct = json.loads(question.correct_answer_json)
            options = json.loads(question.options_json) if question.options_json else []
            if question.question_type in {"reading_mcq", "mcq"}:
                ids = [option["id"] for option in options]
                texts = [option["text"] for option in options]
                self.assertEqual(ids.count(correct["correct_option_id"]), 1)
                self.assertEqual(len(texts), len(set(texts)))
            if question.question_type == "sentence_completion":
                answer = correct["accepted_answers"][0]
                self.assertEqual(sorted(tile["value"] for tile in build_letter_tiles(answer)), sorted(grapheme_clusters(answer)))
            if question.question_type == "sentence_rearrange":
                reference = correct["reference_text"]
                ordered = correct["ordered_words"]
                self.assertTrue(ordered_words_match_sentence(ordered, reference))
                self.assertTrue(word_tiles_match_sentence(ordered, reference))
        db.close()

    def test_initial_assessment_can_start_and_finish_in_kannada(self):
        token = self._register_and_token("finish-kn@example.com")
        with patched_plan(["reading", "writing"], {"reading": 1, "writing": 1}):
            started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(started.status_code, 200, started.text)
            attempt_id = started.json()["attempt_id"]
            current = started.json()["current_question"]
            self.assertEqual(current["learning_language"], "kn")

            for _ in range(2):
                db = self.Session()
                answer = self._answer_for_question(db, current["question_id"])
                db.close()
                response = self.client.post(
                    f"/assessment/attempts/{attempt_id}/answer",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"attempt_question_id": current["attempt_question_id"], "answer": answer},
                )
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                if data["assessment_complete"]:
                    break
                current = data["next_question"]

        self.assertTrue(data["assessment_complete"])
        self.assertEqual(data["result"]["completed"], True)

    def test_generated_learning_plan_schema_accepts_kannada(self):
        payload = {
            "status": "ready",
            "comfortable_language": "kn-IN",
            "learning_language": "English",
            "learner_summary": "ಕಲಿಯುವವರು ಕನ್ನಡದಲ್ಲಿ ಸೂಚನೆಗಳನ್ನು ಪಡೆಯುತ್ತಾರೆ.",
            "weakest_skills": ["grammar"],
            "strongest_skills": ["reading"],
            "generation_version": "test-v1",
            "courses": [
                {
                    "title": "English Reading",
                    "description": "Start with short words.",
                    "primary_skill": "reading",
                    "difficulty": 1,
                    "sequence_order": 1,
                    "is_unlocked": True,
                    "modules": [
                        {
                            "title": "Words",
                            "description": "Read familiar words.",
                            "sequence_order": 1,
                            "lesson_plans": [
                                {
                                    "title": "First Words",
                                    "learning_objective": "Read simple English words.",
                                    "skill": "reading",
                                    "difficulty": 1,
                                    "sequence_order": 1,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        plan = LearningPlanAIOutput.model_validate(payload)
        self.assertEqual(plan.comfortable_language, "kn")
        self.assertEqual(plan.learning_language, "en")
