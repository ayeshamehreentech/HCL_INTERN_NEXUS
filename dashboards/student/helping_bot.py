import os
import re
import sqlite3
import tempfile
import uuid
import math
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ============================================================
# 1. ENVIRONMENT & CONFIGS
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHERMAP_API_KEY = os.getenv("WEATHERMAP_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
DB_PATH = "agent_memory.db"

# Memory types used by the Helping Bot. The main memory types are also
# visible to the student inside Settings for transparency and control.
MEMORY_TYPES = {
    "sensory": "Temporary raw observations",
    "recent_messages": "Recent conversation messages",
    "working": "Current task and active reasoning context",
    "working_window": "Small active context window",
    "short_term": "Temporary information from current session",
    "summary": "Compressed older conversation",
    "episodic": "Important past events and experiences",
    "semantic": "Stable facts and knowledge",
    "procedural": "How tasks/workflows should be performed",
    "profile": "Stable user profile information",
    "preference": "User preferences and choices",
    "entity": "People, projects, technologies and relationships",
    "landmark": "Important milestones or significant events",
    "prospective": "Things intended to happen later",
    "hierarchical": "Parent-child memory relationships",
    "shared": "Memory reusable across conversations",
    "asymmetric": "Importance-weighted long-lasting memory",
}


# ============================================================
# 2. DATABASE UTILITIES
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            importance REAL DEFAULT 0.5,
            strength REAL DEFAULT 0.5,
            confidence REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed TEXT,
            expires_at TEXT,
            parent_id INTEGER,
            source TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(parent_id) REFERENCES memories(memory_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_memory_id INTEGER,
            target_memory_id INTEGER,
            relationship TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_preferences (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            custom_prompt TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# 3. CHAT & MESSAGE FUNCTIONS
# ============================================================

def create_chat(title="New Chat"):
    chat_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "INSERT INTO chats (chat_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (chat_id, title, now, now)
    )
    conn.commit()
    conn.close()
    return chat_id


def load_chats():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()
    conn.close()
    return rows


def update_chat_title(chat_id, title):
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE chat_id = ?",
        (title, now, chat_id)
    )
    conn.commit()
    conn.close()


def delete_all_chats():
    conn = get_connection()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM chats")
    conn.commit()
    conn.close()


def save_message(chat_id, role, content):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, now)
    )
    conn.execute(
        "UPDATE chats SET updated_at = ? WHERE chat_id = ?",
        (now, chat_id)
    )
    conn.commit()
    conn.close()


