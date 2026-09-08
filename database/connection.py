import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "app.db"


def get_connection():
    """Return a SQLite connection that exposes columns by name."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_users_table(conn):
    """Upgrade the early username/password demo schema without deleting data."""
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    required_columns = {
        "name": "TEXT",
        "role": "TEXT DEFAULT 'student'",
        "password_hash": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "start_date": "TEXT",
        "end_date": "TEXT",
        "last_login": "TEXT",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in columns:
            conn.execute(
                f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
            )

    # Preserve data from the original demo schema where possible.
    if "username" in columns:
        conn.execute(
            "UPDATE users SET name = username WHERE name IS NULL OR name = ''"
        )
    if "password" in columns:
        conn.execute(
            "UPDATE users SET password_hash = password "
            "WHERE password_hash IS NULL OR password_hash = ''"
        )

    conn.execute(
        "UPDATE users SET role = 'student' WHERE role IS NULL OR role = ''"
    )
    conn.execute(
        "UPDATE users SET is_active = 1 WHERE is_active IS NULL"
    )


def init_db():
    """Create and safely upgrade the database schema used by the portal."""
    conn = get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            start_date TEXT,
            end_date TEXT,
            last_login TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            seconds INTEGER
        );

        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            mentor_id INTEGER,
            title TEXT NOT NULL,
            meeting_date TEXT,
            meeting_time TEXT,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS meeting_transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            transcript TEXT NOT NULL,
            summary TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learning_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            level TEXT NOT NULL,
            hours_per_day REAL NOT NULL,
            days INTEGER NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learning_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            item TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT 'blog',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resource_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            UNIQUE(user_id, topic)
        );

        CREATE TABLE IF NOT EXISTS formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS student_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            mentor_id INTEGER,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            attachment_name TEXT,
            attachment_data BLOB,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT
        );

        CREATE TABLE IF NOT EXISTS user_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resource_key TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            topic TEXT NOT NULL,
            saved INTEGER NOT NULL DEFAULT 0,
            viewed INTEGER NOT NULL DEFAULT 0,
            last_viewed_at TEXT,
            UNIQUE(user_id, resource_key)
        );
        """
    )

    _migrate_users_table(conn)
    conn.commit()
    conn.close()
