from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]

# Environment variables
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_SSL_CA = os.getenv("DB_SSL_CA")

# Create engine (same logic as your main config)
if DB_HOST:
    connect_args = {}
    if DB_SSL_CA:
        if not os.path.isabs(DB_SSL_CA):
            DB_SSL_CA = str(ROOT_DIR / DB_SSL_CA)
        connect_args["ssl_ca"] = DB_SSL_CA
        connect_args["ssl_disabled"] = False

    DATABASE_URL = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    print(f"Connected to MySQL/RDS: {DB_HOST}")

else:
    DB_PATH = ROOT_DIR / "db" / "email_memory.sqlite"
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DATABASE_URL)
    print(f"Connected to SQLite: {DB_PATH}")


def drop_all_tables():
    with engine.begin() as conn:

        if engine.dialect.name == "sqlite":
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()

            for (table_name,) in tables:
                if table_name != "sqlite_sequence":
                    print(f"Dropping table: {table_name}")
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))

        elif engine.dialect.name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            tables = conn.execute(text("SHOW TABLES;")).fetchall()

            for (table_name,) in tables:
                print(f"Dropping table: {table_name}")
                conn.execute(text(f"DROP TABLE `{table_name}`;"))

            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

        else:
            raise RuntimeError("Unsupported database type")

    print("✅ All tables dropped successfully.")


if __name__ == "__main__":
    confirm = input(
        "⚠️  This will DELETE ALL TABLES. Type 'yes' to continue: "
    )

    if confirm.lower() == "yes":
        drop_all_tables()
    else:
        print("Operation cancelled.")
