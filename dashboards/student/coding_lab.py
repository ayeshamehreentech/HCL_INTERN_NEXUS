"""Beginner-friendly, Deep-Agent-style Coding Lab."""
from datetime import datetime
import streamlit as st
from database.connection import get_connection

QUESTIONS = {
    "Beginner": [
        {"key": "b1", "title": "Print your name", "prompt": "Write Python code that prints your name.", "checks": ["print", "(", ")"], "concept": "A function call sends text to the screen."},
        {"key": "b2", "title": "Two numbers", "prompt": "Store 5 and 7 in variables, then print their sum.", "checks": ["=", "print", "+"], "concept": "Variables remember values; + combines numbers."},
        {"key": "b3", "title": "Greeting", "prompt": "Create a variable called name and print a friendly greeting.", "checks": ["name", "=", "print"], "concept": "A variable lets one program work with different names."}
    ],
    "Intermediate": [
        {"key": "i1", "title": "Even or odd", "prompt": "Ask for a number and print whether it is even or odd.", "checks": ["input", "%", "if", "else"], "concept": "Use remainder (%) to test divisibility and if/else to choose a path."},
        {"key": "i2", "title": "Count to five", "prompt": "Use a loop to print the numbers 1 through 5.", "checks": ["for", "range", "print"], "concept": "A loop repeats a clear instruction."}
    ],
    "Advanced": [
        {"key": "a1", "title": "Right triangle", "prompt": "Print a right triangle of stars with 5 rows using a loop.", "checks": ["for", "range", "*", "print"], "concept": "Patterns come from changing one small value each loop."},
        {"key": "a2", "title": "Number pyramid", "prompt": "Print rows of 1, 22, 333, 4444, 55555 using a loop.", "checks": ["for", "range", "str", "print"], "concept": "Convert a number to text, then repeat it by the row count."}
    ]
}

def _attempt_count(user_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(DISTINCT question_key) AS total FROM coding_lab_attempts WHERE user_id = ? AND passed = 1", (user_id,)).fetchone()["total"]
    finally:
        conn.close()

def _save_attempt(user_id, question, category, code, passed, feedback):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO coding_lab_attempts (user_id, question_key, category, code, passed, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, question["key"], category, code, int(passed), feedback, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()

def _coach(question, code):
    missing = [token for token in question["checks"] if token not in code]
    if not code.strip():
        return False, "Start with one tiny step. Read the first sentence of the question, then write only that line."
    if missing:
        return False, "You are close. Your next focus is: {}. {} Try adding it, then trace what happens first, next, and last.".format(missing[0], question["concept"])
    return True, "Well done — your solution contains the core logic. {} Now explain the code aloud in your own words.".format(question["concept"])

def render_coding_lab():
    st.subheader("Coding Lab")
    st.caption("Your AI learning loop: understand → plan → write → check → improve. Start small; every correct question builds your logic.")
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("Please sign in again to save Coding Lab progress.")
        return
    completed = _attempt_count(user_id)
    st.progress(min(completed / 50, 1.0), text="{}/50 mastery questions completed".format(completed))
    if completed >= 50:
        st.success("You have reached the 50-question milestone. You are ready to practise small logic and pattern programs.")
    category = st.selectbox("Choose your level", list(QUESTIONS), key="coding_lab_category")
    question_index = st.selectbox("Choose a challenge", range(len(QUESTIONS[category])), format_func=lambda i: QUESTIONS[category][i]["title"])
    question = QUESTIONS[category][question_index]
    st.markdown("### " + question["title"])
    st.write(question["prompt"])
    with st.expander("Plan before you code"):
        st.write("Concept: " + question["concept"])
        st.write("1. Identify the input or value. 2. Choose one instruction. 3. Predict the output. 4. Write and improve.")
    code = st.text_area("Write Python code", height=220, placeholder="# Write your first attempt here", key="code_" + question["key"])
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Check my logic", use_container_width=True):
            passed, feedback = _coach(question, code)
            _save_attempt(user_id, question, category, code, passed, feedback)
            (st.success if passed else st.info)(feedback)
    with col2:
        if st.button("Give me a gentle hint", use_container_width=True):
            st.warning("Hint: " + question["concept"] + " Do not copy a full answer — write one line, then ask yourself what it will do.")
