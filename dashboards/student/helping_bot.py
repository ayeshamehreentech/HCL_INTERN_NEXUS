"""Student Helping Bot with private, permanent Supabase chat history."""
import os

import streamlit as st
from groq import Groq

from database.helping_bot import (
    clear_helping_bot_history,
    list_helping_bot_messages,
    save_helping_bot_message,
)


def _current_user_id():
    """Read the signed-in student safely from the shared dashboard session."""
    user = st.session_state.get("user") or st.session_state.get("current_user") or {}
    if isinstance(user, dict):
        return user.get("id")
    return getattr(user, "id", None)


def _setting(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def _generate_answer(question, history):
    """Use Groq when configured; otherwise return an honest, safe fallback."""
    api_key = _setting("GROQ_API_KEY")
    model = _setting("GROQ_MODEL", "openai/gpt-oss-120b")
    if not api_key:
        return (
            "Your question has been saved. Add GROQ_API_KEY to Streamlit secrets "
            "to enable AI replies."
        )

    context = [
        {
            "role": "system",
            "content": (
                "You are Helping Bot for an internship learning portal. Teach patiently, "
                "use simple examples, identify misunderstandings, and do not invent facts."
            ),
        }
    ]
    context.extend(
        {"role": item["role"], "content": item["content"]}
        for item in history[-12:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    )
    context.append({"role": "user", "content": question})
    try:
        answer = Groq(api_key=api_key).chat.completions.create(
            model=model,
            messages=context,
            temperature=0.25,
        )
        return answer.choices[0].message.content.strip()
    except Exception:
        return (
            "I saved your question, but the AI service is temporarily unavailable. "
            "Please try again in a moment."
        )


def render_helping_bot_tab():
    """Render a per-student Helping Bot; history never leaves that student's account."""
    user_id = _current_user_id()
    st.title("🤖 Helping Bot")
    st.caption("Ask at any time. Your conversation is private to your student account.")

    if not user_id:
        st.info("Please sign in again to use Helping Bot.")
        return

    history = list_helping_bot_messages(user_id)
    header_col, clear_col = st.columns([5, 1])
    with header_col:
        st.caption(f"{len(history)} messages saved permanently in Supabase.")
    with clear_col:
        if st.button("Clear history", key="clear_helping_history", use_container_width=True):
            if clear_helping_bot_history(user_id):
                st.rerun()
            st.error("History could not be cleared. Please try again.")

    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    question = st.chat_input("Ask for help with Python, your internship, or a concept…")
    if not question:
        return

    with st.chat_message("user"):
        st.write(question)
    save_helping_bot_message(user_id, "user", question)

    with st.chat_message("assistant"):
        with st.spinner("Helping you understand…"):
            answer = _generate_answer(question, history)
        st.write(answer)
    save_helping_bot_message(user_id, "assistant", answer)
    st.rerun()
