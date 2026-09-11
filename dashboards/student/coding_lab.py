"""LangGraph-powered adaptive Python Coding Lab."""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal, TypedDict
from urllib.parse import quote_plus
from uuid import uuid4

import streamlit as st
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from ai.config import get_groq_api_key, get_groq_model
from database.connection import get_connection


class CodingLabState(TypedDict, total=False):
    action: Literal["generate", "review", "hint", "solution"]
    level: str
    completed_count: int
    previous_titles: list[str]
    task: dict[str, Any]
    code: str
    research: str
    feedback: str
    passed: bool
    solution: str
    error: str


def _json_object(text: str) -> dict[str, Any]:
    """Read a JSON object even when the model wraps it in Markdown."""
    fence = chr(96) * 3
    cleaned = text.strip().replace(fence + "json", "").replace(fence, "").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _content(message: Any) -> str:
    content = getattr(message, "content", message)
    return " ".join(str(item) for item in content) if isinstance(content, list) else str(content)


@lru_cache(maxsize=1)
def _model() -> ChatGroq:
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for the Coding Lab agent.")
    return ChatGroq(model=get_groq_model(), api_key=api_key, temperature=0.25)


def _search_learning_context(state: CodingLabState) -> dict[str, Any]:
    """Tool node: optional web context before planning a challenge."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        query = f"Python {state.get('level', 'Beginner')} tutorial concepts"
        return {"research": DuckDuckGoSearchRun().run(query)[:1800]}
    except Exception:
        return {"research": "Use standard Python documentation and first-principles teaching."}


def _generate_task(state: CodingLabState) -> dict[str, Any]:
    prior = ", ".join(state.get("previous_titles", [])[-12:]) or "none"
    prompt = f"""You are the planning node in an adaptive Python Coding Lab.
Create one fresh {state.get('level', 'Beginner')} Python challenge for a learner who has completed {state.get('completed_count', 0)} verified challenges.
Do not repeat these previous titles: {prior}.
The task must be small, practical, solvable without external packages, and teach one clear idea.
Use this optional research context only to choose an appropriate concept: {state.get('research', '')}.
Return JSON only with title, prompt, concept, requirements (array of 2-4 strings), and starter_code.
Do not include a solution, tests, answer, or markdown fences."""
    payload = _json_object(_content(_model().invoke(prompt)))
    required = ("title", "prompt", "concept", "requirements")
    if not all(payload.get(key) for key in required) or not isinstance(payload.get("requirements"), list):
        return {"error": "The tutor could not create a structured challenge. Please try again."}
    return {"task": {
        "key": uuid4().hex,
        "title": str(payload["title"]).strip()[:120],
        "prompt": str(payload["prompt"]).strip(),
        "concept": str(payload["concept"]).strip()[:180],
        "requirements": [str(item).strip() for item in payload["requirements"][:4]],
        "starter_code": str(payload.get("starter_code", "")),
        "category": state.get("level", "Beginner"),
    }}


def _review_attempt(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are the review node in a Python learning graph. Assess this submitted code without executing it.
A submission passes only if it clearly satisfies every requirement. Be kind but exact.
Task: {task.get('prompt', '')}
Concept: {task.get('concept', '')}
Requirements: {json.dumps(task.get('requirements', []))}
Student code:
{state.get('code', '')}
Return JSON only: {{"passed": true or false, "feedback": "concise explanation and next step"}}.
Never provide a complete replacement solution."""
    payload = _json_object(_content(_model().invoke(prompt)))
    return {"passed": bool(payload.get("passed", False)), "feedback": str(payload.get("feedback", "I could not verify this attempt. Please try again."))}


