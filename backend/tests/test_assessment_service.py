import unittest
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assessment_service import (
    BLUEPRINT,
    classify_proficiency,
    _score_completion,
    _score_copy,
    _score_short,
)
import assessment_flow_service as flow
import models
from seed_assessment import build_question_bank


class AssessmentQuestionBankTests(unittest.TestCase):
    def test_question_bank_has_required_language_and_section_counts(self):
        bank = build_question_bank()

        self.assertEqual(len(bank), 275)
        by_language = Counter(question["language"] for question in bank)
        self.assertEqual(by_language, {"en": 55, "hi": 55, "ta": 55, "te": 55, "kn": 55})

        by_language_section = Counter(
            (question["language"], question["section"]) for question in bank
        )
        for language in ["en", "hi", "ta", "te", "kn"]:
            self.assertEqual(by_language_section[(language, "reading")], 13)
            self.assertEqual(by_language_section[(language, "typing")], 21)
            self.assertEqual(by_language_section[(language, "mcq")], 21)

    def test_blueprint_counts_match_required_assessment_size(self):
        self.assertEqual(sum(BLUEPRINT["reading"].values()), 5)
        self.assertEqual(sum(BLUEPRINT["typing"].values()), 3)
        self.assertEqual(sum(BLUEPRINT["mcq"].values()), 5)

    def test_option_questions_have_correct_option_and_do_not_reveal_sentence(self):
        for question in build_question_bank():
            if question["question_type"] not in {"reading_mcq", "mcq"}:
                continue

            options = question["options"]
            correct_id = question["correct"]["correct_option_id"]
            option_by_id = {option["id"]: option["text"] for option in options}

            self.assertIn(correct_id, option_by_id, question["stable_key"])
            self.assertEqual(len(option_by_id), len(options), question["stable_key"])
            self.assertEqual(sum(1 for option in options if option["id"] == correct_id), 1, question["stable_key"])
            self.assertTrue(all(option["text"].strip() for option in options), question["stable_key"])
            if question["skill_tag"] == "sentence meaning":
                self.assertNotIn(option_by_id[correct_id], question["prompt"])

    def test_question_bank_includes_normalized_difficulty_metadata(self):
        bank = build_question_bank()

        ratings = {question["difficulty_rating"] for question in bank}
        self.assertEqual(ratings, {1, 2, 3, 4, 5})
        self.assertTrue(all(question["comfortable_language"] == question["language"] for question in bank))
        self.assertTrue(all(question["learning_language"] == question["language"] for question in bank))

    def test_invalid_mcq_is_rejected_by_runtime_validator(self):
        question = models.AssessmentQuestion(
            assessment_id=1,
            stable_key="invalid-mcq",
            assessment_version="initial-literacy-v1",
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
            prompt="Choose the word used for reading.",
            options_json='[{"id":"option_1","text":""}]',
            correct_answer_json='{"correct_option_id":"option_2"}',
            marks=2,
            skill_tag="vocabulary",
            is_active=True,
        )
        self.assertFalse(flow._is_valid_assessment_question(question))

    def test_spoken_fill_blank_requires_a_single_unambiguous_answer(self):
        valid_question = models.AssessmentQuestion(
            assessment_id=1,
            stable_key="spoken-fill-blank-valid",
            assessment_version="initial-literacy-v1",
            section="typing",
            language="hi",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="hi",
            learning_language="hi",
            skill="writing",
            question_type="spoken_fill_blank",
            prompt="वाक्य को बोलकर पूरा कीजिए।",
            correct_answer_json='{"display_text":"मैं पढ़ने के लिए ____ जाता हूँ।","accepted_answers":["स्कूल"],"reference_text":"मैं पढ़ने के लिए स्कूल जाता हूँ।"}',
            scoring_config_json="{}",
            marks=5,
            skill_tag="copy accuracy",
            is_active=True,
        )
        practice_only_question = models.AssessmentQuestion(
            assessment_id=1,
            stable_key="spoken-fill-blank-practice",
            assessment_version="initial-literacy-v1",
            section="typing",
            language="hi",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Adult",
            experience_level="Beginner",
            comfortable_language="hi",
            learning_language="hi",
            skill="writing",
            question_type="spoken_fill_blank",
            prompt="वाक्य को बोलकर पूरा कीजिए।",
            correct_answer_json='{"display_text":"मैं ____ जाता हूँ।","accepted_answers":["स्कूल","बाजार"],"reference_text":"मैं स्कूल जाता हूँ।"}',
            scoring_config_json='{"practice_only": true}',
            marks=5,
            skill_tag="copy accuracy",
            is_active=True,
        )

        self.assertTrue(flow._is_valid_assessment_question(valid_question))
        self.assertFalse(flow._is_valid_assessment_question(practice_only_question))


class AssessmentScoringTests(unittest.TestCase):
    def test_copy_typing_scores_exact_answer(self):
        marks, details = _score_copy("I can read.", "I can read.", 5)

        self.assertEqual(marks, 5)
        self.assertEqual(details["similarity"], 100)

    def test_sentence_completion_scores_exact_and_partial(self):
        full_marks, full_details = _score_completion(
            "water",
            {"accepted_answers": ["water"], "required_keywords": ["water"]},
            6,
        )
        partial_marks, partial_details = _score_completion(
            "pen",
            {"accepted_answers": ["pen pencil"], "required_keywords": ["pen", "pencil"]},
            6,
        )

        self.assertEqual(full_marks, 6)
        self.assertEqual(full_details["match"], "exact")
        self.assertEqual(partial_marks, 1.5)
        self.assertEqual(partial_details["match"], "partial_keywords")

    def test_short_response_rubric_awards_structured_answer(self):
        marks, details = _score_short(
            "I go to school every morning. I read a book.",
            {"required_keywords": ["school", "read"], "minimum_words": 6},
            10,
        )

        self.assertEqual(marks, 10)
        self.assertEqual(details["rubric_points"], 10)

    def test_proficiency_safeguards(self):
        self.assertEqual(classify_proficiency(75, 45, 80), "intermediate")
        self.assertEqual(classify_proficiency(45, 20, 80), "beginner")
        self.assertEqual(classify_proficiency(72, 70, 70), "advanced")


if __name__ == "__main__":
    unittest.main()
