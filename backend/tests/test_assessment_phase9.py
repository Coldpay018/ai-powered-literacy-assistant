import json
import sys
import unittest
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
from assessment_question_utils import build_word_tiles, sentence_word_tokens, word_tiles_match_sentence
from database import Base
from language_utils import normalize_language
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


class AssessmentPhase9TtsAndTilesTests(unittest.TestCase):
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

    def _register_custom_and_token(self, payload: dict):
        response = self.client.post("/register", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": payload["email"], "password": payload["password"]})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _answer_for_question(self, db, question_id: int):
        question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == question_id).first()
        self.assertIsNotNone(question)
        if question.question_type in {"reading_mcq", "mcq"}:
            payload = json.loads(question.correct_answer_json)
            return {"selected_option_id": payload["correct_option_id"]}
        payload = json.loads(question.correct_answer_json)
        if question.question_type == "sentence_rearrange":
            return {"text": payload["reference_text"]}
        if "accepted_answers" in payload and payload["accepted_answers"]:
            return {"text": payload["accepted_answers"][0]}
        if "reference_text" in payload:
            return {"text": payload["reference_text"]}
        return {"text": "answer"}

    def _create_sentence_rearrange_attempt(self, email: str, reference_text: str, translation_language: str = "hi"):
        token = self._register_and_token(email)
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == email).first()
        assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()
        question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key=f"{email}-rearrange",
            assessment_version=assessment.version,
            section="typing",
            language="en",
            difficulty="beginner",
            difficulty_rating=2,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            skill="writing",
            question_type="sentence_rearrange",
            prompt="Arrange the words to make a sentence.",
            correct_answer_json=json.dumps(
                {
                    "reference_text": reference_text,
                    "case_sensitive": False,
                    "allow_terminal_punctuation": True,
                },
                ensure_ascii=False,
            ),
            marks=5,
            skill_tag="sentence rearrangement",
            is_active=True,
        )
        db.add(question)
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
        flow._create_attempt_question(db, attempt, question, translation_language=translation_language)
        db.commit()
        db.close()
        return token, attempt.id

    def _create_mcq_pair_attempt(self, email: str):
        token = self._register_and_token(email)
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == email).first()
        assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()
        source_question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key=f"{email}-mcq-en",
            assessment_version=assessment.version,
            section="mcq",
            language="en",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            skill="vocabulary",
            question_type="mcq",
            prompt="Choose the word for a place to learn.",
            options_json=json.dumps(
                [
                    {"id": "option_1", "text": "school"},
                    {"id": "option_2", "text": "book"},
                    {"id": "option_3", "text": "river"},
                    {"id": "option_4", "text": "market"},
                ],
                ensure_ascii=False,
            ),
            correct_answer_json=json.dumps({"correct_option_id": "option_1"}, ensure_ascii=False),
            marks=2,
            skill_tag="vocabulary",
            is_active=True,
        )
        translation_question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key=f"{email}-mcq-hi",
            assessment_version=assessment.version,
            section="mcq",
            language="hi",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="hi",
            learning_language="hi",
            skill="vocabulary",
            question_type="mcq",
            prompt="पढ़ने के लिए जगह चुनें।",
            options_json=json.dumps(
                [
                    {"id": "option_1", "text": "स्कूल"},
                    {"id": "option_2", "text": "किताब"},
                    {"id": "option_3", "text": "नदी"},
                    {"id": "option_4", "text": "बाज़ार"},
                ],
                ensure_ascii=False,
            ),
            correct_answer_json=json.dumps({"correct_option_id": "option_1"}, ensure_ascii=False),
            marks=2,
            skill_tag="vocabulary",
            is_active=True,
        )
        db.add(source_question)
        db.add(translation_question)
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
        flow._create_attempt_question(db, attempt, source_question, translation_language="hi")
        db.commit()
        db.close()
        return token, attempt.id

    def test_mcq_payload_includes_speech_metadata(self):
        token = self._register_and_token("mcq-tts@example.com")
        with patch.object(flow, "ASSESSMENT_SKILL_ORDER", ["reading"]), patch.object(flow, "ASSESSMENT_SKILL_TARGETS", {"reading": 1}), patch.object(flow, "MAX_TOTAL_QUESTIONS", 1):
            response = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        question = data["current_question"]
        self.assertIn("tts_text", question)
        self.assertIn("tts_read_options", question)
        self.assertIn("prompt_translation", question)
        self.assertIn("translation_language", question)
        self.assertIsNone(question["input_mode"])
        self.assertIsNone(question["shuffled_tiles"])
        self.assertEqual(len(question["tts_read_options"]), len(question["options"]))
        self.assertTrue(all("translation" in option for option in question["options"]))
        self.assertNotIn("correct_answer", json.dumps(question))

    def test_sentence_completion_returns_tiles_and_validates_answer(self):
        token = self._register_and_token("tiles@example.com")
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "tiles@example.com").first()
        assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()
        question = (
            db.query(models.AssessmentQuestion)
            .filter(
                models.AssessmentQuestion.assessment_version == flow.ASSESSMENT_VERSION,
                models.AssessmentQuestion.question_type == "sentence_completion",
            )
            .first()
        )
        self.assertIsNotNone(user)
        self.assertIsNotNone(assessment)
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
        attempt_question = flow._create_attempt_question(db, attempt, question)
        db.commit()
        db.close()

        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]
        self.assertEqual(payload["input_mode"], "letter_tiles")
        self.assertTrue(payload["shuffled_tiles"])
        self.assertEqual(len({tile["id"] for tile in payload["shuffled_tiles"]}), len(payload["shuffled_tiles"]))
        self.assertNotIn("correct_answer", json.dumps(payload))

        db = self.Session()
        answer = self._answer_for_question(db, payload["question_id"])
        db.close()

        submitted = self.client.post(
            f"/assessment/attempts/{started.json()['attempt_id']}/answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": payload["attempt_question_id"],
                "answer": answer,
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertIn("next_question", submitted.json())

    def test_mcq_translations_remain_paired_after_shuffle(self):
        token, attempt_id = self._create_mcq_pair_attempt("mcq-pair@example.com")
        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]
        pairs = {option["text"]: option["translation"] for option in payload["options"]}
        self.assertEqual(pairs["school"], "स्कूल")
        self.assertEqual(pairs["book"], "किताब")
        self.assertEqual(pairs["river"], "नदी")
        self.assertEqual(pairs["market"], "बाज़ार")

    def test_sentence_tiles_remain_paired_after_shuffle(self):
        token, attempt_id = self._create_sentence_rearrange_attempt(
            "sentence-pair@example.com",
            "Ravi reads a book every morning.",
            translation_language="hi",
        )
        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]
        tile_pairs = {tile["value"].rstrip("."): tile["translation"] for tile in payload["shuffled_tiles"]}
        self.assertEqual(tile_pairs["Ravi"], "रवि")
        self.assertEqual(tile_pairs["reads"], "पढ़ता")
        self.assertEqual(tile_pairs["book"], "किताब")
        self.assertEqual(tile_pairs["every"], "हर")
        self.assertEqual(tile_pairs["morning"], "सुबह")

    def test_sentence_rearrange_returns_word_tiles_and_normalizes_answer(self):
        token, attempt_id = self._create_sentence_rearrange_attempt("rearrange@example.com", "We read read books.")
        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]
        self.assertEqual(payload["input_mode"], "word_tiles")
        self.assertIn("translation_language", payload)
        self.assertTrue(payload["shuffled_tiles"])
        self.assertEqual(len({tile["id"] for tile in payload["shuffled_tiles"]}), len(payload["shuffled_tiles"]))
        self.assertIn("read", [tile["value"] for tile in payload["shuffled_tiles"]])
        self.assertGreaterEqual([tile["value"] for tile in payload["shuffled_tiles"]].count("read"), 2)
        self.assertTrue(all("translation" in tile for tile in payload["shuffled_tiles"]))
        self.assertNotIn("We read read books.", json.dumps(payload))
        self.assertNotIn("correct_answer", json.dumps(payload))

        submitted = self.client.post(
            f"/assessment/attempts/{attempt_id}/answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": payload["attempt_question_id"],
                "answer": {"text": "we read read books"},
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertTrue(submitted.json()["correct"])

    def test_sentence_rearrange_tokens_match_complete_tamil_and_telugu_sentences(self):
        samples = [
            "ரவி ஒவ்வொரு காலையும் புத்தகம் வாசிக்கிறான்.",
            "రవి ప్రతి ఉదయం పుస్తకం చదువుతాడు.",
        ]
        for sentence in samples:
            with self.subTest(sentence=sentence):
                tiles = build_word_tiles(sentence)
                self.assertTrue(word_tiles_match_sentence(tiles, sentence))
                self.assertEqual(len(tiles), len(sentence_word_tokens(sentence)))
                self.assertGreaterEqual(len(tiles), 4)
                self.assertLessEqual(len(tiles), 8)
                self.assertTrue(all(isinstance(tile["original_order"], int) for tile in tiles))

    def test_sentence_rearrange_repeated_words_remain_separate_tiles(self):
        sentence = "நாம் நாம் தினமும் படிக்கிறோம்."
        tiles = build_word_tiles(sentence)
        values = [tile["value"].rstrip(".") for tile in tiles]
        self.assertEqual(values.count("நாம்"), 2)
        self.assertEqual(len({tile["id"] for tile in tiles}), len(tiles))
        self.assertTrue(word_tiles_match_sentence(tiles, sentence))

    def test_sentence_rearrange_punctuation_and_unicode_are_preserved(self):
        sentence = "బిడ్డ పెన్సిల్‌ను బల్లపై పెడుతుంది."
        tiles = build_word_tiles(sentence)
        values = [tile["value"] for tile in tiles]
        self.assertIn("పెన్సిల్‌ను", values)
        self.assertIn("పెడుతుంది.", values)
        self.assertTrue(word_tiles_match_sentence(tiles, sentence.rstrip(".")))

    def test_tamil_telugu_sentence_tile_translations_remain_paired_after_shuffle(self):
        cases = [
            (
                "tile-translate-ta@example.com",
                "ta",
                "ta-typing-rearrange-1",
                {
                    "ரவி": "Ravi",
                    "ஒவ்வொரு": "every",
                    "காலையும்": "morning",
                    "புத்தகம்": "book",
                    "வாசிக்கிறான்.": "reads",
                },
            ),
            (
                "tile-translate-te@example.com",
                "te",
                "te-typing-rearrange-1",
                {
                    "రవి": "Ravi",
                    "ప్రతి": "every",
                    "ఉదయం": "morning",
                    "పుస్తకం": "book",
                    "చదువుతాడు.": "reads",
                },
            ),
        ]
        for email, language, stable_key, expected_pairs in cases:
            with self.subTest(language=language):
                token = self._register_custom_and_token(
                    {
                        "full_name": f"{language} Learner",
                        "age": 20,
                        "email": email,
                        "password": "password123",
                        "comfortable_language": "English",
                        "learning_language": "Tamil" if language == "ta" else "Telugu",
                        "experience_level": "Beginner",
                        "education_level": "Primary",
                        "role": "learner",
                    }
                )
                db = self.Session()
                user = db.query(models.User).filter(models.User.email == email).first()
                assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()
                question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.stable_key == stable_key).first()
                attempt = models.AssessmentAttempt(
                    user_id=user.id,
                    assessment_id=assessment.id,
                    assessment_version=assessment.version,
                    preferred_language=language,
                    status="in_progress",
                )
                db.add(attempt)
                db.flush()
                flow._create_attempt_question(db, attempt, question, translation_language="en")
                db.commit()
                db.close()

                started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(started.status_code, 200, started.text)
                payload = started.json()["current_question"]
                actual_pairs = {tile["value"]: tile["translation"] for tile in payload["shuffled_tiles"]}
                self.assertEqual(actual_pairs, expected_pairs)
                self.assertEqual(len({tile["id"] for tile in payload["shuffled_tiles"]}), len(payload["shuffled_tiles"]))

    def test_malformed_existing_sentence_tiles_are_repaired_before_display(self):
        token, attempt_id = self._create_sentence_rearrange_attempt(
            "rearrange-repair@example.com",
            "Ravi reads a book every morning.",
        )
        db = self.Session()
        attempt_question = (
            db.query(models.AssessmentAttemptQuestion)
            .filter(models.AssessmentAttemptQuestion.attempt_id == attempt_id)
            .first()
        )
        attempt_question.shuffled_tiles_json = json.dumps(
            [
                {"id": "tile_1", "value": "Ravi"},
                {"id": "tile_2", "value": "reads"},
                {"id": "tile_3", "value": "extra"},
            ],
            ensure_ascii=False,
        )
        db.commit()
        db.close()

        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]
        values = [tile["value"] for tile in payload["shuffled_tiles"]]
        self.assertCountEqual([value.rstrip(".") for value in values], ["Ravi", "reads", "a", "book", "every", "morning"])
        self.assertTrue(word_tiles_match_sentence(payload["shuffled_tiles"], "Ravi reads a book every morning."))

    def test_sentence_rearrange_rejects_incorrect_word_order(self):
        token, attempt_id = self._create_sentence_rearrange_attempt("rearrange-wrong@example.com", "We read read books.")
        started = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(started.status_code, 200, started.text)
        payload = started.json()["current_question"]

        submitted = self.client.post(
            f"/assessment/attempts/{attempt_id}/answer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "attempt_question_id": payload["attempt_question_id"],
                "answer": {"text": "read we read books"},
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertFalse(submitted.json()["correct"])

    def test_voice_question_payload_for_english_learning_language(self):
        token = self._register_custom_and_token(
            {
                "full_name": "Voice Learner",
                "age": 20,
                "email": "voice-en@example.com",
                "password": "password123",
                "comfortable_language": "Hindi",
                "learning_language": "English",
                "experience_level": "Beginner",
                "education_level": "Primary",
                "role": "learner",
            }
        )
        with patch.object(flow, "ASSESSMENT_SKILL_ORDER", ["writing"]), patch.object(flow, "ASSESSMENT_SKILL_TARGETS", {"writing": 1}), patch.object(flow, "MAX_TOTAL_QUESTIONS", 1):
            response = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()["current_question"]
        self.assertEqual(payload["input_mode"], "voice")
        self.assertTrue(payload["stt_enabled"])
        self.assertIn(payload["question_type"], {"spoken_answer", "spoken_fill_blank", "reading_aloud", "sentence_repetition", "pronunciation", "speaking"})
        self.assertEqual(payload["learning_language"], "en")
        self.assertTrue(payload["instruction_text"].strip())
        self.assertTrue(payload["target_text"].strip())
        self.assertTrue(payload["target_translation"].strip())
        self.assertEqual(payload["tts_text"], payload["target_text"])
        self.assertNotIn("correct_answer", json.dumps(payload))

    def test_voice_question_payload_for_hindi_learning_language(self):
        token = self._register_custom_and_token(
            {
                "full_name": "Voice Learner Hindi",
                "age": 20,
                "email": "voice-hi@example.com",
                "password": "password123",
                "comfortable_language": "English",
                "learning_language": "Hindi",
                "experience_level": "Beginner",
                "education_level": "Primary",
                "role": "learner",
            }
        )
        with patch.object(flow, "ASSESSMENT_SKILL_ORDER", ["writing"]), patch.object(flow, "ASSESSMENT_SKILL_TARGETS", {"writing": 1}), patch.object(flow, "MAX_TOTAL_QUESTIONS", 1):
            response = self.client.post("/assessment/start", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()["current_question"]
        self.assertEqual(payload["input_mode"], "voice")
        self.assertTrue(payload["stt_enabled"])
        self.assertEqual(payload["learning_language"], "hi")
        self.assertTrue(payload["instruction_text"].strip())
        self.assertTrue(payload["target_text"].strip())
        self.assertTrue(payload["target_translation"].strip())
        self.assertEqual(payload["tts_text"], payload["target_text"])

    def test_language_locale_normalization_accepts_indian_locales(self):
        self.assertEqual(normalize_language("hi-IN"), "hi")
        self.assertEqual(normalize_language("ta-IN"), "ta")
        self.assertEqual(normalize_language("te-IN"), "te")

    def test_mismatched_language_questions_are_skipped(self):
        token = self._register_custom_and_token(
            {
                "full_name": "Tamil Learner",
                "age": 20,
                "email": "tamil-skip@example.com",
                "password": "password123",
                "comfortable_language": "English",
                "learning_language": "Tamil",
                "experience_level": "Beginner",
                "education_level": "Primary",
                "role": "learner",
            }
        )
        db = self.Session()
        user = db.query(models.User).filter(models.User.email == "tamil-skip@example.com").first()
        assessment = db.query(models.Assessment).filter(models.Assessment.version == flow.ASSESSMENT_VERSION).first()

        bad_question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="ta-bad-hindi-content",
            assessment_version=assessment.version,
            section="reading",
            language="ta",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="ta",
            learning_language="ta",
            skill="reading",
            question_type="mcq",
            prompt="यह हिंदी वाक्य है",
            options_json=json.dumps(
                [
                    {"id": "option_1", "text": "स्कूल"},
                    {"id": "option_2", "text": "किताब"},
                ],
                ensure_ascii=False,
            ),
            correct_answer_json=json.dumps({"correct_option_id": "option_1"}, ensure_ascii=False),
            marks=2,
            skill_tag="vocabulary",
            is_active=True,
        )
        good_question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="ta-good-content",
            assessment_version=assessment.version,
            section="reading",
            language="ta",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="ta",
            learning_language="ta",
            skill="reading",
            question_type="mcq",
            prompt="பள்ளிக்குச் செல்லும் இடத்தைத் தேர்ந்தெடுக்கவும்.",
            options_json=json.dumps(
                [
                    {"id": "option_1", "text": "பள்ளி"},
                    {"id": "option_2", "text": "புத்தகம்"},
                ],
                ensure_ascii=False,
            ),
            correct_answer_json=json.dumps({"correct_option_id": "option_1"}, ensure_ascii=False),
            marks=2,
            skill_tag="vocabulary",
            is_active=True,
        )
        db.add_all([bad_question, good_question])
        db.flush()
        attempt = models.AssessmentAttempt(
            user_id=user.id,
            assessment_id=assessment.id,
            assessment_version=assessment.version,
            preferred_language="ta",
            status="in_progress",
        )
        db.add(attempt)
        db.flush()

        candidates = flow._candidate_questions(db, user, attempt.id, "reading", 1)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].id, good_question.id)
        self.assertNotIn(bad_question.id, [question.id for question in candidates])
        db.close()


if __name__ == "__main__":
    unittest.main()
