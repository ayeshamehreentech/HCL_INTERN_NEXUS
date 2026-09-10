import streamlit as st

from database.connection import get_connection
from database.messages import (
    count_unread_messages,
    list_private_messages,
    mark_messages_read,
    send_private_message,
)


def _assigned_mentor(student_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT mentor_id FROM meetings WHERE student_id = ? "
        "AND mentor_id IS NOT NULL ORDER BY created_at DESC LIMIT 1",
        (student_id,),
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT id FROM users WHERE lower(role) = 'mentor' ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            row = {"mentor_id": row["id"]}
    conn.close()
    return row["mentor_id"] if row else None


def render_student_messages():
    user_id = st.session_state.get("user_id")
    mentor_id = _assigned_mentor(user_id)
    st.subheader("📝 Doubt Clarification with your mentor")
    st.caption("Only you and your assigned mentor can see these clarifications.")
    if not mentor_id:
        st.warning("No mentor account is available yet. Your text box will appear as soon as a mentor is created.")
        return
    messages = list_private_messages(user_id, mentor_id)
    mark_messages_read(user_id, mentor_id)
    for message in messages:
        role = "user" if message["sender_id"] == user_id else "assistant"
        with st.chat_message(role):
            st.write(message["message"])
    message = st.text_area(
        "Ask a doubt to your mentor",
        placeholder=(
            "Write your doubt, absence information, or meeting problem here..."
        ),
        height=120,
        key="student_private_message",
    )
    if st.button(
        "📨 Send doubt to mentor",
        key="send_student_doubt",
        use_container_width=True,
    ):
        if not message.strip():
            st.warning("Write a doubt or message before sending.")
            return
        send_private_message(user_id, mentor_id, message)
        st.success("Your doubt was sent privately to your mentor.")
        st.rerun()


def render_mentor_messages():
    user_id = st.session_state.get("user_id")
    conn = get_connection()
    meeting_rows = conn.execute(
        "SELECT student_id FROM meetings WHERE mentor_id = ?", (user_id,)
    ).fetchall()
    student_ids = {row["student_id"] for row in meeting_rows if row.get("student_id") is not None}
    students = []
    for student_id in student_ids:
        student = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (student_id,)
        ).fetchone()
        if student:
            students.append(student)
    conn.close()
    st.subheader("📝 Student Doubt Clarifications")
    st.caption("Each clarification is visible only to you and that student.")
    if not students:
        st.info("No student doubt clarifications are available yet.")
        return
    selected = st.selectbox(
        "Student conversation",
        [dict(student) for student in students],
        format_func=lambda student: f"{student['name']} · {student['email']}",
        key="mentor_message_student",
    )
    student_id = selected["id"]
    messages = list_private_messages(user_id, student_id)
    mark_messages_read(user_id, student_id)
    for message in messages:
        role = "user" if message["sender_id"] == user_id else "assistant"
        with st.chat_message(role):
            st.write(message["message"])
    message = st.chat_input(
        "Reply to this student...",
        key=f"mentor_private_message_{student_id}",
    )
    if message:
        send_private_message(user_id, student_id, message)
        st.rerun()
