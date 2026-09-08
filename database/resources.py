from datetime import datetime

from .connection import get_connection


def list_resources(topic=None):
    conn = get_connection()
    if topic:
        rows = conn.execute(
            "SELECT * FROM resources WHERE lower(topic) = lower(?) "
            "ORDER BY updated_at DESC",
            (topic.strip(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM resources ORDER BY updated_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_resource(topic, title, url, resource_type, created_by=None):
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO resources "
        "(topic, title, url, resource_type, created_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic.strip(), title.strip(), url.strip(), resource_type, created_by, now, now),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def update_resource(resource_id, topic, title, url, resource_type):
    conn = get_connection()
    conn.execute(
        "UPDATE resources SET topic = ?, title = ?, url = ?, "
        "resource_type = ?, updated_at = ? WHERE id = ?",
        (topic.strip(), title.strip(), url.strip(), resource_type,
         datetime.now().isoformat(), resource_id),
    )
    conn.commit()
    conn.close()


def delete_resource(resource_id):
    conn = get_connection()
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()


def save_topic_history(user_id, topic):
    conn = get_connection()
    conn.execute(
        "INSERT INTO resource_history (user_id, topic, opened_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, topic) DO UPDATE SET opened_at = excluded.opened_at",
        (user_id, topic.strip(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def list_topic_history(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic, opened_at FROM resource_history "
        "WHERE user_id = ? ORDER BY opened_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_user_resource(user_id, resource_key, resource_type, title, url, topic):
    conn = get_connection()
    conn.execute(
        "INSERT INTO user_resources "
        "(user_id, resource_key, resource_type, title, url, topic, saved) "
        "VALUES (?, ?, ?, ?, ?, ?, 1) "
        "ON CONFLICT(user_id, resource_key) DO UPDATE SET saved = 1",
        (user_id, resource_key, resource_type, title, url, topic),
    )
    conn.commit()
    conn.close()


def mark_resource_viewed(user_id, resource_key, resource_type, title, url, topic):
    conn = get_connection()
    conn.execute(
        "INSERT INTO user_resources "
        "(user_id, resource_key, resource_type, title, url, topic, viewed, last_viewed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, ?) "
        "ON CONFLICT(user_id, resource_key) DO UPDATE SET viewed = 1, last_viewed_at = excluded.last_viewed_at",
        (user_id, resource_key, resource_type, title, url, topic, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def list_saved_resources(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM user_resources WHERE user_id = ? AND saved = 1 "
        "ORDER BY last_viewed_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]