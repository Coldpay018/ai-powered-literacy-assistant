import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import models
from database import Base
from gamification_service import XP_PUZZLE_SET_COMPLETION
from main import app, get_db
from puzzle_service import create_puzzle_set, create_puzzles, split_graphemes, validate_puzzle
from schema_updates import apply_sqlite_schema_updates


class PuzzleTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

        db = self.Session()
        self.user = self._create_user(db, "puzzle@example.com", comfortable_language="hi", learning_language="kn")
        self.other_user = self._create_user(db, "other-puzzle@example.com")
        self.lesson = self._create_lesson(db)
        self.base_set = self._create_set(db, "Base puzzles", puzzle_count=2)
        db.commit()
        self.base_set_id = self.base_set.id
        self.base_puzzle_ids = [puzzle.id for puzzle in self.base_set.puzzles]
        db.close()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.token = auth.create_access_token(self.user.id)
        self.other_token = auth.create_access_token(self.other_user.id)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _create_user(self, db, email, comfortable_language="en", learning_language="kn"):
        user = models.User(
            full_name="Puzzle Learner",
            age=20,
            email=email,
            hashed_password=auth.hash_password("password123"),
            comfortable_language=comfortable_language,
            learning_language=learning_language,
            preferred_language=comfortable_language,
            experience_level="Beginner",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    def _create_lesson(self, db):
        course = models.Course(
            title="Puzzle Course",
            description="Puzzle course",
            skill="reading",
            difficulty_level="beginner",
            language="kn",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="Puzzle Module",
            description="Puzzle module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        lesson = models.Lesson(
            course_id=course.id,
            module_id=module.id,
            title="Puzzle Lesson",
            description="Puzzle lesson",
            content="Vocabulary",
            skill="reading",
            skill_type="reading",
            difficulty_level="beginner",
            proficiency_level="beginner",
            language="kn",
            difficulty_order=1,
            estimated_minutes=10,
            estimated_duration_minutes=10,
            sequence_order=1,
        )
        db.add(lesson)
        db.flush()
        return lesson

    def _create_set(self, db, title, puzzle_count=2):
        puzzle_set = create_puzzle_set(
            db,
            user_id=self.user.id,
            lesson_id=self.lesson.id,
            title=title,
            skill="reading",
            difficulty=1,
            learning_language="kn",
            comfortable_language="hi",
        )
        puzzle_specs = []
        words = ["ಮನೆ", "ನೀರು", "ಅಮ್ಮ", "ಪುಸ್ತಕ", "ಶಾಲೆ"]
        for index, word in enumerate(words[:puzzle_count], start=1):
            puzzle_specs.append(
                {
                    "puzzle_type": "jumbled_word",
                    "instruction_text": "सही क्रम चुनें",
                    "prompt_text": "ಕನ್ನಡ ಪದ",
                    "puzzle_data": {"tiles": list(reversed(split_graphemes(word))), "clue": "कन्नड़ शब्द"},
                    "answer_data": {"target_word": word, "accepted_answers": [word]},
                    "sequence_order": index,
                }
            )
        create_puzzles(db, puzzle_set_id=puzzle_set.id, puzzles=puzzle_specs)
        db.flush()
        return puzzle_set

    def _post_attempt(self, puzzle_id, submitted_answer, token=None):
        return self.client.post(
            f"/puzzles/{puzzle_id}/attempt",
            headers={"Authorization": f"Bearer {token or self.token}"},
            json={"submitted_answer": submitted_answer, "is_correct": True, "score": 1},
        )

    def test_puzzle_set_and_puzzle_creation_hides_answer_data(self):
        response = self.client.get(f"/puzzles/sets/{self.base_set_id}", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["comfortable_language"], "hi")
        self.assertEqual(data["learning_language"], "kn")
        self.assertNotIn("answer_data", data["puzzles"][0])
        self.assertNotIn("answer_data_json", response.text)
        self.assertEqual(data["puzzles"][0]["instruction_text"], "सही क्रम चुनें")
        self.assertTrue(any(tile in {"ಮ", "ನೆ"} or "ೀ" in tile for tile in data["puzzles"][0]["puzzle_data"]["tiles"]))

    def test_jumbled_word_validation_rejects_missing_extra_and_bad_repeated_tiles(self):
        with self.assertRaises(ValueError):
            validate_puzzle(
                "jumbled_word",
                {"tiles": ["ಮ"]},
                {"target_word": "ಮನೆ", "accepted_answers": ["ಮನೆ"]},
            )
        with self.assertRaises(ValueError):
            validate_puzzle(
                "jumbled_word",
                {"tiles": ["ಮ", "ನೆ", "x"]},
                {"target_word": "ಮನೆ", "accepted_answers": ["ಮನೆ"]},
            )
        with self.assertRaises(ValueError):
            validate_puzzle(
                "jumbled_word",
                {"tiles": ["ಅ", "ಮ"]},
                {"target_word": "ಅಮ್ಮ", "accepted_answers": ["ಅಮ್ಮ"]},
            )

    def test_kannada_grapheme_clusters_are_preserved(self):
        clusters = split_graphemes("ಕ್ರಿಯೆ")
        self.assertIn("ಕ್ರಿ", clusters)
        puzzle_data, _answer_data = validate_puzzle(
            "jumbled_word",
            {"tiles": list(reversed(clusters))},
            {"target_word": "ಕ್ರಿಯೆ", "accepted_answers": ["ಕ್ರಿಯೆ"]},
        )
        self.assertCountEqual(puzzle_data["tiles"], clusters)

    def test_jumbled_shuffle_is_not_identical_when_possible(self):
        puzzle_data, _answer_data = validate_puzzle(
            "jumbled_word",
            {"tiles": ["ಮ", "ನೆ"]},
            {"target_word": "ಮನೆ", "accepted_answers": ["ಮನೆ"]},
        )
        self.assertNotEqual("".join(puzzle_data["tiles"]), "ಮನೆ")

    def test_matching_validation_rejects_incomplete_duplicate_and_ambiguous_pairs(self):
        left_items = [{"id": "l1", "text": "ಮನೆ"}, {"id": "l2", "text": "ನೀರು"}]
        right_items = [{"id": "r1", "text": "घर"}, {"id": "r2", "text": "पानी"}]
        valid_data, valid_answer = validate_puzzle(
            "matching",
            {"left_items": left_items, "right_items": list(reversed(right_items))},
            {"pairs": [{"left_id": "l1", "right_id": "r1"}, {"left_id": "l2", "right_id": "r2"}]},
        )
        self.assertEqual(valid_data["right_items"][0]["id"], "r2")
        self.assertEqual(valid_answer["pairs"][0]["right_id"], "r1")
        with self.assertRaises(ValueError):
            validate_puzzle("matching", {"left_items": left_items, "right_items": right_items}, {"pairs": [{"left_id": "l1", "right_id": "r1"}]})
        with self.assertRaises(ValueError):
            validate_puzzle("matching", {"left_items": left_items, "right_items": right_items}, {"pairs": [{"left_id": "l1", "right_id": "r1"}, {"left_id": "l1", "right_id": "r2"}]})
        with self.assertRaises(ValueError):
            validate_puzzle("matching", {"left_items": left_items + [{"id": "l2", "text": "ಅಮ್ಮ"}], "right_items": right_items}, {"pairs": []})

    def test_backend_calculates_correctness_and_rejects_malformed_answers(self):
        puzzle_id = self.base_puzzle_ids[0]
        bad = self._post_attempt(puzzle_id, {"tiles": ["ಮ", "ನೆ", "x"]})
        self.assertEqual(bad.status_code, 400)
        response = self._post_attempt(puzzle_id, {"tiles": ["ನೆ", "ಮ"]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["attempt"]["is_correct"])
        self.assertEqual(response.json()["attempt"]["score"], 0)
        db = self.Session()
        try:
            self.assertEqual(db.query(models.PuzzleAttempt).filter(models.PuzzleAttempt.puzzle_id == puzzle_id).count(), 1)
        finally:
            db.close()

    def test_user_access_isolation(self):
        response = self.client.get(f"/puzzles/sets/{self.base_set_id}", headers={"Authorization": f"Bearer {self.other_token}"})
        self.assertEqual(response.status_code, 404)
        response = self._post_attempt(self.base_puzzle_ids[0], {"tiles": ["ನೆ", "ಮ"]}, token=self.other_token)
        self.assertEqual(response.status_code, 404)

    def test_meaningful_completion_awards_xp_and_streak_once(self):
        db = self.Session()
        try:
            puzzle_set = self._create_set(db, "XP puzzles", puzzle_count=5)
            db.commit()
            puzzle_ids = [puzzle.id for puzzle in puzzle_set.puzzles]
            expected_answers = [json.loads(puzzle.answer_data_json)["target_word"] for puzzle in puzzle_set.puzzles]
        finally:
            db.close()
        xp = 0
        for puzzle_id, answer in zip(puzzle_ids, expected_answers):
            response = self._post_attempt(puzzle_id, {"answer": answer})
            self.assertEqual(response.status_code, 200)
            xp += response.json()["xp_earned"]
        self.assertEqual(xp, XP_PUZZLE_SET_COMPLETION)

        duplicate = self._post_attempt(puzzle_ids[0], {"answer": expected_answers[0]})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["xp_earned"], 0)
        db = self.Session()
        try:
            self.assertEqual(db.query(func.coalesce(func.sum(models.XPTransaction.amount), 0)).filter(models.XPTransaction.user_id == self.user.id).scalar(), XP_PUZZLE_SET_COMPLETION)
            self.assertEqual(db.query(models.DailyStreakActivity).filter(models.DailyStreakActivity.user_id == self.user.id).count(), 1)
        finally:
            db.close()

    def test_low_accuracy_and_incomplete_sets_award_no_xp(self):
        db = self.Session()
        try:
            puzzle_set = self._create_set(db, "Low accuracy puzzles", puzzle_count=5)
            db.commit()
            puzzle_ids = [puzzle.id for puzzle in puzzle_set.puzzles]
            expected_answers = [json.loads(puzzle.answer_data_json)["target_word"] for puzzle in puzzle_set.puzzles]
        finally:
            db.close()
        for puzzle_id, answer in zip(puzzle_ids[:2], expected_answers[:2]):
            response = self._post_attempt(puzzle_id, {"answer": answer})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["xp_earned"], 0)
        for puzzle_id, answer in zip(puzzle_ids[2:], expected_answers[2:]):
            response = self._post_attempt(puzzle_id, {"tiles": list(reversed(split_graphemes(answer)))})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["xp_earned"], 0)
        db = self.Session()
        try:
            self.assertEqual(db.query(models.XPTransaction).filter(models.XPTransaction.user_id == self.user.id).count(), 0)
            self.assertEqual(db.query(models.DailyStreakActivity).filter(models.DailyStreakActivity.user_id == self.user.id).count(), 0)
        finally:
            db.close()

    def test_later_local_day_completion_can_award_again(self):
        db = self.Session()
        try:
            puzzle_set = self._create_set(db, "Daily repeat puzzles", puzzle_count=1)
            puzzle = puzzle_set.puzzles[0]
            db.commit()
            puzzle_id = puzzle.id
            answer = json.loads(puzzle.answer_data_json)["target_word"]
        finally:
            db.close()
        first = self._post_attempt(puzzle_id, {"answer": answer})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["xp_earned"], XP_PUZZLE_SET_COMPLETION)
        db = self.Session()
        try:
            from puzzle_service import submit_puzzle_attempt

            response = submit_puzzle_attempt(
                db,
                user_id=self.user.id,
                puzzle_id=puzzle_id,
                submitted_answer={"answer": answer},
                completed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
            db.commit()
            self.assertEqual(response["xp_earned"], XP_PUZZLE_SET_COMPLETION)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
