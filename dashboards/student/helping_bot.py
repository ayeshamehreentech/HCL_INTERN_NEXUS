import os, re
import requests
import streamlit as st
from groq import Groq
from database.helping_bot import NEW_CHAT_MARKER, clear_helping_bot_history, list_helping_bot_messages, save_helping_bot_message, start_helping_bot_chat

def S(name):
    try: return st.secrets.get(name, os.getenv(name, ""))
    except Exception: return os.getenv(name, "")

def H(rows):
    marker = max((i for i, row in enumerate(rows) if row.get("content") == NEW_CHAT_MARKER), default=-1)
    return [row for row in rows[marker + 1:] if row.get("role") in {"user", "assistant"}]

def W(question):
    key = S("WEATHERMAP_API_KEY")
    match = re.search(r"\b(?:in|at)\s+([^?]+)", question, re.I)
    if not key: return "Add WEATHERMAP_API_KEY to Streamlit secrets for live weather."
    if not match: return "Please include a city, for example: weather in Nellore."
    try:
        place = requests.get("https://api.openweathermap.org/geo/1.0/direct", params={"q": match.group(1).strip(), "limit": 1, "appid": key}, timeout=8).json()[0]
        data = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"lat": place["lat"], "lon": place["lon"], "units": "metric", "appid": key}, timeout=8).json()
        main = data["main"]; desc = data["weather"][0]["description"].capitalize()
        return f"**{place['name']}**: {desc}, **{main['temp']} C**, feels like {main['feels_like']} C; humidity {main['humidity']}%."
    except Exception: return "I could not retrieve live weather right now. Please try again shortly."

def A(question, history, temperature):
    key = S("GROQ_API_KEY")
    if not key: return "Your question was saved. Add GROQ_API_KEY to enable AI replies."
    messages = [{"role":"system", "content":"You are a patient internship learning assistant. Teach simply and do not invent facts."}]
    messages += [{"role":x["role"], "content":x["content"]} for x in history[-12:]] + [{"role":"user", "content":question}]
    try: return Groq(api_key=key).chat.completions.create(model=S("GROQ_MODEL") or "openai/gpt-oss-120b", messages=messages, temperature=temperature).choices[0].message.content.strip()
    except Exception: return "I saved your question, but the AI service is temporarily unavailable."

def render_helping_bot_tab():
    user_id = st.session_state.get("user_id")
    st.title("Helping Bot")
    if not user_id:
        st.info("Please sign in again to use Helping Bot."); return
    rows = list_helping_bot_messages(user_id); history = H(rows)
    c1, c2, c3 = st.columns([4,1,1])
    with c1: temperature = st.slider("Response temperature", 0.0, 1.0, 0.25, 0.05, key="helping_bot_temperature")
    with c2:
        st.write("")
        if st.button("New chat", use_container_width=True):
            if start_helping_bot_chat(user_id): st.rerun()
            else: st.error("New chat could not be started.")
    with c3:
        st.write("")
        if st.button("Clear history", use_container_width=True):
            if clear_helping_bot_history(user_id): st.rerun()
            else: st.error("History could not be cleared.")
    with st.expander("Memory and context"):
        st.write(f"{sum(x.get('content') != NEW_CHAT_MARKER for x in rows)} messages are permanently saved in Supabase. This chat has {len(history)} active messages.")
        st.caption("New chat keeps old chats saved but gives the AI fresh context. Weather uses WEATHERMAP_API_KEY.")
    for x in history:
        with st.chat_message(x["role"]): st.write(x["content"])
    question = st.chat_input("Ask about Python, weather, or your internship...")
    if question:
        with st.chat_message("user"): st.write(question)
        save_helping_bot_message(user_id, "user", question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = W(question) if any(k in question.lower() for k in ("weather","temperature","forecast","humidity","rain")) else A(question, history, temperature)
            st.write(answer)
        save_helping_bot_message(user_id, "assistant", answer); st.rerun()
