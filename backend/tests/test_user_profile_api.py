import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
import models
from database import Base
from main import app, get_db
from schema_updates import apply_sqlite_schema_updates


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


class UserProfileApiTests(unittest.TestCase):
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

    def tearDown(self):
        app.dependency_overrides.clear()

    def register_and_token(self):
        response = self.client.post("/register", json=user_payload())
        self.assertEqual(response.status_code, 200, response.text)
        login = self.client.post(
            "/login",
            json={"email": "learner@example.com", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def test_successful_registration_with_all_fields(self):
        response = self.client.post("/register", json=user_payload())

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["comfortable_language"], "hi")
        self.assertEqual(data["learning_language"], "en")
        self.assertEqual(data["experience_level"], "Beginner")
        self.assertTrue(data["profile_complete"])
        self.assertNotIn("password", data)
        self.assertNotIn("hashed_password", data)

    def test_missing_comfortable_language_is_rejected(self):
        payload = user_payload()
        del payload["comfortable_language"]

        response = self.client.post("/register", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_missing_learning_language_is_rejected(self):
        payload = user_payload()
        del payload["learning_language"]

        response = self.client.post("/register", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_same_comfortable_and_learning_language_is_rejected(self):
        response = self.client.post(
            "/register",
            json=user_payload(comfortable_language="English", learning_language="en"),
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_experience_level_is_rejected(self):
        response = self.client.post(
            "/register",
            json=user_payload(experience_level="Expert"),
        )

        self.assertEqual(response.status_code, 422)

    def test_successful_profile_update(self):
        token = self.register_and_token()

        response = self.client.patch(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "age": 21,
                "comfortable_language": "Tamil",
                "learning_language": "English",
                "experience_level": "Intermediate",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["age"], 21)
        self.assertEqual(data["comfortable_language"], "ta")
        self.assertEqual(data["learning_language"], "en")
        self.assertEqual(data["experience_level"], "Intermediate")
        self.assertTrue(data["profile_complete"])
        self.assertEqual(data["preferred_language"], "ta")

    def test_invalid_profile_update_is_rejected(self):
        token = self.register_and_token()

        response = self.client.patch(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"learning_language": "Hindi"},
        )

        self.assertEqual(response.status_code, 422)

    def test_profile_response_contains_learner_fields(self):
        token = self.register_and_token()

        response = self.client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["comfortable_language"], "hi")
        self.assertEqual(data["learning_language"], "en")
        self.assertEqual(data["experience_level"], "Beginner")
        self.assertTrue(data["profile_complete"])


class UserProfileMigrationTests(unittest.TestCase):
    def test_existing_preferred_language_is_migrated(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users ("
                    "id INTEGER PRIMARY KEY, full_name VARCHAR(100) NOT NULL, age INTEGER NOT NULL, "
                    "email VARCHAR(255) NOT NULL, hashed_password VARCHAR(255) NOT NULL, "
                    "preferred_language VARCHAR(50) NOT NULL, education_level VARCHAR(100) NOT NULL, "
                    "role VARCHAR(50) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, full_name, age, email, hashed_password, preferred_language, education_level, role, created_at) "
                    "VALUES (1, 'Existing User', 30, 'old@example.com', 'hash', 'hi', 'Primary', 'learner', '2026-01-01')"
                )
            )
            connection.execute(text("CREATE TABLE courses (id INTEGER PRIMARY KEY, proficiency_level VARCHAR(30), is_active BOOLEAN)"))
            connection.execute(
                text(
                    "CREATE TABLE lessons (id INTEGER PRIMARY KEY, skill_type VARCHAR(30), proficiency_level VARCHAR(30), "
                    "estimated_duration_minutes INTEGER, difficulty_order INTEGER, is_active BOOLEAN)"
                )
            )
            connection.execute(text("CREATE TABLE learner_progress (id INTEGER PRIMARY KEY)"))

        apply_sqlite_schema_updates(engine)

        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT preferred_language, comfortable_language, learning_language, experience_level "
                    "FROM users WHERE id = 1"
                )
            ).mappings().first()

        self.assertEqual(row["preferred_language"], "hi")
        self.assertEqual(row["comfortable_language"], "hi")
        self.assertIsNone(row["learning_language"])
        self.assertIsNone(row["experience_level"])

    def test_previous_defaulted_profile_columns_are_corrected(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users ("
                    "id INTEGER PRIMARY KEY, full_name VARCHAR(100) NOT NULL, age INTEGER NOT NULL, "
                    "email VARCHAR(255) NOT NULL, hashed_password VARCHAR(255) NOT NULL, "
                    "comfortable_language VARCHAR(50) NOT NULL DEFAULT 'en', "
                    "learning_language VARCHAR(50) NOT NULL DEFAULT 'hi', "
                    "experience_level VARCHAR(30) NOT NULL DEFAULT 'Beginner', "
                    "preferred_language VARCHAR(50) NOT NULL, education_level VARCHAR(100) NOT NULL, "
                    "role VARCHAR(50) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, full_name, age, email, hashed_password, comfortable_language, "
                    "learning_language, experience_level, preferred_language, education_level, role, created_at) "
                    "VALUES (1, 'Existing User', 30, 'old@example.com', 'hash', 'hi', "
                    "'hi', 'Beginner', 'hi', 'Primary', 'learner', '2026-01-01T00:00:00')"
                )
            )
            connection.execute(text("CREATE TABLE courses (id INTEGER PRIMARY KEY, proficiency_level VARCHAR(30), is_active BOOLEAN)"))
            connection.execute(
                text(
                    "CREATE TABLE lessons (id INTEGER PRIMARY KEY, skill_type VARCHAR(30), proficiency_level VARCHAR(30), "
                    "estimated_duration_minutes INTEGER, difficulty_order INTEGER, is_active BOOLEAN)"
                )
            )
            connection.execute(text("CREATE TABLE learner_progress (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text(
                    "CREATE TABLE schema_migrations "
                    "(name VARCHAR(120) PRIMARY KEY, applied_at DATETIME NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (name, applied_at) "
                    "VALUES ('phase1_learner_profile_fields_v1', '2026-07-10T00:00:00')"
                )
            )

        apply_sqlite_schema_updates(engine)

        columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
        with engine.begin() as connection:
            row = connection.execute(
                text("SELECT comfortable_language, learning_language, experience_level FROM users WHERE id = 1")
            ).mappings().first()

        self.assertTrue(columns["learning_language"]["nullable"])
        self.assertTrue(columns["experience_level"]["nullable"])
        self.assertEqual(row["comfortable_language"], "hi")
        self.assertIsNone(row["learning_language"])
        self.assertIsNone(row["experience_level"])


if __name__ == "__main__":
    unittest.main()
