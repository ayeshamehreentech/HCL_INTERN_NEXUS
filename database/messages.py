from datetime import datetime

from .connection import get_connection


def list_private_messages(user_id, other_user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM private_messages WHERE "
        "(sender_id = ? AND recipient_id = ?) OR "
        "(sender_id = ? AND recipient_id = ?) ORDER BY created_at",
        (user_id, other_user_id, other_user_id, user_id),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def send_private_message(sender_id, recipient_id, message):
    conn = get_connection()
    conn.execute(
        "INSERT INTO private_messages "
        "(sender_id, recipient_id, message, created_at) VALUES (?, ?, ?, ?)",
        (sender_id, recipient_id, message.strip(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def count_unread_messages(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM private_messages "
        "WHERE recipient_id = ? AND read_at IS NULL",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["count"]


def mark_messages_read(user_id, sender_id):
    conn = get_connection()
    conn.execute(
        "UPDATE private_messages SET read_at = ? "
        "WHERE recipient_id = ? AND sender_id = ? AND read_at IS NULL",
        (datetime.now().isoformat(), user_id, sender_id),
    )
    conn.commit()
    conn.close()
