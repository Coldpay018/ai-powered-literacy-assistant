import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    return database_url


def resolve_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return normalize_database_url(database_url)

    sqlite_path = os.getenv("SQLITE_DATABASE_PATH")
    database_path = Path(sqlite_path).expanduser() if sqlite_path else Path(__file__).resolve().parent / "literacy_learning.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database_path}"


def database_backend(database_url: str) -> str:
    return make_url(database_url).get_backend_name()


def connection_args_for(database_url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if database_backend(database_url) == "sqlite" else {}


def engine_options_for(database_url: str) -> dict[str, object]:
    if database_backend(database_url) == "postgresql":
        return {"pool_pre_ping": True}
    return {}


def install_sqlite_foreign_key_pragma(target_engine: Engine) -> None:
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SQLALCHEMY_DATABASE_URL = resolve_database_url()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connection_args_for(SQLALCHEMY_DATABASE_URL),
    **engine_options_for(SQLALCHEMY_DATABASE_URL),
)

install_sqlite_foreign_key_pragma(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
