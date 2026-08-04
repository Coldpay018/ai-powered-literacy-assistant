import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateIndex
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models
from database import (
    Base,
    connection_args_for,
    database_backend,
    engine_options_for,
    normalize_database_url,
    resolve_database_url,
)
from main import app
from schema_updates import apply_sqlite_schema_updates


class DatabaseConfigTests(unittest.TestCase):
    def test_database_url_takes_precedence_over_sqlite_path(self):
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://username:password@hostname/database?sslmode=require",
                "SQLITE_DATABASE_PATH": "./ignored.db",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_database_url(),
                "postgresql+psycopg://username:password@hostname/database?sslmode=require",
            )

    def test_plain_postgresql_urls_use_psycopg_driver(self):
        self.assertEqual(
            normalize_database_url("postgresql://username:password@hostname/database?sslmode=require"),
            "postgresql+psycopg://username:password@hostname/database?sslmode=require",
        )
        self.assertEqual(
            normalize_database_url("postgresql+psycopg://username:password@hostname/database?sslmode=require"),
            "postgresql+psycopg://username:password@hostname/database?sslmode=require",
        )

    def test_sqlite_connection_args_are_sqlite_only(self):
        self.assertEqual(connection_args_for("sqlite:///local.db"), {"check_same_thread": False})
        self.assertEqual(connection_args_for("sqlite+pysqlite:///local.db"), {"check_same_thread": False})
        self.assertEqual(
            connection_args_for("postgresql://username:password@hostname/database?sslmode=require"),
            {},
        )

    def test_postgresql_engine_uses_pre_ping_for_stale_connections(self):
        self.assertEqual(engine_options_for("sqlite:///local.db"), {})
        self.assertEqual(
            engine_options_for("postgresql://username:password@hostname/database?sslmode=require"),
            {"pool_pre_ping": True},
        )

    def test_postgresql_url_backend_is_accepted(self):
        self.assertEqual(
            database_backend("postgresql+psycopg://username:password@hostname/database?sslmode=require"),
            "postgresql",
        )

    def test_sqlite_schema_updates_skip_postgresql_engines(self):
        class FakeDialect:
            name = "postgresql"

        class FakeEngine:
            dialect = FakeDialect()

            def begin(self):
                raise AssertionError("PostgreSQL should skip SQLite schema updates")

        apply_sqlite_schema_updates(FakeEngine())

    def test_metadata_initialization_is_idempotent_for_empty_database(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)
        tables = set(inspect(engine).get_table_names())
        self.assertIn("users", tables)
        self.assertIn("offline_sync_events", tables)
        self.assertIn("puzzle_attempts", tables)

    def test_postgresql_partial_active_plan_index_compiles(self):
        index = next(
            index
            for index in models.LearningPlan.__table__.indexes
            if index.name == "uq_learning_plans_user_active"
        )
        compiled = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        self.assertIn("WHERE is_active = true", compiled)

    def test_rollback_after_duplicate_constraint_allows_next_transaction(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_updates(engine)
        Session = sessionmaker(bind=engine)

        db = Session()
        try:
            db.add(self._user("same@example.com"))
            db.commit()
            db.add(self._user("same@example.com"))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            db.add(self._user("different@example.com"))
            db.commit()
            self.assertEqual(db.query(models.User).count(), 2)
        finally:
            db.close()

    def test_health_does_not_expose_database_credentials(self):
        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://username:secret-password@hostname/database?sslmode=require"},
            clear=False,
        ):
            response = TestClient(app).get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("healthy", body)
        self.assertNotIn("secret-password", body)
        self.assertNotIn("postgresql://", body)

    def _user(self, email):
        return models.User(
            full_name="Database Tester",
            age=20,
            email=email,
            hashed_password="hashed",
            comfortable_language="en",
            learning_language="hi",
            experience_level="Beginner",
            preferred_language="en",
            education_level="Primary",
            role="learner",
            is_active=True,
        )


if __name__ == "__main__":
    unittest.main()
