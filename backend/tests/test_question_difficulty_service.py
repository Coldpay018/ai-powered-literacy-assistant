import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import models
from assessment_service import submit_attempt
from adaptive_difficulty_service import evaluate_difficulty
from database import Base
from main import app, get_db
from question_difficulty_service import (
    build_starting_difficulty_profile,
    determine_starting_difficulty,
    filter_question_query,
)
from question_taxonomy import normalize_difficulty_value, score_to_difficulty
from schema_updates import apply_sqlite_schema_updates
from seed_assessment import ASSESSMENT_VERSION


def user_payload(email="learner@example.com", experience_level="Beginner"):
    return {
        "full_name": "Learner One",
        "age": 20,
        "email": email,
        "password": "password123",
        "comfortable_language": "Hindi",
        "learning_language": "English",
        "experience_level": experience_level,
        "education_level": "Primary",
        "role": "learner",
    }


class QuestionDifficultyRuleTests(unittest.TestCase):
    def test_all_five_difficulty_levels_are_supported(self):
        self.assertEqual([normalize_difficulty_value(level) for level in range(1, 6)], [1, 2, 3, 4, 5])
        self.assertEqual([score_to_difficulty(score) for score in [10, 40, 60, 80, 95]], [1, 2, 3, 4, 5])

    def test_invalid_difficulty_metadata_is_rejected(self):
        for invalid_value in [0, 6, "0", "7", "easy"]:
            with self.assertRaises(ValueError):
                normalize_difficulty_value(invalid_value)

    def test_beginner_intermediate_advanced_fallback(self):
        assessment = None
        for level, expected in [("Beginner", 2), ("Intermediate", 3), ("Advanced", 4)]:
            user = models.User(
                id=1,
                full_name="Learner",
                age=24,
                email=f"{level.lower()}@example.com",
                hashed_password="x",
                comfortable_language="en",
                learning_language="hi",
                experience_level=level,
                preferred_language="en",
                education_level="Primary",
                role="learner",
                is_active=True,
            )
            self.assertEqual(determine_starting_difficulty(user, assessment, "reading"), expected)

    def test_assessment_result_overrides_fallback(self):
        user = models.User(
            id=2,
            full_name="Learner",
            age=24,
            email="assessment@example.com",
            hashed_password="x",
            comfortable_language="en",
            learning_language="hi",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        assessment = SimpleNamespace(
            overall_score=92,
            reading_score=96,
            typing_score=60,
            mcq_score=44,
        )

        self.assertEqual(determine_starting_difficulty(user, assessment, "reading"), 5)
        self.assertEqual(determine_starting_difficulty(user, assessment, "writing"), 3)

    def test_separate_difficulty_by_skill_from_progress(self):
        user = models.User(
            id=3,
            full_name="Learner",
            age=24,
            email="progress@example.com",
            hashed_password="x",
            comfortable_language="en",
            learning_language="hi",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        progress_records = []
        for record_id, (skill, score, difficulty) in enumerate(
            [("reading", 94, "advanced"), ("writing", 38, "beginner")],
            start=1,
        ):
            progress = models.LearnerProgress(
                id=record_id,
                user_id=user.id,
                lesson_id=record_id,
                completion_status="completed",
                status="completed",
                progress_percentage=100,
                questions_attempted=4,
                correct_answers=4,
                incorrect_answers=0,
                current_difficulty=difficulty,
                score=score,
                best_quiz_score=score,
                attempt_count=1,
                time_spent_seconds=120,
                time_spent=120,
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
                completed_at=datetime.now(timezone.utc),
                last_accessed_at=datetime.now(timezone.utc),
            )
            progress.__dict__["lesson"] = SimpleNamespace(skill_type=skill, skill=skill)
            progress_records.append(progress)

        self.assertEqual(determine_starting_difficulty(user, None, "reading", progress_records), 5)
        self.assertEqual(determine_starting_difficulty(user, None, "writing", progress_records), 2)


class QuestionDifficultyFilteringTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_question_filtering_supports_skill_difficulty_language_and_type(self):
        assessment = models.Assessment(
            stable_key="assessment-filter",
            title="Assessment",
            version=ASSESSMENT_VERSION,
            is_active=True,
        )
        self.db.add(assessment)
        self.db.flush()
        q1 = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="q1",
            assessment_version=ASSESSMENT_VERSION,
            section="reading",
            language="en",
            difficulty="advanced",
            difficulty_rating=5,
            age_group="Adult",
            experience_level="Advanced",
            comfortable_language="en",
            learning_language="en",
            skill="reading",
            question_type="reading_mcq",
            prompt="Prompt one",
            marks=2,
            skill_tag="passage comprehension",
            correct_answer_json="{}",
        )
        q2 = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="q2",
            assessment_version=ASSESSMENT_VERSION,
            section="typing",
            language="hi",
            difficulty="beginner",
            difficulty_rating=2,
            age_group="Child",
            experience_level="Beginner",
            comfortable_language="hi",
            learning_language="hi",
            skill="writing",
            question_type="copy_typing",
            prompt="Prompt two",
            marks=2,
            skill_tag="copy accuracy",
            correct_answer_json="{}",
        )
        self.db.add_all([q1, q2])
        self.db.commit()

        query = filter_question_query(
            self.db.query(models.AssessmentQuestion),
            models.AssessmentQuestion,
            skill="reading",
            difficulty=5,
            age_group="Adult",
            experience_level="Advanced",
            comfortable_language="en",
            learning_language="en",
            question_type="reading_comprehension",
        )
        results = query.all()
        self.assertEqual([question.stable_key for question in results], ["q1"])


class QuestionDifficultyMigrationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.engine = engine
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_schema_update_backfills_question_metadata(self):
        db = self.Session()
        user = models.User(
            full_name="Learner One",
            age=24,
            email="legacy@example.com",
            hashed_password="password",
            comfortable_language=None,
            learning_language=None,
            experience_level=None,
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        db.add(user)
        course = models.Course(
            title="Course",
            description="Course",
            skill="reading",
            difficulty_level="beginner",
            language="en",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="Module",
            description="Module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        lesson = models.Lesson(
            course_id=course.id,
            module_id=module.id,
            title="Lesson",
            description="Lesson",
            content="Content",
            skill="reading",
            skill_type="reading",
            difficulty_level="beginner",
            proficiency_level="beginner",
            language="en",
            difficulty_order=1,
            estimated_minutes=10,
            estimated_duration_minutes=10,
            sequence_order=1,
        )
        db.add(lesson)
        db.flush()
        assessment = models.Assessment(
            stable_key="assessment",
            title="Assessment",
            version=ASSESSMENT_VERSION,
            is_active=True,
        )
        db.add(assessment)
        db.flush()
        db.add(
            models.AssessmentQuestion(
                assessment_id=assessment.id,
                stable_key="legacy-assessment",
                assessment_version=ASSESSMENT_VERSION,
                section="mcq",
                language="en",
                difficulty="advanced",
                question_type="mcq",
                prompt="Prompt",
                marks=2,
                skill_tag="basic comprehension",
                correct_answer_json="{}",
            )
        )
        db.add(
            models.LessonContent(
                lesson_id=lesson.id,
                content_type="quiz",
                title="Quiz",
                metadata_json='{"passing_score": 60}',
                sequence_order=1,
            )
        )
        db.flush()
        db.add(
            models.LessonQuestion(
                lesson_id=lesson.id,
                question_text="Question",
                question_type="mcq",
                skill="reading",
                difficulty_level="beginner",
                minimum_age=9,
                maximum_age=11,
                correct_answer="Answer",
                sequence_order=1,
                points=1,
            )
        )
        db.commit()
        db.close()

        apply_sqlite_schema_updates(self.engine)

        db = self.Session()
        assessment_question = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.stable_key == "legacy-assessment").first()
        lesson_question = db.query(models.LessonQuestion).first()

        self.assertEqual(assessment_question.difficulty_rating, 5)
        self.assertEqual(assessment_question.age_group, "Adult")
        self.assertEqual(assessment_question.experience_level, "Advanced")
        self.assertEqual(assessment_question.comfortable_language, "en")
        self.assertEqual(assessment_question.learning_language, "en")
        self.assertEqual(assessment_question.skill, "comprehension")
        self.assertEqual(lesson_question.difficulty_rating, 1)
        self.assertEqual(lesson_question.age_group, "Child")
        self.assertEqual(lesson_question.experience_level, "Beginner")
        self.assertEqual(lesson_question.comfortable_language, "en")
        self.assertEqual(lesson_question.learning_language, "en")
        db.close()


class QuestionDifficultyApiTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

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

    def test_starting_difficulty_endpoint_returns_profile(self):
        response = self.client.post("/register", json=user_payload())
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": "learner@example.com", "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]

        db = self.Session()
        assessment = models.Assessment(
            stable_key="assessment",
            title="Assessment",
            version=ASSESSMENT_VERSION,
            is_active=True,
        )
        db.add(assessment)
        db.flush()
        attempt = models.AssessmentAttempt(
            user_id=db.query(models.User).filter(models.User.email == "learner@example.com").first().id,
            assessment_id=assessment.id,
            assessment_version=ASSESSMENT_VERSION,
            preferred_language="en",
            status="submitted",
        )
        db.add(attempt)
        db.flush()
        db.add(
            models.AssessmentResult(
                attempt_id=attempt.id,
                user_id=attempt.user_id,
                assessment_version=ASSESSMENT_VERSION,
                reading_score=96,
                typing_score=68,
                mcq_score=42,
                overall_score=88,
                proficiency_level="advanced",
            )
        )
        db.commit()
        db.close()

        response = self.client.get("/difficulty/me?skill=reading", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["age_group"], "Adult")
        self.assertEqual(data["starting_difficulty"], 5)
        self.assertEqual(data["skill_difficulties"]["reading"], 5)
        self.assertEqual(data["requested_skill"], "reading")


class AdaptiveDifficultyEngineTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _user(self, email="learner@example.com", experience_level="Beginner"):
        user = models.User(
            full_name="Learner One",
            age=20,
            email=email,
            hashed_password="password",
            comfortable_language="en",
            learning_language="hi",
            experience_level=experience_level,
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_three_correct_responses_increase_by_one(self):
        user = self._user()
        state = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "a"}, commit=False)
        state = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "b"}, commit=False)
        state = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "c"}, commit=False)

        self.assertEqual(state["previous_difficulty"], 2)
        self.assertEqual(state["new_difficulty"], 3)
        self.assertTrue(state["adjusted"])
        self.assertEqual(state["reason"], "three_consecutive_correct")

    def test_three_incorrect_responses_decrease_by_one(self):
        user = self._user()
        state_row = models.LearnerSkillDifficulty(
            user_id=user.id,
            skill="reading",
            current_difficulty=3,
            correct_streak=0,
            incorrect_streak=0,
            recent_response_history_json="[]",
            rolling_accuracy=0,
            last_adjustment_reason="starting_difficulty",
        )
        self.db.add(state_row)
        self.db.commit()

        state = evaluate_difficulty(self.db, user.id, "reading", False, {"source": "lesson_practice", "event_id": "d"}, commit=False)
        state = evaluate_difficulty(self.db, user.id, "reading", False, {"source": "lesson_practice", "event_id": "e"}, commit=False)
        state = evaluate_difficulty(self.db, user.id, "reading", False, {"source": "lesson_practice", "event_id": "f"}, commit=False)

        self.assertEqual(state["previous_difficulty"], 3)
        self.assertEqual(state["new_difficulty"], 2)
        self.assertTrue(state["adjusted"])
        self.assertEqual(state["reason"], "three_consecutive_incorrect")

    def test_rolling_window_high_accuracy_increases(self):
        user = self._user()
        pattern = [True, True, False, True, True]
        state = None
        for index, is_correct in enumerate(pattern, start=1):
            state = evaluate_difficulty(
                self.db,
                user.id,
                "reading",
                is_correct,
                {"source": "lesson_practice", "event_id": f"high-{index}"},
                commit=False,
            )

        self.assertEqual(state["new_difficulty"], 3)
        self.assertEqual(state["reason"], "rolling_accuracy_high")
        self.assertAlmostEqual(state["rolling_accuracy"], 0.8, places=2)

    def test_rolling_window_low_accuracy_decreases(self):
        user = self._user()
        state_row = models.LearnerSkillDifficulty(
            user_id=user.id,
            skill="reading",
            current_difficulty=3,
            correct_streak=0,
            incorrect_streak=0,
            recent_response_history_json="[]",
            rolling_accuracy=0,
            last_adjustment_reason="starting_difficulty",
        )
        self.db.add(state_row)
        self.db.commit()
        pattern = [False, False, True, False, False]
        state = None
        for index, is_correct in enumerate(pattern, start=1):
            state = evaluate_difficulty(
                self.db,
                user.id,
                "reading",
                is_correct,
                {"source": "lesson_practice", "event_id": f"low-{index}"},
                commit=False,
            )

        self.assertEqual(state["new_difficulty"], 2)
        self.assertEqual(state["reason"], "rolling_accuracy_low")
        self.assertAlmostEqual(state["rolling_accuracy"], 0.2, places=2)

    def test_middle_accuracy_keeps_level_unchanged(self):
        user = self._user()
        pattern = [True, False, True, False, True]
        state = None
        for index, is_correct in enumerate(pattern, start=1):
            state = evaluate_difficulty(
                self.db,
                user.id,
                "reading",
                is_correct,
                {"source": "lesson_practice", "event_id": f"mid-{index}"},
                commit=False,
            )

        self.assertEqual(state["new_difficulty"], 2)
        self.assertFalse(state["adjusted"])
        self.assertEqual(state["reason"], "maintained")

    def test_no_double_adjustment_on_same_response(self):
        user = self._user()
        state = None
        for index in range(3):
            state = evaluate_difficulty(
                self.db,
                user.id,
                "reading",
                True,
                {"source": "lesson_practice", "event_id": f"double-{index}"},
                commit=False,
            )

        self.assertEqual(state["new_difficulty"], 3)
        self.assertEqual(state["reason"], "three_consecutive_correct")

    def test_bounds_are_respected(self):
        user = self._user(experience_level="Advanced")
        state_row = models.LearnerSkillDifficulty(
            user_id=user.id,
            skill="reading",
            current_difficulty=5,
            correct_streak=2,
            incorrect_streak=0,
            recent_response_history_json="[]",
            rolling_accuracy=1,
            last_adjustment_reason="starting_difficulty",
        )
        self.db.add(state_row)
        self.db.commit()
        state = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "bound-max"}, commit=False)
        self.assertEqual(state["new_difficulty"], 5)
        self.assertEqual(state["reason"], "already_at_max_level")

        user_low = self._user(email="low@example.com")
        low_state_row = models.LearnerSkillDifficulty(
            user_id=user_low.id,
            skill="reading",
            current_difficulty=1,
            correct_streak=0,
            incorrect_streak=2,
            recent_response_history_json="[]",
            rolling_accuracy=0,
            last_adjustment_reason="starting_difficulty",
        )
        self.db.add(low_state_row)
        self.db.commit()
        state = evaluate_difficulty(self.db, user_low.id, "reading", False, {"source": "lesson_practice", "event_id": "bound-min"}, commit=False)
        self.assertEqual(state["new_difficulty"], 1)
        self.assertEqual(state["reason"], "already_at_min_level")

    def test_independent_skill_difficulty(self):
        user = self._user()
        evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "skill-a"}, commit=False)
        evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "skill-b"}, commit=False)
        evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "skill-c"}, commit=False)
        writing_state = evaluate_difficulty(self.db, user.id, "writing", False, {"source": "lesson_practice", "event_id": "skill-d"}, commit=False)

        self.assertEqual(writing_state["previous_difficulty"], 2)
        self.assertEqual(writing_state["new_difficulty"], 2)
        self.assertEqual(writing_state["skill"], "writing")

    def test_duplicate_submission_is_ignored(self):
        user = self._user()
        first = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "dup-1"}, commit=False)
        duplicate = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "dup-1"}, commit=False)

        self.assertTrue(first["adjusted"] is False)
        self.assertEqual(duplicate["reason"], "duplicate_submission")
        self.assertEqual(duplicate["new_difficulty"], first["new_difficulty"])

    def test_missing_history_uses_phase6_starting_difficulty(self):
        user = self._user(experience_level="Intermediate")
        state = evaluate_difficulty(self.db, user.id, "reading", True, {"source": "lesson_practice", "event_id": "start-1"}, commit=False)
        self.assertEqual(state["previous_difficulty"], 3)

    def test_invalid_skill_rejected(self):
        user = self._user()
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            evaluate_difficulty(self.db, user.id, "not-a-skill", True, {"source": "lesson_practice", "event_id": "bad"}, commit=False)


