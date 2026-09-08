import json
from datetime import datetime

from .connection import get_connection


def list_formulas():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM formulas ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_formula(title, content):
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO formulas (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title.strip(), json.dumps(content), now, now),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def update_formula(formula_id, title, content):
    conn = get_connection()
    conn.execute(
        "UPDATE formulas SET title = ?, content = ?, updated_at = ? WHERE id = ?",
        (title.strip(), json.dumps(content), datetime.now().isoformat(), formula_id),
    )
    conn.commit()
    conn.close()


def delete_formula(formula_id):
    conn = get_connection()
    conn.execute("DELETE FROM formulas WHERE id = ?", (formula_id,))
    conn.commit()
    conn.close()