from datetime import datetime

from .connection import get_connection


def list_reports(student_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, student_id, mentor_id, title, content, attachment_name, "
        "attachment_data, "
        "created_at, updated_at FROM student_reports WHERE student_id = ? "
        "ORDER BY updated_at DESC",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_report(student_id, mentor_id, title, content, attachment_name=None, attachment_data=None):
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO student_reports (student_id, mentor_id, title, content, "
        "attachment_name, attachment_data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, mentor_id, title.strip(), content.strip(), attachment_name,
         attachment_data, now, now),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def get_report(report_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM student_reports WHERE id = ?",
        (report_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None