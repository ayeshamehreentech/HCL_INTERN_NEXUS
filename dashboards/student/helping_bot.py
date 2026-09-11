import os, re
import requests
import streamlit as st
from groq import Groq
from database.helping_bot import (
    NEW_CHAT_MARKER,
    clear_helping_bot_history,
    is_helping_bot_internal_record,
    latest_helping_bot_memory,
    list_helping_bot_messages,
    save_helping_bot_memory,
    save_helping_bot_message,
    start_helping_bot_chat,
)

def S(name):
    try: return st.secrets.get(name, os.getenv(name, ""))
    except Exception: return os.getenv(name, "")

def conversations(rows):
    """Split the permanent message log into chats at saved new-chat markers."""
    chats, current, has_marker = [], [], False
    for row in rows:
        if str(row.get("content", "")) == NEW_CHAT_MARKER:
            if current:
                chats.append(current)
            current = []
            has_marker = True
        elif not is_helping_bot_internal_record(row) and row.get("role") in {"user", "assistant"}:
            current.append(row)
    if current or has_marker:
        chats.append(current)
    return chats


def chat_label(chat, index, newest_index):
    first_question = next((x.get("content", "") for x in chat if x.get("role") == "user"), "Empty chat")
    when = str(chat[-1].get("created_at", ""))[:16].replace("T", " ") if chat else "New"
    prefix = "Current chat" if index == newest_index else f"Chat {index + 1}"
    return f"{prefix} · {when} · {first_question[:42]}"

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

def A(question, history, temperature, custom_instruction=""):
    key = S("GROQ_API_KEY")
    if not key: return "Your question was saved. Add GROQ_API_KEY to enable AI replies."
    system = "You are a patient internship learning assistant. Teach simply and do not invent facts."
    if custom_instruction.strip():
        system += " Adopt this requested teaching style: " + custom_instruction.strip()[:600]
        system += " Be supportive, but do not claim to be a real parent, mentor, or person."
    messages = [{"role":"system", "content":system}]
    messages += [{"role":x["role"], "content":x["content"]} for x in history[-12:]] + [{"role":"user", "content":question}]
    try: return Groq(api_key=key).chat.completions.create(model=S("GROQ_MODEL") or "openai/gpt-oss-120b", messages=messages, temperature=temperature).choices[0].message.content.strip()
    except Exception: return "I saved your question, but the AI service is temporarily unavailable."

