"""Student Helping Bot with private, permanent Supabase chat history."""
import os

import streamlit as st
from groq import Groq

from database.helping_bot import clear_helping_bot_history, list_helping_bot_messages, save_helping_bot_message


def _current_user_id():
    """Read the same authenticated ID used by the student dashboard."""
    user_id = st.session_state.get("user_id")
    if user_id:
        return user_id
    user = st.session_state.get("user") or st.session_state.get("current_user") or {}
    return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)


def _setting(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def _generate_answer(question, history):
    api_key = _setting("GROQ_API_KEY")
    if not api_key:
        return "Your question was saved. Add GROQ_API_KEY to Streamlit secrets to enable AI replies."
    messages = [{"role": "system", "content": "You are Helping Bot for an internship learning portal. Teach patiently with simple examples and do not invent facts."}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in history[-12:] if item.get("role") in {"user", "assistant"} and item.get("content"))
    messages.append({"role": "user", "content": question})
    try:
        response = Groq(api_key=api_key).chat.completions.create(model=_setting("GROQ_MODEL", "openai/gpt-oss-120b"), messages=messages, temperature=0.25)
        return response.choices[0].message.content.strip()
    except Exception:
        return "I saved your question, but the AI service is temporarily unavailable. Please try again in a moment."


def render_helping_bot_tab():
    """Render the permanent, private per-student chat."""
    user_id = _current_user_id()
    st.title("🤖 Helping Bot")
    st.caption("Ask at any time. Your conversation is private to your student account.")
    if not user_id:
        st.info("Please sign in again to use Helping Bot.")
        return
    history = list_helping_bot_messages(user_id)
    info_col, clear_col = st.columns([5, 1])
    with info_col:
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