def _give_hint(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are a supportive Python tutor. Give exactly one progressive hint for this task using the student's current attempt.
Explain the missing idea, but do not give final code, full pseudocode, or an answer.
Task: {task.get('prompt', '')}
Concept: {task.get('concept', '')}
Student code:
{state.get('code', '') or '(no attempt yet)'}"""
    return {"feedback": _content(_model().invoke(prompt)).strip()}


def _reveal_solution(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are the answer node in a Python learning graph. Produce a correct, short reference solution for this exact task.
Include only Python code followed by a two-sentence explanation.
Task: {task.get('prompt', '')}
Requirements: {json.dumps(task.get('requirements', []))}"""
    return {"solution": _content(_model().invoke(prompt)).strip()}


def _route(state: CodingLabState) -> str:
    return state.get("action", "generate")


@lru_cache(maxsize=1)
def coding_lab_graph():
    """Compile the LangGraph workflow once per Streamlit process."""
    graph = StateGraph(CodingLabState)
    graph.add_node("research", _search_learning_context)
    graph.add_node("generate", _generate_task)
    graph.add_node("review", _review_attempt)
    graph.add_node("hint", _give_hint)
    graph.add_node("solution", _reveal_solution)
    graph.add_conditional_edges(START, _route, {
        "generate": "research", "review": "review", "hint": "hint", "solution": "solution",
    })
    graph.add_edge("research", "generate")
    graph.add_edge("generate", END)
    graph.add_edge("review", END)
    graph.add_edge("hint", END)
    graph.add_edge("solution", END)
    return graph.compile()


def run_coding_agent(action: str, **state: Any) -> dict[str, Any]:
    """Invoke one explicit LangGraph path and return a serialisable result."""
    return dict(coding_lab_graph().invoke({"action": action, **state}))


def _count_completed(user_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(DISTINCT question_key) AS total FROM coding_lab_attempts WHERE user_id = ? AND passed = 1", (user_id,)).fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def _count_unlocks(user_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM coding_lab_attempts WHERE user_id = ? AND feedback = ?", (user_id, "solution_unlock")).fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def _is_task_completed(user_id: int, question_key: str) -> bool:
    """A challenge can award progress only once, even after repeated checks."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM coding_lab_attempts WHERE user_id = ? AND question_key = ? AND passed = 1",
            (user_id, question_key),
        ).fetchone()
        return bool(row and int(row["count"]))
    finally:
        conn.close()


def _render_learn_first(task: dict[str, Any]) -> bool:
    """Give every learner a no-cost learning route before they attempt a task."""
    concept = str(task.get("concept", "Python basics"))
    query = quote_plus(f"Python {concept}")
    st.markdown("### Learn this before you code")
    st.write(f"You do not need prior knowledge. Spend a few minutes learning **{concept}**, then return and try the challenge.")
    resource_columns = st.columns(3)
    with resource_columns[0]:
        st.link_button("IBM SkillsBuild · free learning", "https://skillsbuild.org/", use_container_width=True)
    with resource_columns[1]:
        st.link_button("Cisco Networking Academy · free courses", "https://www.netacad.com/courses", use_container_width=True)
    with resource_columns[2]:
        st.link_button("Python docs · topic guide", f"https://docs.python.org/3/search.html?q={query}", use_container_width=True)
    st.caption("These are focused learning sources, not answers. Read one source, then use the coach and hints if you are stuck.")
    return st.checkbox("I reviewed a learning resource and I am ready to try this task", key=f"coding_lab_ready_{task['key']}")


def _save_attempt(user_id: int, task: dict[str, Any], code: str, passed: bool, feedback: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO coding_lab_attempts (user_id, question_key, category, code, passed, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, task["key"], task.get("category", "Beginner"), code, int(passed), feedback, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _student_id() -> int | None:
    user = st.session_state.get("user")
    if isinstance(user, dict) and user.get("id"):
        return int(user["id"])
    value = st.session_state.get("user_id")
    return int(value) if value else None


def render_coding_lab() -> None:
    """Render an endless, adaptive Python practice loop."""
    st.header("🧪 Coding Lab")
    st.caption("LangGraph plans a fresh challenge, reviews your reasoning, coaches one step at a time, and never runs submitted code.")
    user_id = _student_id()
    if not user_id:
        st.info("Sign in as a student to start your personal Coding Lab.")
        return

    completed = _count_completed(user_id)
    coins = max(0, completed // 3 - _count_unlocks(user_id))
    progress_in_coin_cycle = completed % 3
    left, middle, right, bonus = st.columns(4)
    left.metric("Verified challenges", completed)
    middle.metric("Answer coins", f"🪙 {coins}")
    right.metric("Next coin in", 3 - progress_in_coin_cycle if progress_in_coin_cycle else 3)
    bonus.metric("Progress points", f"{completed} ⭐")
    st.markdown("**Coin progress — each verified answer fills one step**")
    coin_progress = st.progress(progress_in_coin_cycle / 3, text=f"{progress_in_coin_cycle}/3 correct answers toward your next 🪙 answer coin")

    level = st.selectbox("Choose your current level", ["Beginner", "Intermediate", "Advanced"], key="coding_lab_level")
    session_key = f"coding_lab_task_{user_id}"
    history_key = f"coding_lab_titles_{user_id}"
    task = st.session_state.get(session_key)

    if st.button("✨ Create my next AI challenge", type="primary"):
        with st.spinner("The LangGraph planner is researching and creating a challenge…"):
            try:
                result = run_coding_agent("generate", level=level, completed_count=completed, previous_titles=st.session_state.get(history_key, []))
                if result.get("task"):
                    st.session_state[session_key] = result["task"]
                    st.session_state[history_key] = (st.session_state.get(history_key, []) + [result["task"]["title"]])[-30:]
                    st.session_state.pop(f"coding_lab_answer_{user_id}", None)
                    st.rerun()
                st.warning(result.get("error", "The planner did not return a challenge. Please try again."))
            except Exception:
                st.error("The AI tutor is temporarily unavailable. Please try again shortly.")
        return

    if not task:
        st.info("Choose a level, then ask the LangGraph planner for a fresh Python challenge.")
        return

    st.subheader(task["title"])
    st.write(task["prompt"])
    st.caption(f"Concept: {task['concept']}")
    st.markdown("**Success criteria**")
    for requirement in task["requirements"]:
        st.markdown(f"- {requirement}")

    if not _render_learn_first(task):
        st.info("Start with one free learning resource above. When you are ready, tick the box to open your coding workspace.")
        return

    code = st.text_area("Write your Python attempt", value=task.get("starter_code", ""), height=260, key=f"coding_lab_code_{task['key']}")
    check, hint, answer = st.columns(3)
    if check.button("Check my logic"):
        if _is_task_completed(user_id, task["key"]):
            st.info("You already earned this task's progress point. Create a fresh challenge for the next point.")
        elif not code.strip():
            st.warning("Write an attempt first. The tutor will coach your first step.")
        else:
            with st.spinner("The review node is checking your logic…"):
                try:
                    result = run_coding_agent("review", task=task, code=code)
                    passed = bool(result.get("passed", False))
                    feedback = result.get("feedback", "No review was returned.")
                    _save_attempt(user_id, task, code, passed, feedback)
                    if passed:
                        next_completed = completed + 1
                        st.success("Correct answer verified! +1 progress point added to your coin bar.")
                        if next_completed % 3 == 0:
                            coin_progress.progress(1.0, text="3/3 correct answers — 🪙 answer coin earned!")
                            st.balloons()
                            st.success("🪙 Coin earned! Use it only when you truly need a reference answer.")
                        else:
                            coin_progress.progress((next_completed % 3) / 3, text=f"{next_completed % 3}/3 correct answers toward your next 🪙 answer coin")
                            st.info(f"{next_completed % 3}/3 correct answers toward your next answer coin.")
                    else:
                        st.info(feedback)
                except Exception:
                    st.error("The review node is temporarily unavailable. Your work has not been marked.")

    if hint.button("Give a gentle hint"):
        with st.spinner("The coaching node is preparing one hint…"):
            try:
                st.info(run_coding_agent("hint", task=task, code=code).get("feedback", "Try breaking the task into one smaller step."))
            except Exception:
                st.error("The hint node is temporarily unavailable.")

    if answer.button("Use 1 coin for answer", disabled=coins < 1):
        with st.spinner("Unlocking the reference answer…"):
            try:
                solution = run_coding_agent("solution", task=task, code=code).get("solution", "No answer was returned.")
                _save_attempt(user_id, task, "", False, "solution_unlock")
                st.session_state[f"coding_lab_answer_{user_id}"] = solution
                st.rerun()
            except Exception:
                st.error("The answer node is temporarily unavailable. Your coin was not used.")

    if coins < 1:
        st.caption("Earn one answer coin after every three verified, distinct challenges. Coins are not required for hints.")
    unlocked = st.session_state.get(f"coding_lab_answer_{user_id}")
    if unlocked:
        st.markdown("### Unlocked reference answer")
        st.code(unlocked, language="python")