def render_helping_bot_tab():
    user_id = st.session_state.get("user_id")
    st.title("Helping Bot")
    if not user_id:
        st.info("Please sign in again to use Helping Bot."); return
    rows = list_helping_bot_messages(user_id)
    saved_profile = latest_helping_bot_memory(rows, "profile") or {}
    profile_payload = saved_profile.get("payload", {}) if isinstance(saved_profile.get("payload", {}), dict) else {}
    if "helping_bot_temperature" not in st.session_state:
        st.session_state.helping_bot_temperature = float(profile_payload.get("temperature", 0.25))
    if "helping_bot_custom_instruction" not in st.session_state:
        st.session_state.helping_bot_custom_instruction = str(profile_payload.get("instruction", ""))
    chats = conversations(rows)
    if not chats:
        chats = [[]]
    newest_index = len(chats) - 1
    selected_key = "helping_bot_selected_chat"
    if selected_key not in st.session_state or st.session_state[selected_key] >= len(chats):
        st.session_state[selected_key] = newest_index

    chat_area, panel = st.columns([3, 1], gap="large")
    with panel:
        st.subheader("Chat controls")
        if st.button("＋ New chat", use_container_width=True, key="helping_bot_new_chat"):
            if start_helping_bot_chat(user_id):
                st.session_state.pop(selected_key, None)
                st.rerun()
            else:
                st.error("New chat could not be started.")
        labels = [chat_label(chat, i, newest_index) for i, chat in enumerate(chats)]
        selected = st.selectbox("Chat history", range(len(chats)), format_func=lambda i: labels[i], index=st.session_state[selected_key], key="helping_bot_chat_picker")
        st.session_state[selected_key] = selected
        temperature = st.slider("Response temperature", 0.0, 1.0, 0.25, 0.05, key="helping_bot_temperature")
        custom_instruction = st.text_area("Customize the bot", placeholder="Example: Act like a supportive mentor and explain Python with short examples.", max_chars=600, key="helping_bot_custom_instruction")
        if st.button("Save bot personality", use_container_width=True, key="helping_bot_save_profile"):
            if save_helping_bot_memory(user_id, "profile", {"instruction": custom_instruction, "temperature": temperature}):
                st.success("Your bot personality and temperature are permanently saved.")
            else:
                st.error("Bot personalization could not be saved.")
        if st.button("Clear all history", use_container_width=True, key="helping_bot_clear_history"):
            if clear_helping_bot_history(user_id):
                st.session_state.pop(selected_key, None)
                st.rerun()
            else:
                st.error("History could not be cleared.")

        st.subheader("Memory")
        current_chat = chats[selected]
        saved_working = latest_helping_bot_memory(rows, "working") or {}
        saved_summary = latest_helping_bot_memory(rows, "summary") or {}
        working_payload = saved_working.get("payload", {}) if isinstance(saved_working.get("payload", {}), dict) else {}
        saved_working_messages = working_payload.get("messages", [])
        with st.expander("Working memory", expanded=False):
            st.caption("Permanent Supabase snapshot of the last prompt context (up to 6 messages).")
            if saved_working_messages:
                for item in saved_working_messages:
                    st.write(f"**{item.get('role', 'message').title()}:** {str(item.get('content', ''))[:160]}")
                st.caption(f"Saved {str(saved_working.get('saved_at', ''))[:16].replace('T', ' ')} UTC")
            else: st.caption("A permanent snapshot is saved after the first bot answer.")
        with st.expander("Episodic memory", expanded=False):
            st.caption("Past chats saved permanently in Supabase. The bot does not read these unless you open that chat.")
            for i in range(max(0, newest_index - 5), newest_index):
                chat = chats[i]
                st.write(chat_label(chat, i, newest_index))
            if len(chats) <= 1: st.caption("No earlier chats yet.")
        with st.expander("Summary memory", expanded=False):
            st.caption("Permanent Supabase summary saved after each bot answer.")
            summary_payload = saved_summary.get("payload", {}) if isinstance(saved_summary.get("payload", {}), dict) else {}
            if summary_payload:
                st.write(summary_payload.get("text", "No saved summary text."))
                st.caption(f"Saved {str(saved_summary.get('saved_at', ''))[:16].replace('T', ' ')} UTC")
            else: st.caption("A permanent summary is saved after the first bot answer.")

    with chat_area:
        st.caption("Your messages are private to your student account and permanently stored in Supabase.")
        history = chats[selected]
        for x in history:
            with st.chat_message(x["role"]): st.write(x["content"])
        if selected != newest_index:
            st.info("You are viewing a previous chat. Choose Current chat in the right panel to continue asking questions.")
            return
        question = st.chat_input("Ask about Python, weather, or your internship...")
    if question:
        with st.chat_message("user"): st.write(question)
        save_helping_bot_message(user_id, "user", question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = W(question) if any(k in question.lower() for k in ("weather","temperature","forecast","humidity","rain")) else A(question, history, temperature, custom_instruction)
            st.write(answer)
        save_helping_bot_message(user_id, "assistant", answer)
        saved_context = (history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])[-6:]
        save_helping_bot_memory(user_id, "working", {"messages": saved_context})
        summary = (
            f"Current chat: {len(history) + 2} messages. "
            f"Latest student question: {question[:180]}. "
            f"Latest bot response: {answer[:240]}"
        )
        save_helping_bot_memory(user_id, "summary", {"text": summary})
        st.rerun()
