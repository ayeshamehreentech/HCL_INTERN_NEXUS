import json
from datetime import datetime

from .connection import get_connection


def save_learning_plan(
    user_id,
    topic,
    level,
    hours_per_day,
    days,
    plan
):
    """Save an AI-generated learning plan."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO learning_plans
        (
            user_id,
            topic,
            level,
            hours_per_day,
            days,
            plan_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            topic,
            level,
            hours_per_day,
            days,
            json.dumps(plan),
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def get_latest_plan(user_id):
    """Get the latest learning plan for a user."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM learning_plans
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)

    try:
        result["plan"] = json.loads(result["plan_json"])
    except Exception:
        result["plan"] = result["plan_json"]

    return result


def save_checklist(user_id, topic, items):
    """Save checklist items."""

    conn = get_connection()
    cursor = conn.cursor()

    # Remove previous checklist for this topic
    cursor.execute(
        """
        DELETE FROM learning_checklist
        WHERE user_id = ? AND topic = ?
        """,
        (user_id, topic)
    )

    for item in items:
        cursor.execute(
            """
            INSERT INTO learning_checklist
            (
                user_id,
                topic,
                item,
                completed,
                created_at
            )
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                user_id,
                topic,
                item,
                datetime.now().isoformat()
            )
        )

    conn.commit()
    conn.close()


def get_checklist(user_id, topic=None):
    """Get checklist items."""

    conn = get_connection()
    cursor = conn.cursor()

    if topic:
        cursor.execute(
            """
            SELECT *
            FROM learning_checklist
            WHERE user_id = ? AND topic = ?
            ORDER BY id
            """,
            (user_id, topic)
        )
    else:
        cursor.execute(
            """
            SELECT *
            FROM learning_checklist
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,)
        )

    items = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return items


def set_checklist_item(item_id, completed):
    """Mark a checklist item complete/incomplete."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE learning_checklist
        SET completed = ?
        WHERE id = ?
        """,
        (1 if completed else 0, item_id)
    )

    conn.commit()
    conn.close()


def get_learning_progress(user_id):
    """Calculate overall checklist progress."""

    items = get_checklist(user_id)

    if not items:
        return {
            "total": 0,
            "completed": 0,
            "percentage": 0
        }

    completed = sum(
        1 for item in items
        if item["completed"]
    )

    total = len(items)

    return {
        "total": total,
        "completed": completed,
        "percentage": round((completed / total) * 100, 2)
    }