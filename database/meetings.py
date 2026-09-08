from datetime import datetime

from .connection import get_connection


# ============================================================
# SCHEDULE MEETING
# ============================================================

def save_meeting(
    student_id,
    mentor_id,
    title,
    meeting_date,
    meeting_time,
    meeting_link=""
):
    """Create a scheduled meeting."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO meetings
        (
            student_id,
            mentor_id,
            title,
            meeting_date,
            meeting_time,
            meeting_link,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?)
        """,
        (
            student_id,
            mentor_id,
            title,
            meeting_date,
            meeting_time,
            meeting_link,
            datetime.now().isoformat()
        )
    )

    conn.commit()

    meeting_id = cursor.lastrowid

    conn.close()

    return meeting_id


# ============================================================
# LIST MEETINGS
# ============================================================

def list_meetings(user_id, role="student"):
    """Get meetings belonging to a student or mentor."""

    conn = get_connection()
    cursor = conn.cursor()

    if role == "mentor":

        cursor.execute(
            """
            SELECT *
            FROM meetings
            WHERE mentor_id = ?
            ORDER BY meeting_date, meeting_time
            """,
            (user_id,)
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM meetings
            WHERE student_id = ?
            ORDER BY meeting_date, meeting_time
            """,
            (user_id,)
        )

    meetings = [
        dict(row)
        for row in cursor.fetchall()
    ]

    conn.close()

    return meetings


def update_meeting(meeting_id, title, meeting_date, meeting_time, meeting_link):
    conn = get_connection()
    conn.execute(
        "UPDATE meetings SET title = ?, meeting_date = ?, meeting_time = ?, "
        "meeting_link = ? WHERE id = ?",
        (title.strip(), meeting_date, meeting_time, meeting_link.strip(), meeting_id),
    )
    conn.commit()
    conn.close()


# ============================================================
# GET ONE MEETING
# ============================================================

def get_meeting(meeting_id):
    """Get one meeting by ID."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    )

    meeting = cursor.fetchone()

    conn.close()

    return dict(meeting) if meeting else None


# ============================================================
# MARK MEETING AS JOINED
# ============================================================

def mark_joined(meeting_id):
    """Mark a meeting as joined."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE meetings
        SET status = 'joined'
        WHERE id = ?
        """,
        (meeting_id,)
    )

    conn.commit()

    conn.close()


# ============================================================
# CANCEL MEETING
# ============================================================

def cancel_meeting(meeting_id):
    """Cancel a meeting."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE meetings
        SET status = 'cancelled'
        WHERE id = ?
        """,
        (meeting_id,)
    )

    conn.commit()

    conn.close()


# ============================================================
# SAVE MEETING TRANSCRIPTION
# ============================================================

def save_meeting_transcription(
    user_id,
    transcript,
    summary
):
    """
    Save a meeting transcript and its AI-generated summary.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO meeting_transcriptions
        (
            user_id,
            transcript,
            summary,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            transcript,
            summary,
            datetime.now().isoformat()
        )
    )

    conn.commit()

    transcription_id = cursor.lastrowid

    conn.close()

    return transcription_id