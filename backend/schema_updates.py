from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _quote_default(value: str) -> str:
    return value.replace("'", "''")


def _column_names(engine: Engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _columns(engine: Engine, table_name: str) -> list[dict]:
    return inspect(engine).get_columns(table_name)


def _add_column_if_missing(
    engine: Engine,
    table_name: str,
    column_name: str,
    ddl: str,
) -> None:
    if column_name in _column_names(engine, table_name):
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def _execute(engine: Engine, statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


def _has_migration_marker(engine: Engine, marker: str) -> bool:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name VARCHAR(120) PRIMARY KEY, applied_at DATETIME NOT NULL)"
            )
        )
        result = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE name = :name"),
            {"name": marker},
        ).first()
    return result is not None


def _mark_migration_applied(engine: Engine, marker: str, applied_at: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT OR IGNORE INTO schema_migrations (name, applied_at) "
                "VALUES (:name, :applied_at)"
            ),
            {"name": marker, "applied_at": applied_at},
        )


def _migration_applied_at(engine: Engine, marker: str) -> str | None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name VARCHAR(120) PRIMARY KEY, applied_at DATETIME NOT NULL)"
            )
        )
        result = connection.execute(
            text("SELECT applied_at FROM schema_migrations WHERE name = :name"),
            {"name": marker},
        ).first()
    return result[0] if result else None


def _profile_columns_need_nullable_rebuild(engine: Engine) -> bool:
    columns = {column["name"]: column for column in _columns(engine, "users")}
    return any(
        columns.get(column_name) is not None and not columns[column_name].get("nullable", True)
        for column_name in ("comfortable_language", "learning_language", "experience_level")
    )


