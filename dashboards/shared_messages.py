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
    conn.close()
    return row["mentor_id"] if row else None


def render_student_messages():
    user_id = st.session_state.get("user_id")
    mentor_id = _assigned_mentor(user_id)
    st.subheader("💬 Private chat with your mentor")
    st.caption("Only you and your assigned mentor can see these messages.")
    if not mentor_id:
        st.info("Your mentor chat will appear after a meeting is assigned.")
        return
    messages = list_private_messages(user_id, mentor_id)
    mark_messages_read(user_id, mentor_id)
    for message in messages:
        role = "user" if message["sender_id"] == user_id else "assistant"
        with st.chat_message(role):
            st.write(message["message"])
    message = st.chat_input(
        "Ask a doubt or report an absence/meeting problem...",
        key="student_private_message",
    )
    if message:
        send_private_message(user_id, mentor_id, message)
        st.rerun()


def render_mentor_messages():
    user_id = st.session_state.get("user_id")
    conn = get_connection()
    students = conn.execute(
        "SELECT DISTINCT u.id, u.name, u.email FROM users u "
        "JOIN meetings m ON m.student_id = u.id "
        "WHERE m.mentor_id = ? ORDER BY u.name",
        (user_id,),
    ).fetchall()
    conn.close()
    st.subheader("💬 Private student chats")
    st.caption("Each conversation is visible only to you and that student.")
    if not students:
        st.info("No student conversations are available yet.")
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