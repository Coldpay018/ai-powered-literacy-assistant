from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _quote_default(value: str) -> str:
    return value.replace("'", "''")


def _column_names(engine: Engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _columns(engine: Engine, table_name: str) -> list[dict]:
    return inspect(engine).get_columns(table_name)


def _table_exists(engine: Engine, table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def _add_column_if_missing(
    engine: Engine,
    table_name: str,
    column_name: str,
    ddl: str,
) -> None:
    if not _table_exists(engine, table_name):
        return
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


def _create_generated_learning_plan_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS learning_plans ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "status VARCHAR(30) NOT NULL DEFAULT 'pending', "
        "comfortable_language VARCHAR(10) NOT NULL, "
        "learning_language VARCHAR(10) NOT NULL, "
        "learner_summary TEXT NOT NULL, "
        "weakest_skills TEXT NOT NULL DEFAULT '[]', "
        "strongest_skills TEXT NOT NULL DEFAULT '[]', "
        "generation_model VARCHAR(100), "
        "generation_version VARCHAR(100) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "generated_at DATETIME, "
        "CONSTRAINT ck_learning_plans_status CHECK (status in ('pending', 'generating', 'ready', 'failed'))"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS generated_courses ("
        "id INTEGER PRIMARY KEY, "
        "learning_plan_id INTEGER NOT NULL REFERENCES learning_plans(id), "
        "title VARCHAR(255) NOT NULL, "
        "description TEXT NOT NULL, "
        "primary_skill VARCHAR(30) NOT NULL, "
        "difficulty INTEGER NOT NULL, "
        "sequence_order INTEGER NOT NULL, "
        "is_unlocked BOOLEAN NOT NULL DEFAULT 0, "
        "completion_status VARCHAR(30) NOT NULL DEFAULT 'not_started', "
        "CONSTRAINT ck_generated_courses_primary_skill CHECK (primary_skill in ('reading', 'writing', 'grammar', 'vocabulary', 'listening', 'speaking', 'comprehension')), "
        "CONSTRAINT ck_generated_courses_difficulty_range CHECK (difficulty >= 1 and difficulty <= 5), "
        "CONSTRAINT ck_generated_courses_sequence_positive CHECK (sequence_order > 0), "
        "CONSTRAINT ck_generated_courses_completion_status CHECK (completion_status in ('not_started', 'in_progress', 'completed')), "
        "CONSTRAINT uq_generated_courses_plan_sequence UNIQUE (learning_plan_id, sequence_order)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS generated_modules ("
        "id INTEGER PRIMARY KEY, "
        "generated_course_id INTEGER NOT NULL REFERENCES generated_courses(id), "
        "title VARCHAR(255) NOT NULL, "
        "description TEXT NOT NULL, "
        "sequence_order INTEGER NOT NULL, "
        "CONSTRAINT ck_generated_modules_sequence_positive CHECK (sequence_order > 0), "
        "CONSTRAINT uq_generated_modules_course_sequence UNIQUE (generated_course_id, sequence_order)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS generated_lesson_plans ("
        "id INTEGER PRIMARY KEY, "
        "generated_module_id INTEGER NOT NULL REFERENCES generated_modules(id), "
        "title VARCHAR(255) NOT NULL, "
        "learning_objective TEXT NOT NULL, "
        "skill VARCHAR(30) NOT NULL, "
        "difficulty INTEGER NOT NULL, "
        "sequence_order INTEGER NOT NULL, "
        "content_status VARCHAR(30) NOT NULL DEFAULT 'not_generated', "
        "CONSTRAINT ck_generated_lesson_plans_skill CHECK (skill in ('reading', 'writing', 'grammar', 'vocabulary', 'listening', 'speaking', 'comprehension')), "
        "CONSTRAINT ck_generated_lesson_plans_difficulty_range CHECK (difficulty >= 1 and difficulty <= 5), "
        "CONSTRAINT ck_generated_lesson_plans_sequence_positive CHECK (sequence_order > 0), "
        "CONSTRAINT ck_generated_lesson_plans_content_status CHECK (content_status in ('not_generated', 'generating', 'ready', 'failed')), "
        "CONSTRAINT uq_generated_lesson_plans_module_sequence UNIQUE (generated_module_id, sequence_order)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_user_id ON learning_plans(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_status ON learning_plans(status)",
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_is_active ON learning_plans(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_user_status ON learning_plans(user_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_user_languages ON learning_plans(user_id, comfortable_language, learning_language)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_plans_user_active ON learning_plans(user_id) WHERE is_active = 1",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_learning_plan_id ON generated_courses(learning_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_primary_skill ON generated_courses(primary_skill)",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_difficulty ON generated_courses(difficulty)",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_is_unlocked ON generated_courses(is_unlocked)",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_completion_status ON generated_courses(completion_status)",
        "CREATE INDEX IF NOT EXISTS ix_generated_courses_plan_order ON generated_courses(learning_plan_id, sequence_order)",
        "CREATE INDEX IF NOT EXISTS ix_generated_modules_generated_course_id ON generated_modules(generated_course_id)",
        "CREATE INDEX IF NOT EXISTS ix_generated_modules_course_order ON generated_modules(generated_course_id, sequence_order)",
        "CREATE INDEX IF NOT EXISTS ix_generated_lesson_plans_generated_module_id ON generated_lesson_plans(generated_module_id)",
        "CREATE INDEX IF NOT EXISTS ix_generated_lesson_plans_skill ON generated_lesson_plans(skill)",
        "CREATE INDEX IF NOT EXISTS ix_generated_lesson_plans_difficulty ON generated_lesson_plans(difficulty)",
        "CREATE INDEX IF NOT EXISTS ix_generated_lesson_plans_content_status ON generated_lesson_plans(content_status)",
        "CREATE INDEX IF NOT EXISTS ix_generated_lesson_plans_module_order ON generated_lesson_plans(generated_module_id, sequence_order)",
    ]:
        _execute(engine, statement)


def _create_gamification_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS xp_transactions ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "amount INTEGER NOT NULL, "
        "source_type VARCHAR(50) NOT NULL, "
        "source_id INTEGER NOT NULL, "
        "reward_key VARCHAR(100) NOT NULL, "
        "description_key VARCHAR(120) NOT NULL, "
        "metadata_json TEXT NOT NULL DEFAULT '{}', "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_xp_transactions_amount_positive CHECK (amount > 0), "
        "CONSTRAINT uq_xp_transaction_reward_once UNIQUE (user_id, source_type, source_id, reward_key)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS gamification_summaries ("
        "user_id INTEGER PRIMARY KEY REFERENCES users(id), "
        "total_xp INTEGER NOT NULL DEFAULT 0, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_gamification_summaries_total_xp_non_negative CHECK (total_xp >= 0)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_user_id ON xp_transactions(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_source_type ON xp_transactions(source_type)",
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_source_id ON xp_transactions(source_id)",
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_reward_key ON xp_transactions(reward_key)",
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_created_at ON xp_transactions(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_xp_transactions_user_created ON xp_transactions(user_id, created_at)",
    ]:
        _execute(engine, statement)


def _create_streak_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS streak_summaries ("
        "user_id INTEGER PRIMARY KEY REFERENCES users(id), "
        "current_streak INTEGER NOT NULL DEFAULT 0, "
        "longest_streak INTEGER NOT NULL DEFAULT 0, "
        "last_activity_date DATE, "
        "streak_started_at DATETIME, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_streak_summaries_current_non_negative CHECK (current_streak >= 0), "
        "CONSTRAINT ck_streak_summaries_longest_non_negative CHECK (longest_streak >= 0)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS daily_streak_activities ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "activity_date DATE NOT NULL, "
        "first_qualified_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "source_type VARCHAR(50) NOT NULL, "
        "source_id INTEGER NOT NULL, "
        "CONSTRAINT uq_daily_streak_activity_user_date UNIQUE (user_id, activity_date)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_daily_streak_activities_user_id ON daily_streak_activities(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_streak_activities_activity_date ON daily_streak_activities(activity_date)",
        "CREATE INDEX IF NOT EXISTS ix_daily_streak_activities_source_type ON daily_streak_activities(source_type)",
        "CREATE INDEX IF NOT EXISTS ix_daily_streak_activities_source_id ON daily_streak_activities(source_id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_streak_activities_user_date ON daily_streak_activities(user_id, activity_date)",
    ]:
        _execute(engine, statement)


def _create_badge_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS badges ("
        "id INTEGER PRIMARY KEY, "
        "badge_key VARCHAR(100) NOT NULL UNIQUE, "
        "name_key VARCHAR(160) NOT NULL, "
        "description_key VARCHAR(160) NOT NULL, "
        "category VARCHAR(50) NOT NULL, "
        "icon_key VARCHAR(50) NOT NULL, "
        "requirement_type VARCHAR(50) NOT NULL, "
        "requirement_value INTEGER NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1, "
        "CONSTRAINT ck_badges_requirement_value_non_negative CHECK (requirement_value >= 0)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS user_badges ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "badge_id INTEGER NOT NULL REFERENCES badges(id), "
        "earned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "source_type VARCHAR(50) NOT NULL, "
        "source_id INTEGER NOT NULL, "
        "CONSTRAINT uq_user_badges_user_badge UNIQUE (user_id, badge_id)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_badges_badge_key ON badges(badge_key)",
        "CREATE INDEX IF NOT EXISTS ix_badges_category ON badges(category)",
        "CREATE INDEX IF NOT EXISTS ix_badges_requirement_type ON badges(requirement_type)",
        "CREATE INDEX IF NOT EXISTS ix_badges_is_active ON badges(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_user_id ON user_badges(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_badge_id ON user_badges(badge_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_earned_at ON user_badges(earned_at)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_source_type ON user_badges(source_type)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_source_id ON user_badges(source_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_badges_user_earned ON user_badges(user_id, earned_at)",
    ]:
        _execute(engine, statement)


def _create_flashcard_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS flashcard_decks ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "lesson_id INTEGER REFERENCES lessons(id), "
        "generated_lesson_plan_id INTEGER REFERENCES generated_lesson_plans(id), "
        "title VARCHAR(255) NOT NULL, "
        "skill VARCHAR(30) NOT NULL, "
        "learning_language VARCHAR(10) NOT NULL, "
        "comfortable_language VARCHAR(10) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_flashcard_decks_skill CHECK (skill in ('reading', 'writing', 'grammar', 'vocabulary', 'listening', 'speaking', 'comprehension')), "
        "CONSTRAINT ck_flashcard_decks_learning_language CHECK (learning_language in ('en', 'hi', 'ta', 'te', 'kn')), "
        "CONSTRAINT ck_flashcard_decks_comfortable_language CHECK (comfortable_language in ('en', 'hi', 'ta', 'te', 'kn')), "
        "CONSTRAINT ck_flashcard_decks_has_source CHECK (lesson_id is not null or generated_lesson_plan_id is not null), "
        "CONSTRAINT uq_flashcard_decks_user_lesson_title UNIQUE (user_id, lesson_id, title), "
        "CONSTRAINT uq_flashcard_decks_user_generated_lesson_title UNIQUE (user_id, generated_lesson_plan_id, title)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS flashcards ("
        "id INTEGER PRIMARY KEY, "
        "deck_id INTEGER NOT NULL REFERENCES flashcard_decks(id), "
        "front_text TEXT NOT NULL, "
        "back_text TEXT NOT NULL, "
        "example_text TEXT, "
        "example_translation TEXT, "
        "pronunciation_text TEXT, "
        "sequence_order INTEGER NOT NULL, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_flashcards_sequence_positive CHECK (sequence_order > 0), "
        "CONSTRAINT uq_flashcards_deck_sequence UNIQUE (deck_id, sequence_order)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS flashcard_progress ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "flashcard_id INTEGER NOT NULL REFERENCES flashcards(id), "
        "review_count INTEGER NOT NULL DEFAULT 0, "
        "correct_count INTEGER NOT NULL DEFAULT 0, "
        "incorrect_count INTEGER NOT NULL DEFAULT 0, "
        "mastery_level INTEGER NOT NULL DEFAULT 0, "
        "review_interval_days INTEGER NOT NULL DEFAULT 1, "
        "next_review_at DATETIME, "
        "last_reviewed_at DATETIME, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT uq_flashcard_progress_user_card UNIQUE (user_id, flashcard_id), "
        "CONSTRAINT ck_flashcard_progress_review_count_non_negative CHECK (review_count >= 0), "
        "CONSTRAINT ck_flashcard_progress_correct_count_non_negative CHECK (correct_count >= 0), "
        "CONSTRAINT ck_flashcard_progress_incorrect_count_non_negative CHECK (incorrect_count >= 0), "
        "CONSTRAINT ck_flashcard_progress_mastery_range CHECK (mastery_level >= 0 and mastery_level <= 5), "
        "CONSTRAINT ck_flashcard_progress_interval_positive CHECK (review_interval_days >= 1)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_user_id ON flashcard_decks(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_lesson_id ON flashcard_decks(lesson_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_generated_lesson_plan_id ON flashcard_decks(generated_lesson_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_skill ON flashcard_decks(skill)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_learning_language ON flashcard_decks(learning_language)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_comfortable_language ON flashcard_decks(comfortable_language)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_is_active ON flashcard_decks(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_decks_user_active ON flashcard_decks(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS ix_flashcards_deck_id ON flashcards(deck_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcards_deck_order ON flashcards(deck_id, sequence_order)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_user_id ON flashcard_progress(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_flashcard_id ON flashcard_progress(flashcard_id)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_mastery_level ON flashcard_progress(mastery_level)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_next_review_at ON flashcard_progress(next_review_at)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_last_reviewed_at ON flashcard_progress(last_reviewed_at)",
        "CREATE INDEX IF NOT EXISTS ix_flashcard_progress_user_next_review ON flashcard_progress(user_id, next_review_at)",
    ]:
        _execute(engine, statement)


def _create_puzzle_tables(engine: Engine) -> None:
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS puzzle_sets ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "lesson_id INTEGER REFERENCES lessons(id), "
        "generated_lesson_plan_id INTEGER REFERENCES generated_lesson_plans(id), "
        "title VARCHAR(255) NOT NULL, "
        "skill VARCHAR(30) NOT NULL, "
        "difficulty INTEGER NOT NULL, "
        "learning_language VARCHAR(10) NOT NULL, "
        "comfortable_language VARCHAR(10) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_puzzle_sets_skill CHECK (skill in ('reading', 'writing', 'grammar', 'vocabulary', 'listening', 'speaking', 'comprehension')), "
        "CONSTRAINT ck_puzzle_sets_difficulty_range CHECK (difficulty >= 1 and difficulty <= 5), "
        "CONSTRAINT ck_puzzle_sets_learning_language CHECK (learning_language in ('en', 'hi', 'ta', 'te', 'kn')), "
        "CONSTRAINT ck_puzzle_sets_comfortable_language CHECK (comfortable_language in ('en', 'hi', 'ta', 'te', 'kn')), "
        "CONSTRAINT ck_puzzle_sets_has_source CHECK (lesson_id is not null or generated_lesson_plan_id is not null), "
        "CONSTRAINT uq_puzzle_sets_user_lesson_title UNIQUE (user_id, lesson_id, title), "
        "CONSTRAINT uq_puzzle_sets_user_generated_lesson_title UNIQUE (user_id, generated_lesson_plan_id, title)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS puzzles ("
        "id INTEGER PRIMARY KEY, "
        "puzzle_set_id INTEGER NOT NULL REFERENCES puzzle_sets(id), "
        "puzzle_type VARCHAR(30) NOT NULL, "
        "instruction_text TEXT NOT NULL, "
        "instruction_translation TEXT, "
        "prompt_text TEXT, "
        "prompt_translation TEXT, "
        "puzzle_data_json TEXT NOT NULL, "
        "answer_data_json TEXT NOT NULL, "
        "sequence_order INTEGER NOT NULL, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT ck_puzzles_type CHECK (puzzle_type in ('jumbled_word', 'matching')), "
        "CONSTRAINT ck_puzzles_sequence_positive CHECK (sequence_order > 0), "
        "CONSTRAINT uq_puzzles_set_sequence UNIQUE (puzzle_set_id, sequence_order)"
        ")",
    )
    _execute(
        engine,
        "CREATE TABLE IF NOT EXISTS puzzle_attempts ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "puzzle_id INTEGER NOT NULL REFERENCES puzzles(id), "
        "submitted_answer_json TEXT NOT NULL, "
        "is_correct BOOLEAN NOT NULL, "
        "score FLOAT NOT NULL DEFAULT 0, "
        "attempt_number INTEGER NOT NULL, "
        "completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT uq_puzzle_attempt_user_puzzle_number UNIQUE (user_id, puzzle_id, attempt_number), "
        "CONSTRAINT ck_puzzle_attempts_score_range CHECK (score >= 0 and score <= 1), "
        "CONSTRAINT ck_puzzle_attempts_number_positive CHECK (attempt_number > 0)"
        ")",
    )

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_user_id ON puzzle_sets(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_lesson_id ON puzzle_sets(lesson_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_generated_lesson_plan_id ON puzzle_sets(generated_lesson_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_skill ON puzzle_sets(skill)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_difficulty ON puzzle_sets(difficulty)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_learning_language ON puzzle_sets(learning_language)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_comfortable_language ON puzzle_sets(comfortable_language)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_is_active ON puzzle_sets(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_sets_user_active ON puzzle_sets(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS ix_puzzles_puzzle_set_id ON puzzles(puzzle_set_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzles_puzzle_type ON puzzles(puzzle_type)",
        "CREATE INDEX IF NOT EXISTS ix_puzzles_set_order ON puzzles(puzzle_set_id, sequence_order)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_user_id ON puzzle_attempts(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_puzzle_id ON puzzle_attempts(puzzle_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_is_correct ON puzzle_attempts(is_correct)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_completed_at ON puzzle_attempts(completed_at)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_user_puzzle ON puzzle_attempts(user_id, puzzle_id)",
        "CREATE INDEX IF NOT EXISTS ix_puzzle_attempts_user_completed ON puzzle_attempts(user_id, completed_at)",
    ]:
        _execute(engine, statement)


def apply_sqlite_schema_updates(engine: Engine) -> None:
    """Apply additive SQLite schema changes for projects without Alembic.

    The current project uses SQLAlchemy `create_all` at startup, which creates
    new tables but does not alter existing tables. This helper fills that gap
    with guarded, additive-only changes for already-created SQLite databases.
    """

    if engine.dialect.name != "sqlite":
        return

    now = _quote_default(datetime.now(timezone.utc).isoformat())
    _create_generated_learning_plan_tables(engine)
    _create_gamification_tables(engine)
    _create_streak_tables(engine)
    _create_badge_tables(engine)
    _create_flashcard_tables(engine)
    _create_puzzle_tables(engine)

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

    _add_column_if_missing(engine, "lesson_attempts", "submission_hash", "submission_hash VARCHAR(128)")
    _add_column_if_missing(engine, "assessment_answers", "submission_hash", "submission_hash VARCHAR(128)")
    _add_column_if_missing(engine, "assessment_results", "final_skill_profile_json", "final_skill_profile_json TEXT")
    _add_column_if_missing(
        engine,
        "assessment_attempt_questions",
        "shuffled_tiles_json",
        "shuffled_tiles_json TEXT",
    )

    if not _table_exists(engine, "learner_skill_difficulties"):
        _execute(
            engine,
            "CREATE TABLE IF NOT EXISTS learner_skill_difficulties ("
            "id INTEGER PRIMARY KEY, "
            "user_id INTEGER NOT NULL REFERENCES users(id), "
            "skill VARCHAR(30) NOT NULL, "
            "current_difficulty INTEGER NOT NULL DEFAULT 1, "
            "correct_streak INTEGER NOT NULL DEFAULT 0, "
            "incorrect_streak INTEGER NOT NULL DEFAULT 0, "
            "recent_response_history_json TEXT NOT NULL DEFAULT '[]', "
            "rolling_accuracy FLOAT NOT NULL DEFAULT 0, "
            "last_adjustment_reason VARCHAR(100), "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "CONSTRAINT uq_learner_skill_difficulty_user_skill UNIQUE (user_id, skill)"
            ")",
        )

    question_columns = {
        "difficulty_rating": "difficulty_rating INTEGER",
        "age_group": "age_group VARCHAR(20)",
        "experience_level": "experience_level VARCHAR(30)",
        "comfortable_language": "comfortable_language VARCHAR(10)",
        "learning_language": "learning_language VARCHAR(10)",
        "skill": "skill VARCHAR(30)",
    }
    if _table_exists(engine, "assessment_questions"):
        for column_name, ddl in question_columns.items():
            _add_column_if_missing(engine, "assessment_questions", column_name, ddl)
    if _table_exists(engine, "lesson_questions"):
        for column_name, ddl in question_columns.items():
            if column_name != "skill":
                _add_column_if_missing(engine, "lesson_questions", column_name, ddl)

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
    if _table_exists(engine, "lesson_attempts"):
        index_statements.append(
            "CREATE INDEX IF NOT EXISTS ix_lesson_attempts_submission_hash ON lesson_attempts(user_id, lesson_id, submission_hash)"
        )
    if _table_exists(engine, "assessment_answers"):
        index_statements.append(
            "CREATE INDEX IF NOT EXISTS ix_assessment_answers_submission_hash ON assessment_answers(attempt_id, attempt_question_id, submission_hash)"
        )
    if _table_exists(engine, "learner_skill_difficulties"):
        index_statements.append(
            "CREATE INDEX IF NOT EXISTS ix_learner_skill_difficulties_user_skill ON learner_skill_difficulties(user_id, skill)"
        )
    if _table_exists(engine, "assessment_questions"):
        index_statements.extend(
            [
                "CREATE INDEX IF NOT EXISTS ix_assessment_questions_difficulty_rating ON assessment_questions(difficulty_rating)",
                "CREATE INDEX IF NOT EXISTS ix_assessment_questions_skill ON assessment_questions(skill)",
                "CREATE INDEX IF NOT EXISTS ix_assessment_questions_age_group ON assessment_questions(age_group)",
                "CREATE INDEX IF NOT EXISTS ix_assessment_questions_experience_level ON assessment_questions(experience_level)",
                "CREATE INDEX IF NOT EXISTS ix_assessment_questions_languages ON assessment_questions(comfortable_language, learning_language)",
            ]
        )
    if _table_exists(engine, "lesson_questions"):
        index_statements.extend(
            [
                "CREATE INDEX IF NOT EXISTS ix_lesson_questions_difficulty_rating ON lesson_questions(difficulty_rating)",
                "CREATE INDEX IF NOT EXISTS ix_lesson_questions_age_group ON lesson_questions(age_group)",
                "CREATE INDEX IF NOT EXISTS ix_lesson_questions_experience_level ON lesson_questions(experience_level)",
                "CREATE INDEX IF NOT EXISTS ix_lesson_questions_languages ON lesson_questions(comfortable_language, learning_language)",
            ]
        )
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

    question_framework_marker = "phase6_question_framework_backfill_v1"
    if _table_exists(engine, "assessment_questions") and _table_exists(engine, "lesson_questions") and not _has_migration_marker(engine, question_framework_marker):
        _execute(
            engine,
            "UPDATE assessment_questions SET "
            "difficulty_rating = CASE "
            "WHEN section = 'reading' AND difficulty = 'beginner' THEN 1 "
            "WHEN section = 'reading' AND difficulty = 'intermediate' THEN 2 "
            "WHEN section = 'reading' AND difficulty = 'advanced' THEN 4 "
            "WHEN section = 'typing' AND difficulty = 'beginner' THEN 2 "
            "WHEN section = 'typing' AND difficulty = 'intermediate' THEN 3 "
            "WHEN section = 'typing' AND difficulty = 'advanced' THEN 5 "
            "WHEN section = 'mcq' AND difficulty = 'beginner' THEN 1 "
            "WHEN section = 'mcq' AND difficulty = 'intermediate' THEN 4 "
            "WHEN section = 'mcq' AND difficulty = 'advanced' THEN 5 "
            "ELSE COALESCE(difficulty_rating, 3) END "
            "WHERE difficulty_rating IS NULL OR difficulty_rating < 1 OR difficulty_rating > 5",
        )
        _execute(
            engine,
            "UPDATE assessment_questions SET "
            "age_group = CASE "
            "WHEN difficulty = 'beginner' THEN 'Child' "
            "WHEN difficulty = 'intermediate' THEN 'Teenager' "
            "WHEN difficulty = 'advanced' THEN 'Adult' "
            "ELSE COALESCE(age_group, 'Teenager') END "
            "WHERE age_group IS NULL OR TRIM(age_group) = ''",
        )
        _execute(
            engine,
            "UPDATE assessment_questions SET "
            "experience_level = CASE "
            "WHEN difficulty = 'beginner' THEN 'Beginner' "
            "WHEN difficulty = 'intermediate' THEN 'Intermediate' "
            "WHEN difficulty = 'advanced' THEN 'Advanced' "
            "ELSE COALESCE(experience_level, 'Beginner') END "
            "WHERE experience_level IS NULL OR TRIM(experience_level) = ''",
        )
        _execute(
            engine,
            "UPDATE assessment_questions SET comfortable_language = language, learning_language = language "
            "WHERE comfortable_language IS NULL OR TRIM(comfortable_language) = '' "
            "OR learning_language IS NULL OR TRIM(learning_language) = ''",
        )
        _execute(
            engine,
            "UPDATE assessment_questions SET skill = CASE "
            "WHEN skill_tag IN ('word recognition', 'literal comprehension', 'passage comprehension') THEN 'reading' "
            "WHEN skill_tag IN ('copy accuracy', 'short response') THEN 'writing' "
            "WHEN skill_tag IN ('sentence completion', 'sentence meaning') THEN 'grammar' "
            "WHEN skill_tag = 'vocabulary' THEN 'vocabulary' "
            "WHEN skill_tag = 'basic comprehension' THEN 'comprehension' "
            "ELSE COALESCE(skill, 'comprehension') END "
            "WHERE skill IS NULL OR TRIM(skill) = ''",
        )
        _execute(
            engine,
            "UPDATE lesson_questions SET "
            "difficulty_rating = CASE "
            "WHEN difficulty_level = 'beginner' THEN 1 "
            "WHEN difficulty_level = 'intermediate' THEN 3 "
            "WHEN difficulty_level = 'advanced' THEN 5 "
            "ELSE COALESCE(difficulty_rating, 2) END "
            "WHERE difficulty_rating IS NULL OR difficulty_rating < 1 OR difficulty_rating > 5",
        )
        _execute(
            engine,
            "UPDATE lesson_questions SET "
            "age_group = CASE "
            "WHEN minimum_age <= 12 THEN 'Child' "
            "WHEN minimum_age <= 17 THEN 'Teenager' "
            "ELSE 'Adult' END "
            "WHERE age_group IS NULL OR TRIM(age_group) = ''",
        )
        _execute(
            engine,
            "UPDATE lesson_questions SET "
            "experience_level = CASE "
            "WHEN difficulty_level = 'beginner' THEN 'Beginner' "
            "WHEN difficulty_level = 'intermediate' THEN 'Intermediate' "
            "WHEN difficulty_level = 'advanced' THEN 'Advanced' "
            "ELSE COALESCE(experience_level, 'Beginner') END "
            "WHERE experience_level IS NULL OR TRIM(experience_level) = ''",
        )
        _execute(
            engine,
            "UPDATE lesson_questions SET comfortable_language = (SELECT language FROM lessons WHERE lessons.id = lesson_questions.lesson_id), "
            "learning_language = (SELECT language FROM lessons WHERE lessons.id = lesson_questions.lesson_id) "
            "WHERE comfortable_language IS NULL OR TRIM(comfortable_language) = '' "
            "OR learning_language IS NULL OR TRIM(learning_language) = ''",
        )
        _mark_migration_applied(engine, question_framework_marker, now)
