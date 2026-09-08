from datetime import datetime

from .connection import get_connection


def create_notice(title, message):
    """Create a notice."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO notices
        (
            title,
            message,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            title,
            message,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def update_notice(notice_id, title, message):
    conn = get_connection()
    conn.execute(
        "UPDATE notices SET title = ?, message = ? WHERE id = ?",
        (title.strip(), message.strip(), notice_id),
    )
    conn.commit()
    conn.close()


def list_notices(limit=50):
    """Return recent notices."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM notices
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    )

    notices = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return notices


def delete_notice(notice_id):
    """Delete a notice."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM notices
        WHERE id = ?
        """,
        (notice_id,)
    )

    conn.commit()
    conn.close()


def request_deletion(user_id, reason=""):
    """Create an account deletion request."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO deletion_requests
        (
            user_id,
            reason,
            status,
            created_at
        )
        VALUES (?, ?, 'pending', ?)
        """,
        (
            user_id,
            reason,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def list_deletion_requests():
    """List account deletion requests."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            deletion_requests.*,
            users.name,
            users.email
        FROM deletion_requests
        LEFT JOIN users
            ON deletion_requests.user_id = users.id
        ORDER BY deletion_requests.created_at DESC
        """
    )

    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return requests


def update_deletion_request(request_id, status):
    """Update deletion request status."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE deletion_requests
        SET status = ?
        WHERE id = ?
        """,
        (status, request_id)
    )

    conn.commit()
    conn.close()