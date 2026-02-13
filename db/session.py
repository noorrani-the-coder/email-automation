from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.models import Base

import os
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]

# Check for RDS configuration
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_SSL_CA = os.getenv("DB_SSL_CA")

if DB_HOST:
    # Construct AWS RDS URL
    # Format: mysql+mysqlconnector://user:password@host:port/dbname
    
    # Ensure SSL CA path is absolute if provided
    connect_args = {}
    if DB_SSL_CA:
        if not os.path.isabs(DB_SSL_CA):
            DB_SSL_CA = str(ROOT_DIR / DB_SSL_CA)
        connect_args["ssl_ca"] = DB_SSL_CA
        connect_args["ssl_disabled"] = False

    DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_recycle=3600,
    )
    print(f"Connected to RDS: {DB_HOST}")

else:
    # Fallback to local SQLite
    DB_PATH = ROOT_DIR / "db" / "email_memory.sqlite"
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DATABASE_URL)
    print(f"Connected to local SQLite: {DB_PATH}")

SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """
    Initializes the database by creating all tables.

    Input: None
    Output: None
    """
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def get_session():
    """
    Returns a new database session.

    Input: None
    Output: <Session object>
    """
    return SessionLocal()


def _ensure_columns() -> None:
    """
    Ensures that all required columns exist in the database tables.

    Input: None
    Output: None
    """
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(email_memory)")).fetchall()
        existing = {row[1] for row in rows}
        desired = {
            "priority_label": "TEXT NOT NULL DEFAULT ''",
            "priority_confidence": "REAL NOT NULL DEFAULT 0.0",
            "priority_score": "INTEGER NOT NULL DEFAULT 0",
            "priority_reasons": "TEXT NOT NULL DEFAULT ''",
            "priority_tier": "TEXT NOT NULL DEFAULT ''",
            "decision_timestamp": "TEXT NOT NULL DEFAULT ''",
            "reply_draft": "TEXT NOT NULL DEFAULT ''",
            "reply_timestamp": "TEXT NOT NULL DEFAULT ''",
            "next_action": "TEXT NOT NULL DEFAULT ''",
            "action_reason": "TEXT NOT NULL DEFAULT ''",
            "task_status": "TEXT NOT NULL DEFAULT ''",
            "urgent_flag": "INTEGER NOT NULL DEFAULT 0",
            "needs_human_review": "INTEGER NOT NULL DEFAULT 0",
            "action_timestamp": "TEXT NOT NULL DEFAULT ''",
        }
        for name, ddl in desired.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE email_memory ADD COLUMN {name} {ddl}"))

        behavior_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='behavior_log'")
        ).fetchone()
        if behavior_exists:
            rows = conn.execute(text("PRAGMA table_info(behavior_log)")).fetchall()
            behavior_existing = {row[1] for row in rows}
            behavior_desired = {
                "user_opened": "INTEGER NOT NULL DEFAULT 0",
                "proposed_action": "TEXT NOT NULL DEFAULT ''",
            }
            for name, ddl in behavior_desired.items():
                if name not in behavior_existing:
                    conn.execute(text(f"ALTER TABLE behavior_log ADD COLUMN {name} {ddl}"))