class AdaptiveDifficultyIntegrationTests(unittest.TestCase):
    def setUp(self):
        auth.JWT_SECRET_KEY = "test-secret"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        db = self.Session()
        course = models.Course(
            title="Adaptive Course",
            description="Course",
            skill="reading",
            difficulty_level="beginner",
            language="en",
            proficiency_level="beginner",
        )
        db.add(course)
        db.flush()
        module = models.CourseModule(
            course_id=course.id,
            title="Module",
            description="Module",
            sequence_order=1,
        )
        db.add(module)
        db.flush()
        self.lesson = models.Lesson(
            course_id=course.id,
            module_id=module.id,
            title="Lesson",
            description="Lesson",
            content="Content",
            skill="reading",
            skill_type="reading",
            difficulty_level="beginner",
            proficiency_level="beginner",
            language="en",
            difficulty_order=1,
            estimated_minutes=10,
            estimated_duration_minutes=10,
            sequence_order=1,
        )
        db.add(self.lesson)
        db.flush()
        quiz_block = models.LessonContent(
            lesson_id=self.lesson.id,
            content_type="quiz",
            title="Quiz",
            metadata_json='{"passing_score": 60}',
            sequence_order=1,
        )
        db.add(quiz_block)
        db.flush()
        self.quiz_question = models.LessonQuestion(
            lesson_id=self.lesson.id,
            content_block_id=quiz_block.id,
            question_text="What should you read?",
            question_type="mcq",
            skill="reading",
            difficulty_level="beginner",
            difficulty_rating=1,
            age_group="Child",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            minimum_age=9,
            maximum_age=11,
            correct_answer="this short lesson",
            explanation="The lesson says to read this short lesson.",
            sequence_order=1,
            points=1,
        )
        db.add(self.quiz_question)
        db.flush()
        db.add_all(
            [
                models.QuestionOption(
                    question_id=self.quiz_question.id,
                    option_text="this short lesson",
                    is_correct=True,
                    sequence_order=1,
                ),
                models.QuestionOption(
                    question_id=self.quiz_question.id,
                    option_text="another lesson",
                    is_correct=False,
                    sequence_order=2,
                ),
            ]
        )
        db.commit()
        db.close()

    def tearDown(self):
        app.dependency_overrides.clear()

    def _register_and_token(self):
        response = self.client.post(
            "/register",
            json=user_payload(email="integration@example.com"),
        )
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post("/login", json={"email": "integration@example.com", "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def test_assessment_integration_updates_skill_difficulty(self):
        db = self.Session()
        user = models.User(
            full_name="Learner One",
            age=20,
            email="integration@example.com",
            hashed_password="password",
            comfortable_language="en",
            learning_language="hi",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )
        db.add(user)
        db.flush()
        assessment = models.Assessment(
            stable_key="adaptive-assessment",
            title="Adaptive Assessment",
            version=ASSESSMENT_VERSION,
            is_active=True,
        )
        db.add(assessment)
        db.flush()
        question = models.AssessmentQuestion(
            assessment_id=assessment.id,
            stable_key="adaptive-question",
            assessment_version=ASSESSMENT_VERSION,
            section="mcq",
            language="en",
            difficulty="beginner",
            difficulty_rating=1,
            age_group="Child",
            experience_level="Beginner",
            comfortable_language="en",
            learning_language="en",
            skill="reading",
            question_type="mcq",
            prompt="Prompt",
            marks=2,
            skill_tag="basic comprehension",
            correct_answer_json='{"correct_option_id": "option_1"}',
        )
        db.add(question)
        db.flush()
        attempt = models.AssessmentAttempt(
            user_id=user.id,
            assessment_id=assessment.id,
            assessment_version=ASSESSMENT_VERSION,
            preferred_language="en",
            status="in_progress",
        )
        db.add(attempt)
        db.flush()
        attempt_question = models.AssessmentAttemptQuestion(
            attempt_id=attempt.id,
            question_id=question.id,
            section="mcq",
            display_order=1,
            shuffled_options_json='[{"id":"option_1","text":"correct"},{"id":"option_2","text":"wrong"}]',
            maximum_marks=2,
        )
        db.add(attempt_question)
        db.flush()
        db.add(
            models.AssessmentAnswer(
                attempt_id=attempt.id,
                attempt_question_id=attempt_question.id,
                question_id=question.id,
                answer_json='{"selected_option_id": "option_1"}',
                maximum_marks=2,
            )
        )
        db.commit()
        db.close()

        session = self.Session()
        result = submit_attempt(session, user, attempt.id)
        session.close()
        self.assertEqual(result["proficiency_level"], "beginner")
        lookup = self.Session()
        skill_state = lookup.query(models.LearnerSkillDifficulty).filter(models.LearnerSkillDifficulty.user_id == user.id, models.LearnerSkillDifficulty.skill == "reading").first()
        self.assertIsNotNone(skill_state)
        lookup.close()

    def test_quiz_integration_updates_skill_difficulty_and_duplicate_is_safe(self):
        token = self._register_and_token()
        first = self.client.get(
            f"/lessons/{self.lesson.id}/player",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        question_id = first.json()["questions"][0]["id"]
        payload = {"answers": {str(question_id): "this short lesson"}}

        response = self.client.post(
            f"/lessons/{self.lesson.id}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("difficulty_adjustments", data)

        duplicate = self.client.post(
            f"/lessons/{self.lesson.id}/quiz/submit",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["difficulty_adjustments"], [])




if __name__ == "__main__":
    unittest.main()