def _rebuild_users_with_nullable_profile_columns(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.commit()
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    "CREATE TABLE users_profile_nullable ("
                    "id INTEGER PRIMARY KEY, "
                    "full_name VARCHAR(100) NOT NULL, "
                    "age INTEGER NOT NULL, "
                    "email VARCHAR(255) NOT NULL, "
                    "hashed_password VARCHAR(255) NOT NULL, "
                    "comfortable_language VARCHAR(50), "
                    "learning_language VARCHAR(50), "
                    "experience_level VARCHAR(30), "
                    "preferred_language VARCHAR(50) NOT NULL, "
                    "education_level VARCHAR(100) NOT NULL, "
                    "role VARCHAR(50) NOT NULL, "
                    "is_active BOOLEAN NOT NULL DEFAULT 1, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO users_profile_nullable ("
                    "id, full_name, age, email, hashed_password, comfortable_language, "
                    "learning_language, experience_level, preferred_language, education_level, "
                    "role, is_active, created_at"
                    ") "
                    "SELECT id, full_name, age, email, hashed_password, comfortable_language, "
                    "learning_language, experience_level, preferred_language, education_level, "
                    "role, is_active, created_at FROM users"
                )
            )
            connection.execute(text("DROP TABLE users"))
            connection.execute(text("ALTER TABLE users_profile_nullable RENAME TO users"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_id ON users(id)"))
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            connection.execute(text("PRAGMA foreign_keys=ON"))


def apply_sqlite_schema_updates(engine: Engine) -> None:
    """Apply additive SQLite schema changes for projects without Alembic.

    The current project uses SQLAlchemy `create_all` at startup, which creates
    new tables but does not alter existing tables. This helper fills that gap
    with guarded, additive-only changes for already-created SQLite databases.
    """

    if engine.dialect.name != "sqlite":
        return

    now = _quote_default(datetime.now(timezone.utc).isoformat())

    user_columns = {
        "comfortable_language": "comfortable_language VARCHAR(50)",
        "learning_language": "learning_language VARCHAR(50)",
        "experience_level": "experience_level VARCHAR(30)",
    }
    for column_name, ddl in user_columns.items():
        _add_column_if_missing(engine, "users", column_name, ddl)

    if _profile_columns_need_nullable_rebuild(engine):
        _rebuild_users_with_nullable_profile_columns(engine)

    course_columns = {
        "skill": "skill VARCHAR(30) NOT NULL DEFAULT 'reading'",
        "minimum_age": "minimum_age INTEGER NOT NULL DEFAULT 1",
        "maximum_age": "maximum_age INTEGER NOT NULL DEFAULT 120",
        "difficulty_level": "difficulty_level VARCHAR(30) NOT NULL DEFAULT 'beginner'",
        "thumbnail": "thumbnail VARCHAR(500)",
        "is_published": "is_published BOOLEAN NOT NULL DEFAULT 1",
        "updated_at": f"updated_at DATETIME NOT NULL DEFAULT '{now}'",
    }
    for column_name, ddl in course_columns.items():
        _add_column_if_missing(engine, "courses", column_name, ddl)

    lesson_columns = {
        "module_id": "module_id INTEGER REFERENCES modules(id)",
        "skill": "skill VARCHAR(30) NOT NULL DEFAULT 'reading'",
        "difficulty_level": "difficulty_level VARCHAR(30) NOT NULL DEFAULT 'beginner'",
        "estimated_minutes": "estimated_minutes INTEGER NOT NULL DEFAULT 15",
        "sequence_order": "sequence_order INTEGER NOT NULL DEFAULT 1",
        "xp_reward": "xp_reward INTEGER NOT NULL DEFAULT 10",
        "is_published": "is_published BOOLEAN NOT NULL DEFAULT 1",
        "updated_at": f"updated_at DATETIME NOT NULL DEFAULT '{now}'",
    }
    for column_name, ddl in lesson_columns.items():
        _add_column_if_missing(engine, "lessons", column_name, ddl)

    progress_columns = {
        "lesson_id": "lesson_id INTEGER REFERENCES lessons(id)",
        "course_id": "course_id INTEGER REFERENCES courses(id)",
        "module_id": "module_id INTEGER REFERENCES modules(id)",
        "completion_status": "completion_status VARCHAR(30) NOT NULL DEFAULT 'not_started'",
        "last_content_block_id": "last_content_block_id INTEGER REFERENCES lesson_content(id)",
        "questions_attempted": "questions_attempted INTEGER NOT NULL DEFAULT 0",
        "correct_answers": "correct_answers INTEGER NOT NULL DEFAULT 0",
        "incorrect_answers": "incorrect_answers INTEGER NOT NULL DEFAULT 0",
        "current_difficulty": "current_difficulty VARCHAR(30)",
        "score": "score FLOAT NOT NULL DEFAULT 0",
        "best_quiz_score": "best_quiz_score FLOAT",
        "attempt_count": "attempt_count INTEGER NOT NULL DEFAULT 0",
        "time_spent_seconds": "time_spent_seconds INTEGER NOT NULL DEFAULT 0",
        "time_spent": "time_spent INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, ddl in progress_columns.items():
        _add_column_if_missing(engine, "learner_progress", column_name, ddl)

    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_courses_skill ON courses(skill)",
        "CREATE INDEX IF NOT EXISTS ix_courses_difficulty_level ON courses(difficulty_level)",
        "CREATE INDEX IF NOT EXISTS ix_courses_is_published ON courses(is_published)",
        "CREATE INDEX IF NOT EXISTS ix_courses_skill_difficulty_published ON courses(skill, difficulty_level, is_published)",
        "CREATE INDEX IF NOT EXISTS ix_lessons_module_id ON lessons(module_id)",
        "CREATE INDEX IF NOT EXISTS ix_lessons_skill ON lessons(skill)",
        "CREATE INDEX IF NOT EXISTS ix_lessons_difficulty_level ON lessons(difficulty_level)",
        "CREATE INDEX IF NOT EXISTS ix_lessons_is_published ON lessons(is_published)",
        "CREATE INDEX IF NOT EXISTS ix_lessons_module_published_order ON lessons(module_id, is_published, sequence_order)",
        "CREATE INDEX IF NOT EXISTS ix_learner_progress_last_content_block_id ON learner_progress(last_content_block_id)",
    ]
    for statement in index_statements:
        _execute(engine, statement)

    backfill_marker = "phase1_learning_structure_backfill_v1"
    if not _has_migration_marker(engine, backfill_marker):
        _execute(engine, "UPDATE courses SET skill = 'reading' WHERE skill IS NULL")
        _execute(engine, "UPDATE courses SET difficulty_level = proficiency_level WHERE difficulty_level IS NULL OR difficulty_level = 'beginner'")
        _execute(engine, "UPDATE courses SET is_published = is_active WHERE is_published IS NULL")
        _execute(engine, "UPDATE lessons SET skill = skill_type WHERE skill IS NULL OR skill = 'reading'")
        _execute(engine, "UPDATE lessons SET difficulty_level = proficiency_level WHERE difficulty_level IS NULL OR difficulty_level = 'beginner'")
        _execute(engine, "UPDATE lessons SET estimated_minutes = estimated_duration_minutes WHERE estimated_minutes IS NULL OR estimated_minutes = 15")
        _execute(engine, "UPDATE lessons SET sequence_order = difficulty_order WHERE sequence_order IS NULL OR sequence_order = 1")
        _execute(engine, "UPDATE lessons SET is_published = is_active WHERE is_published IS NULL")
        _mark_migration_applied(engine, backfill_marker, now)

    learner_profile_marker = "phase1_learner_profile_fields_v1"
    if not _has_migration_marker(engine, learner_profile_marker):
        _execute(
            engine,
            "UPDATE users SET comfortable_language = preferred_language "
            "WHERE preferred_language IS NOT NULL AND TRIM(preferred_language) != ''",
        )
        _mark_migration_applied(engine, learner_profile_marker, now)

    progress_backfill_marker = "phase4_learner_progress_backfill_v1"
    if not _has_migration_marker(engine, progress_backfill_marker):
        progress_column_names = _column_names(engine, "learner_progress")
        lesson_column_names = _column_names(engine, "lessons")
        table_names = set(inspect(engine).get_table_names())
        if "modules" not in table_names:
            _execute(
                engine,
                "CREATE TABLE IF NOT EXISTS modules ("
                "id INTEGER PRIMARY KEY, "
                "course_id INTEGER REFERENCES courses(id), "
                "title VARCHAR(255) NOT NULL, "
                "description TEXT NOT NULL, "
                "sequence_order INTEGER NOT NULL DEFAULT 1, "
                "is_published BOOLEAN NOT NULL DEFAULT 1, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")",
            )
            table_names.add("modules")
        has_status = "status" in progress_column_names
        has_progress_percentage = "progress_percentage" in progress_column_names
        lesson_has_course_id = "course_id" in lesson_column_names
        lesson_has_module_id = "module_id" in lesson_column_names and "modules" in table_names
        completion_status_expression = (
            "COALESCE(completion_status, status)" if has_status else "COALESCE(completion_status, 'not_started')"
        )
        score_expression = "COALESCE(score, best_quiz_score, progress_percentage, 0)" if has_progress_percentage else "COALESCE(score, best_quiz_score, 0)"
        course_id_expression = "(SELECT course_id FROM lessons WHERE lessons.id = learner_progress.lesson_id)" if lesson_has_course_id else "NULL"
        module_id_expression = "(SELECT module_id FROM lessons WHERE lessons.id = learner_progress.lesson_id)" if lesson_has_module_id else "NULL"
        _execute(
            engine,
            "UPDATE learner_progress SET "
            f"course_id = {course_id_expression}, "
            f"module_id = {module_id_expression}, "
            f"completion_status = {completion_status_expression}, "
            "current_difficulty = (SELECT proficiency_level FROM lessons WHERE lessons.id = learner_progress.lesson_id), "
            f"score = {score_expression}, "
            "time_spent = COALESCE(time_spent, time_spent_seconds, 0), "
            "questions_attempted = COALESCE(questions_attempted, 0), "
            "correct_answers = COALESCE(correct_answers, 0), "
            "incorrect_answers = COALESCE(incorrect_answers, 0) "
            "WHERE lesson_id IS NOT NULL",
        )
        _execute(
            engine,
            "UPDATE learner_progress SET completion_status = 'not_started' "
            "WHERE completion_status IS NULL OR TRIM(completion_status) = ''",
        )
        _mark_migration_applied(engine, progress_backfill_marker, now)

    cleanup_marker = "phase1_learner_profile_remove_invented_defaults_v1"
    if not _has_migration_marker(engine, cleanup_marker):
        learner_profile_applied_at = _migration_applied_at(engine, learner_profile_marker)
        if learner_profile_applied_at:
            _execute(
                engine,
                "UPDATE users SET learning_language = NULL, experience_level = NULL "
                f"WHERE created_at <= '{_quote_default(learner_profile_applied_at)}' "
                "AND learning_language IN ('en', 'hi') "
                "AND experience_level = 'Beginner'",
            )
        _mark_migration_applied(engine, cleanup_marker, now)