def load_messages(chat_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE chat_id = ? ORDER BY message_id ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


# ============================================================
# 4. CUSTOMIZE YOUR BOT
# ============================================================

def get_custom_bot_prompt():
    conn = get_connection()
    row = conn.execute(
        "SELECT custom_prompt FROM bot_preferences WHERE id = 1"
    ).fetchone()
    conn.close()
    return row["custom_prompt"] if row else ""


def save_custom_bot_prompt(prompt):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute("""
        INSERT INTO bot_preferences (id, custom_prompt, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            custom_prompt = excluded.custom_prompt,
            updated_at = excluded.updated_at
    """, (prompt.strip(), now))
    conn.commit()
    conn.close()


# ============================================================
# 5. MEMORY MANAGEMENT
# ============================================================

def create_memory(memory_type, content, chat_id=None, category=None, importance=0.5, confidence=0.7, source="agent", parent_id=None):
    if not content:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO memories 
        (chat_id, memory_type, content, category, importance, strength, confidence, access_count, created_at, updated_at, last_accessed, source, parent_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1)
    """, (chat_id, memory_type, content.strip(), category, importance, importance, confidence, now, now, now, source, parent_id))
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return memory_id


def get_memories(memory_type=None, chat_id=None, limit=100):
    conn = get_connection()
    if memory_type:
        rows = conn.execute(
            "SELECT * FROM memories WHERE memory_type = ? AND is_active = 1 ORDER BY importance DESC, strength DESC, updated_at DESC LIMIT ?",
            (memory_type, limit)
        ).fetchall()
    elif chat_id:
        rows = conn.execute(
            "SELECT * FROM memories WHERE (chat_id = ? OR memory_type = 'shared') AND is_active = 1 ORDER BY importance DESC, strength DESC, updated_at DESC LIMIT ?",
            (chat_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE is_active = 1 ORDER BY importance DESC, strength DESC, updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return rows


def search_memories(query, limit=8):
    words = [word.lower() for word in re.findall(r"\b\w+\b", query) if len(word) > 2]
    memories = get_memories(limit=300)
    scored = []
    for memory in memories:
        content = memory["content"].lower()
        score = sum(1 for word in words if word in content)
        score += memory["importance"] * 2 + memory["strength"]
        if score > 0:
            scored.append((score, memory))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [memory for _, memory in scored[:limit]]


def access_memory(memory_id):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute("""
        UPDATE memories
        SET access_count = access_count + 1, last_accessed = ?, strength = MIN(1.0, strength + 0.03), updated_at = ?
        WHERE memory_id = ?
    """, (now, now, memory_id))
    conn.commit()
    conn.close()


def calculate_memory_strength(memory):
    try:
        importance = float(memory["importance"] or 0)
        strength = float(memory["strength"] or 0)
        confidence = float(memory["confidence"] or 0)
        accesses = int(memory["access_count"] or 0)
        created = datetime.fromisoformat(memory["created_at"])
        days_old = max(0, (datetime.now() - created).days)
        decay = math.exp(-0.015 * days_old)
        reinforcement = min(1.0, accesses / 10)
        score = (importance * 0.35 + strength * 0.25 + confidence * 0.20 + reinforcement * 0.20) * decay
        return round(min(1.0, max(0.0, score)), 3)
    except Exception:
        return 0.0


def get_strongest_memories(limit=10):
    memories = get_memories(limit=500)
    ranked = [(calculate_memory_strength(m), m) for m in memories]
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [{"score": score, "memory": memory} for score, memory in ranked[:limit]]


def delete_memory(memory_id):
    conn = get_connection()
    conn.execute("UPDATE memories SET is_active = 0 WHERE memory_id = ?", (memory_id,))
    conn.commit()
    conn.close()


def create_chat_title(question):
    question = question.strip()
    if not question:
        return "New Chat"
    text = re.sub(r"^(what is|what are|please|can you|could you|tell me|give me)\s+", "", question, flags=re.IGNORECASE)
    words = text.split()
    if len(words) > 7:
        text = " ".join(words[:7]) + "..."
    return text.capitalize() if text else "New Chat"


# ============================================================
# 6. LLM EXTRACTION & SUMMARY HELPERS
# ============================================================

def extract_memories(client, user_query, assistant_answer):
    prompt = f"""
You are a memory extraction system.
USER: {user_query}
ASSISTANT: {assistant_answer}
Identify ONLY information that may be useful for future interactions.
Return JSON-like lines in this exact format:
TYPE | CONTENT | IMPORTANCE | CONFIDENCE
Allowed TYPE values: profile, preference, semantic, episodic, procedural, entity, landmark, prospective, hierarchical, shared, asymmetric, working, short_term
If there is nothing worth remembering, return: NONE
"""
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception:
        return "NONE"


def store_extracted_memories(extracted, chat_id):
    if not extracted:
        return
    for line in extracted.splitlines():
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            continue
        memory_type, content = parts[0].lower(), parts[1]
        if memory_type not in MEMORY_TYPES:
            continue
        try:
            importance = min(1.0, max(0.0, float(parts[2])))
            confidence = min(1.0, max(0.0, float(parts[3])))
        except Exception:
            importance, confidence = 0.5, 0.5

        create_memory(
            memory_type=memory_type, content=content, chat_id=chat_id,
            importance=importance, confidence=confidence, source="conversation"
        )


def create_recent_message_memory(chat_id, role, content):
    create_memory(
        memory_type="recent_messages", content=f"{role}: {content}",
        chat_id=chat_id, importance=0.35, confidence=1.0, source="conversation"
    )


def refresh_working_window_memory(chat_id, window_size=8):
    """Keep one visible working-window snapshot for the current chat."""
    messages = load_messages(chat_id)[-window_size:]
    if not messages:
        return

    snapshot = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    conn = get_connection()
    conn.execute(
        "UPDATE memories SET is_active = 0 WHERE chat_id = ? AND memory_type = 'working_window' AND is_active = 1",
        (chat_id,)
    )
    conn.commit()
    conn.close()

    create_memory(
        memory_type="working_window",
        content=snapshot,
        chat_id=chat_id,
        importance=0.6,
        confidence=1.0,
        source="conversation_window"
    )


def get_summary(chat_id):
    conn = get_connection()
    row = conn.execute("SELECT summary FROM memory_summaries WHERE chat_id = ? ORDER BY updated_at DESC LIMIT 1", (chat_id,)).fetchone()
    conn.close()
    return row["summary"] if row else ""


def save_summary(chat_id, summary):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute("INSERT INTO memory_summaries (chat_id, summary, created_at, updated_at) VALUES (?, ?, ?, ?)", (chat_id, summary, now, now))
    conn.commit()
    conn.close()


def generate_memory_summary(client, messages):
    if not messages:
        return ""
    conversation = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-20:])
    prompt = f"Summarize this conversation for future AI memory:\n{conversation}\nReturn a concise memory summary."
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception:
        return ""


def build_memory_context(query, chat_id):
    memories = search_memories(query, limit=10)
    context_parts = []

    working = get_memories(memory_type="working", limit=3)
    if working:
        context_parts.append("WORKING MEMORY:\n" + "\n".join(m["content"] for m in working))

    preferences = get_memories(memory_type="preference", limit=5)
    if preferences:
        context_parts.append("USER PREFERENCES:\n" + "\n".join(m["content"] for m in preferences))

    profiles = get_memories(memory_type="profile", limit=5)
    if profiles:
        context_parts.append("USER PROFILE:\n" + "\n".join(m["content"] for m in profiles))

    if memories:
        context_parts.append("RELEVANT LONG-TERM MEMORY:\n" + "\n".join(f"- {m['memory_type']}: {m['content']}" for m in memories))
        for memory in memories:
            access_memory(memory["memory_id"])

    summary = get_summary(chat_id)
    if summary:
        context_parts.append("CONVERSATION SUMMARY:\n" + summary)

    return "\n\n".join(context_parts)


# ============================================================
# 7. EXTERNAL TOOLS (WEATHER, WEB SEARCH, RAG)
# ============================================================

def extract_locations(query):
    query = query.strip()
    patterns = [
        r"\bweather\s+(?:in|at|for)\s+(.+)",
        r"\btemperature\s+(?:in|at|of|for)\s+(.+)",
        r"\btemp\s+(?:in|at|of|for)\s+(.+)",
        r"\bconditions?\s+(?:in|at|for)\s+(.+)",
        r"\b(?:weather|temperature|temp)\s+of\s+(.+)"
    ]
    location_text = None
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            location_text = match.group(1)
            break
    if not location_text:
        return []
    location_text = re.sub(r"[?.!]+$", "", location_text)
    location_text = re.sub(r"\b(today|now|currently|please|right now)\b", "", location_text, flags=re.IGNORECASE)
    parts = re.split(r"\s+(?:and|&)\s+|,\s*", location_text, flags=re.IGNORECASE)
    return [part.strip().title() for part in parts if part.strip()]


def get_single_weather(location):
    if not WEATHERMAP_API_KEY:
        return "WEATHERMAP_API_KEY is missing."
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": location, "appid": WEATHERMAP_API_KEY, "units": "metric"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return f"Could not retrieve weather for {location}."
        data = response.json()
        city = data.get("name", location)
        country = data.get("sys", {}).get("country", "")
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        return f"📍 {city}, {country}\n🌡️ Temperature: {temp:.1f}°C\n☁️ Condition: {desc.title()}"
    except Exception as e:
        return f"Weather error for {location}: {str(e)}"


def get_weather(query):
    locations = extract_locations(query)
    if not locations:
        return "I could not identify a city."
    return "\n\n".join(get_single_weather(loc) for loc in locations)


def search_web(query):
    try:
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as e:
        return f"Web search error: {str(e)}"


@st.cache_resource(show_spinner="Processing PDF...")
def setup_rag_db(file_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name
    try:
        loader = PyPDFLoader(temp_path)
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split_documents(documents)
        try:
            from langchain_community.embeddings import FastEmbedEmbeddings

            embeddings = FastEmbedEmbeddings()
        except ImportError as error:
            raise RuntimeError(
                "PDF search needs the optional fastembed package. "
                "Install it with `pip install fastembed` and restart Streamlit."
            ) from error
        vector_db = FAISS.from_documents(chunks, embeddings)
        return vector_db, len(chunks)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def retrieve_from_pdf(vector_db, query):
    try:
        documents = vector_db.similarity_search(query, k=5)
        if not documents:
            return "No relevant information was found in the PDF."
        return "\n\n".join(doc.page_content for doc in documents)
    except Exception as e:
        return f"RAG retrieval error: {str(e)}"


def route_query(client, query, has_document):
    rag_instruction = "If the question is about the uploaded PDF, ALWAYS select RAG." if has_document else ""
    prompt = f"""
Choose exactly ONE: WEATHER, RAG, WEB_SEARCH
{rag_instruction}
User query: {query}
Return ONLY WEATHER, RAG, or WEB_SEARCH
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    decision = response.choices[0].message.content.strip().upper()
    if decision == "WEATHER":
        return "WEATHER"
    if decision == "RAG" and has_document:
        return "RAG"
    return "WEB_SEARCH"


def generate_answer(
    client,
    query,
    tool_result,
    memory_context,
    chat_history,
    temperature=0.2,
    custom_prompt=""
):
    custom_instruction = custom_prompt.strip() if custom_prompt.strip() else (
        "Answer naturally, clearly, and helpfully."
    )

    prompt = f"""
You are a helpful AI agent with memory.

CUSTOM BOT INSTRUCTIONS:
{custom_instruction}

MEMORY CONTEXT:
{memory_context}

RECENT CONVERSATION:
{chat_history}

CURRENT QUESTION:
{query}

TOOL RESULT:
{tool_result}

Follow the user's custom bot instructions when they do not conflict with system,
safety, or factual requirements.
Answer naturally.
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content


def submit_helping_bot_query():
    """Capture and clear the query before the next widget render."""
    st.session_state["helping_bot_submitted_query"] = st.session_state.get(
        "helping_bot_query",
        "",
    ).strip()
    st.session_state["helping_bot_query"] = ""


# ============================================================
# 8. MAIN RENDER FUNCTION FOR APP IMPORT
# ============================================================

def render_helping_bot_tab():
    """Call this function inside your test.py tab to display the Helping Bot."""

    # Session state setup
    if "active_chat_id" not in st.session_state:
        chats = load_chats()
        st.session_state.active_chat_id = chats[0]["chat_id"] if chats else create_chat()

    st.title("🧠 Helping Bot (AI Agent With Memory)")
    st.caption("Memory + RAG + Weather + Web Search")

    # Main Tabs
    chat_tab, settings_tab = st.tabs(["💬 Agent", "⚙️ Settings"])

    # Sidebar parameters inside the tab container context
    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Agent Controls")
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1)

        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.active_chat_id = create_chat()
            st.rerun()

        st.subheader("Recent Chats")
        for index, chat in enumerate(load_chats(), start=1):
            chat_id = chat["chat_id"]
            title = chat["title"]
            label = f"🔵 {index}. {title}" if chat_id == st.session_state.active_chat_id else f"{index}. {title}"
            if st.button(label, key=f"chat_{chat_id}", use_container_width=True):
                st.session_state.active_chat_id = chat_id
                st.rerun()

        if st.button("🗑️ Clear All Chats", use_container_width=True):
            delete_all_chats()
            st.session_state.active_chat_id = create_chat()
            st.rerun()

        st.markdown("---")
        st.caption("PDF RAG is available from the ➕ button beside the query box.")

    vector_db = st.session_state.get("rag_vector_db")
    chunk_count = st.session_state.get("rag_chunk_count", 0)

    if vector_db is not None:
        st.caption(f"📄 PDF RAG ready ({chunk_count} chunks)")

    # --- AGENT TAB ---
    with chat_tab:
        current_chat_id = st.session_state.active_chat_id
        current_messages = load_messages(current_chat_id)
        chats = load_chats()
        current_title = next((c["title"] for c in chats if c["chat_id"] == current_chat_id), "New Chat")

        if current_title != "New Chat":
            st.subheader(f"💬 {current_title}")

        for message in current_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        query_col, plus_col = st.columns([9, 1])

        with query_col:
            user_query = st.text_input(
                "Ask me anything...",
                key="helping_bot_query",
                on_change=submit_helping_bot_query,
                label_visibility="collapsed",
                placeholder="Ask me anything..."
            )

        user_query = st.session_state.pop(
            "helping_bot_submitted_query",
            "",
        ) or user_query

        with plus_col:
            plus_clicked = st.button(
                "＋",
                key="rag_plus_button",
                help="Upload a PDF for RAG",
                use_container_width=True
            )

        if plus_clicked:
            st.session_state["show_rag_uploader"] = True

        if st.session_state.get("show_rag_uploader", False):
            uploaded_file = st.file_uploader(
                "Upload file for RAG",
                type=["pdf"],
                key="rag_upload"
            )

            if uploaded_file is not None:
                try:
                    with st.spinner("Processing PDF..."):
                        rag_db, chunks = setup_rag_db(uploaded_file.getvalue())

                    st.session_state["rag_vector_db"] = rag_db
                    st.session_state["rag_chunk_count"] = chunks
                    st.session_state["rag_file_name"] = uploaded_file.name

                    st.success(
                        f"📄 {uploaded_file.name} is ready for RAG ({chunks} chunks)."
                    )
                except Exception as e:
                    st.error(f"Could not process the PDF: {e}")

        if user_query:
            if not GROQ_API_KEY:
                st.error("GROQ_API_KEY is missing from .env")
                st.stop()

            client = Groq(api_key=GROQ_API_KEY)

            if current_title == "New Chat" and len(current_messages) == 0:
                update_chat_title(current_chat_id, create_chat_title(user_query))

            save_message(current_chat_id, "user", user_query)
            create_recent_message_memory(current_chat_id, "user", user_query)
            refresh_working_window_memory(current_chat_id)
            create_memory(memory_type="sensory", content=user_query, chat_id=current_chat_id, importance=0.2, confidence=1.0, source="current_input")
            create_memory(memory_type="working", content=f"Current task: {user_query}", chat_id=current_chat_id, importance=0.65, confidence=0.8, source="current_task")

            previous_messages = load_messages(current_chat_id)[:-1]
            recent = previous_messages[-8:]
            chat_history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)

            memory_context = build_memory_context(user_query, current_chat_id)

            with st.chat_message("user"):
                st.write(user_query)

            with st.chat_message("assistant"):
                with st.spinner("🧠 Thinking and routing..."):
                    route = route_query(client, user_query, st.session_state.get("rag_vector_db") is not None)

                st.info(f"🔧 Selected tool: **{route}**")

                with st.spinner("Executing tool..."):
                    if route == "WEATHER":
                        tool_result = get_weather(user_query)
                    elif route == "RAG":
                        tool_result = retrieve_from_pdf(st.session_state.get("rag_vector_db"), user_query) if st.session_state.get("rag_vector_db") else "No PDF uploaded."
                    else:
                        tool_result = search_web(user_query)

                with st.expander("🔍 View Tool Context"):
                    st.write(tool_result)

                with st.expander("🧠 View Retrieved Memory"):
                    st.write(memory_context if memory_context else "No relevant memory.")

                with st.spinner("Generating answer..."):
                    final_answer = generate_answer(
                        client,
                        user_query,
                        tool_result,
                        memory_context,
                        chat_history,
                        temperature,
                        get_custom_bot_prompt()
                    )

                st.write(final_answer)

            save_message(current_chat_id, "assistant", final_answer)
            create_recent_message_memory(current_chat_id, "assistant", final_answer)
            refresh_working_window_memory(current_chat_id)

            with st.spinner("🧠 Updating long-term memory..."):
                extracted = extract_memories(client, user_query, final_answer)
                store_extracted_memories(extracted, current_chat_id)

            all_messages = load_messages(current_chat_id)
            if len(all_messages) >= 10:
                summary = generate_memory_summary(client, all_messages)
                if summary:
                    save_summary(current_chat_id, summary)
                    create_memory(memory_type="summary", content=summary, chat_id=current_chat_id, importance=0.7, confidence=0.9, source="consolidation")

            st.rerun()

    # --- SETTINGS TAB ---
    with settings_tab:
        st.header("⚙️ Settings")
        st.caption(
            "View the memories your Helping Bot is using. You can inspect and delete "
            "individual memory items, and customize how the bot should answer you."
        )

        (
            episodic_tab,
            summary_tab,
            preference_tab,
            customize_tab,
            working_tab,
            working_window_tab,
            conversational_tab,
        ) = st.tabs([
            "🧩 Episodic",
            "📝 Summary",
            "❤️ Preference",
            "🤖 Customize Bot",
            "🧠 Working",
            "🪟 Working Window",
            "💬 Conversational",
        ])

        def render_memory_list(memory_type, empty_message, key_prefix, limit=100):
            memories = get_memories(memory_type=memory_type, limit=limit)
            if not memories:
                st.info(empty_message)
                return

            for index, memory in enumerate(memories, start=1):
                with st.container(border=True):
                    st.markdown(f"**Memory {index}**")
                    st.write(memory["content"])
                    meta = []
                    if memory["source"]:
                        meta.append(f"Source: {memory['source']}")
                    if memory["updated_at"]:
                        meta.append(f"Updated: {memory['updated_at']}")
                    if meta:
                        st.caption(" • ".join(meta))

                    if st.button(
                        "Delete",
                        key=f"{key_prefix}_{memory['memory_id']}"
                    ):
                        delete_memory(memory["memory_id"])
                        st.rerun()

        # ---------------------------------------------------------
        # EPISODIC MEMORY
        # ---------------------------------------------------------
        with episodic_tab:
            st.subheader("🧩 Episodic Memory")
            st.caption(
                "Important past events, experiences, milestones, or conversation events "
                "the AI decided may be useful later."
            )
            render_memory_list(
                "episodic",
                "No episodic memories have been learned yet.",
                "delete_episodic"
            )

        # ---------------------------------------------------------
        # SUMMARY MEMORY
        # ---------------------------------------------------------
        with summary_tab:
            st.subheader("📝 Summary Memory")
            st.caption(
                "Conversation summaries created by the AI so it can remember the main "
                "context without rereading every previous message."
            )
            render_memory_list(
                "summary",
                "No summary memory has been created yet. A summary is created as conversations grow.",
                "delete_summary"
            )

        # ---------------------------------------------------------
        # PREFERENCE MEMORY
        # ---------------------------------------------------------
        with preference_tab:
            st.subheader("❤️ Preference Memory")
            st.caption(
                "Preferences the AI has learned, such as your learning style, answer style, "
                "format choices, or recurring likes and dislikes."
            )
            render_memory_list(
                "preference",
                "No preference memories have been learned yet.",
                "delete_preference"
            )

        # ---------------------------------------------------------
        # CUSTOMIZE YOUR BOT
        # ---------------------------------------------------------
        with customize_tab:
            st.subheader("🤖 Customize Your Bot")
            st.caption(
                "Tell the Helping Bot how you want it to answer. For example: "
                "'Explain simply with examples' or 'Answer like an interview mentor.'"
            )

            current_prompt = get_custom_bot_prompt()
            custom_prompt = st.text_area(
                "Your custom instructions",
                value=current_prompt,
                height=180,
                placeholder=(
                    "Example:\n"
                    "Explain concepts in simple language. Use real-world examples and "
                    "correct me clearly if I am wrong."
                ),
                key="custom_bot_prompt"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Custom Prompt", use_container_width=True):
                    save_custom_bot_prompt(custom_prompt)
                    st.success("Your bot customization has been saved.")
            with col2:
                if st.button("↩️ Reset", use_container_width=True):
                    save_custom_bot_prompt("")
                    st.success("Custom instructions reset.")
                    st.rerun()

        # ---------------------------------------------------------
        # WORKING MEMORY
        # ---------------------------------------------------------
        with working_tab:
            st.subheader("🧠 Working Memory")
            st.caption(
                "The current tasks or pieces of information the bot is actively focusing on."
            )
            render_memory_list(
                "working",
                "No working memories are active yet. Ask the bot a question to create one.",
                "delete_working"
            )

        # ---------------------------------------------------------
        # WORKING WINDOW MEMORY
        # ---------------------------------------------------------
        with working_window_tab:
            st.subheader("🪟 Working Window Memory")
            st.caption(
                "A rolling snapshot of the most recent messages in the active conversation. "
                "It is refreshed as you chat."
            )
            render_memory_list(
                "working_window",
                "No working-window memory exists yet. Start chatting and it will appear here.",
                "delete_working_window",
                limit=20
            )

        # ---------------------------------------------------------
        # CONVERSATIONAL MEMORY
        # ---------------------------------------------------------
        with conversational_tab:
            st.subheader("💬 Conversational Memory")
            st.caption(
                "Recent user and assistant messages stored as conversational memory. "
                "Internally this memory type is named 'recent_messages'."
            )
            render_memory_list(
                "recent_messages",
                "No conversational memories have been stored yet.",
                "delete_conversational",
                limit=200
            )

