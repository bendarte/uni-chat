from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.postgres_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
Base = declarative_base()

PROGRAM_SCHEMA_PATCHES = [
    "ALTER TABLE programs ADD COLUMN IF NOT EXISTS study_pace TEXT",
    "CREATE INDEX IF NOT EXISTS idx_programs_city_lower ON programs (lower(city))",
    "CREATE INDEX IF NOT EXISTS idx_programs_level_lower ON programs (lower(level))",
    "CREATE INDEX IF NOT EXISTS idx_programs_language_lower ON programs (lower(language))",
    "CREATE INDEX IF NOT EXISTS idx_programs_study_pace_lower ON programs (lower(study_pace))",
]


def get_db():
    db = SessionLocal()
    try:
        yield db  # type: Session
    finally:
        db.close()


def ensure_program_schema() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "programs" not in inspector.get_table_names():
            return
        for statement in PROGRAM_SCHEMA_PATCHES:
            connection.execute(text(statement))
