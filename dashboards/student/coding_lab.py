"""LangGraph-powered adaptive Python Coding Lab."""
from __future__ import annotations

import json
import base64
import html
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import quote_plus
from uuid import uuid4

import streamlit as st
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from ai.config import get_groq_api_key, get_groq_model
from database.connection import get_connection


JOURNEY_WORLDS = [
    ("Input & Output", "Airport Boarding", "Learn to receive and display information."),
    ("Variables", "Shopping Cart", "Store and update useful values."),
    ("Conditions", "Castle Gate", "Make decisions using if, elif, and else."),
    ("Loops", "Fuel Station", "Repeat a useful action safely."),
    ("Lists", "Treasure Chest", "Collect and organize items."),
    ("Functions", "Robot Repair", "Build reusable helpers."),
    ("OOP", "AI Lab", "Model objects and their behaviour."),
    ("Advanced Python", "Cyber Lock", "Combine ideas to solve larger missions."),
]

BEGINNER_STAGES = [
    ("Input & Output", "Shopping Cart", "Welcome a shopper by printing one short message."),
    ("Variables", "Shopping Cart", "Put one item name or price into a variable, then print it."),
    ("Input", "Airport Boarding", "Ask for one value with input(), then print a friendly response."),
    ("Conditions", "Castle Gate", "Use one simple if statement with one comparison."),
    ("Loops", "Fuel Station", "Repeat one short action with a small range()."),
]

SCENARIO_ART = {
    "Shopping Cart": "shopping-cart-quest.png",
}


def _scenario_for(concept: str, level: str, completed: int) -> dict[str, str]:
    """Map a generated Python concept to a reusable story world."""
    text = concept.lower()
    matches = [
        (("nested loop",), "Multi-room Castle", "Explore rooms using a loop inside a loop."),
        (("loop", "range", "while", "iterate"), "Fuel Station", "Keep the station running one customer at a time."),
        (("condition", "if", "boolean", "comparison", "logical"), "Castle Gate", "Open the gate only when its rules are satisfied."),
        (("list", "tuple", "dictionary", "dict", "collection"), "Treasure Chest", "Organize the treasures you discover."),
        (("function", "parameter", "return"), "Robot Repair", "Teach a repair robot one reusable skill."),
        (("class", "object", "inheritance", "oop"), "AI Lab", "Program a helpful AI lab device."),
        (("input", "print", "string", "variable", "number"), "Airport Boarding", "Help travellers through a simple check-in."),
    ]
    for keywords, name, story in matches:
        if any(keyword in text for keyword in keywords):
            return {"name": name, "story": story, "difficulty": level, "stage": str(completed + 1)}
    return {"name": "Forest Path", "story": "Choose the next safe step on the learning trail.", "difficulty": level, "stage": str(completed + 1)}


def _next_scenario(level: str, completed: int) -> dict[str, str]:
    """Choose the next reusable world from durable learner progress."""
    if level == "Beginner":
        concept, name, story = BEGINNER_STAGES[min(len(BEGINNER_STAGES) - 1, completed)]
        return {"name": name, "story": story, "concept_focus": concept, "difficulty": level, "stage": str(completed + 1)}
    concept, name, story = JOURNEY_WORLDS[min(len(JOURNEY_WORLDS) - 1, completed // 3)]
    return {"name": name, "story": story, "concept_focus": concept, "difficulty": level, "stage": str(completed + 1)}


def _render_scenario_art(scenario: dict[str, str]) -> None:
    """Show actual quest artwork where an asset exists, not only a text label."""
    filename = SCENARIO_ART.get(scenario.get("name", ""))
    if not filename:
        return
    image_path = Path(__file__).resolve().parents[2] / "assets" / filename
    if image_path.exists():
        st.image(str(image_path), caption="Mission scene · {}".format(scenario["name"]), use_container_width=True)


def _render_game_hud(completed: int, coins: int) -> None:
    """Render the original Python Quest HUD above the playable map."""
    level = max(1, completed // 6 + 1)
    xp = min(100, (completed % 6) * 16 + 8)
    st.markdown(
        f"""<style>
        .pyquest-hud {{background:linear-gradient(115deg,#042c5a,#075e9b 55%,#073d70);border:2px solid #50cfff;border-radius:22px;padding:1rem 1.25rem;color:#fff;box-shadow:0 10px 22px #001c3a55;margin:.2rem 0 .8rem}}
        .pyquest-title {{font-size:1.65rem;font-weight:900;letter-spacing:.04em;color:#ffd44d;text-shadow:2px 2px #092148}} .pyquest-tag {{font-size:.82rem;color:#c9efff}}
        .hud-stat {{background:#082244;border:1px solid #3fc7ff;border-radius:14px;padding:.45rem .75rem;font-weight:800;text-align:center;color:#fff}} .hud-stat b {{color:#ffd548;font-size:1.15rem}}
        .xp-track {{height:9px;background:#081f3b;border-radius:8px;overflow:hidden;margin-top:.35rem}} .xp-fill {{height:100%;width:{xp}%;background:linear-gradient(90deg,#9cf52f,#ffe34a);border-radius:8px}}
        </style><div class='pyquest-hud'><div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap'><div><div class='pyquest-title'>🐍 PYQUEST</div><div class='pyquest-tag'>Code. Solve. Level Up.</div></div><div style='min-width:210px'><b>Level {level}</b> · {completed} verified quests<div class='xp-track'><div class='xp-fill'></div></div><small>{xp}/100 XP to the next level</small></div><div style='display:flex;gap:.5rem'><div class='hud-stat'>🪙 <b>{coins}</b><br><small>coins</small></div><div class='hud-stat'>⚡ <b>5/5</b><br><small>focus</small></div></div></div></div>""",
        unsafe_allow_html=True,
    )


def _render_journey(completed: int) -> None:
    """Render an illustrated map with interactive-looking, progress-aware worlds."""
    unlocked = min(len(JOURNEY_WORLDS), completed // 3 + 1)
    cards = []
    for index, (concept, world, description) in enumerate(JOURNEY_WORLDS):
        status = "unlocked" if index < unlocked else "locked"
        icon = "✅" if index < unlocked - 1 else ("🗺️" if status == "unlocked" else "🔒")
        cards.append(f"<div class='quest-world {status}'><div class='quest-icon'>{icon}</div><strong>{index + 1}. {concept}</strong><span>{world}</span><small>{description}</small></div>")
    map_path = Path(__file__).resolve().parents[2] / "assets" / "python-quest-map.png"
    backdrop = ""
    if map_path.exists():
        backdrop = "data:image/png;base64," + base64.b64encode(map_path.read_bytes()).decode("ascii")
    st.markdown(
        """<style>
        .quest-map-shell {background-image:linear-gradient(#00376633,#00376633),url('""" + backdrop + """');background-size:cover;background-position:center;border-radius:22px;min-height:350px;padding:1rem;box-shadow:inset 0 0 0 2px #5ee4ff,0 12px 22px #02234b66;display:flex;align-items:flex-end}
        .quest-map {display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:.7rem;width:100%;}.quest-world {min-height:90px;padding:.6rem;border-radius:14px;display:flex;flex-direction:column;gap:.1rem;border:2px solid #9ceaff;background:linear-gradient(160deg,#074579ee,#032851ee);color:#fff;box-shadow:0 5px 10px #001e42aa;text-shadow:1px 1px #001b38}.quest-world.unlocked:hover{transform:translateY(-3px);border-color:#ffe95a}.quest-world.locked{filter:saturate(.1);opacity:.76;background:#20384ddd}.quest-world span{color:#ffe769;font-size:.76rem;font-weight:800}.quest-world small{color:#d7f4ff;font-size:.67rem;line-height:1.15}.quest-icon{font-size:1rem}@media(max-width:800px){.quest-map{grid-template-columns:repeat(2,minmax(120px,1fr))}.quest-map-shell{min-height:440px}}
        </style><div class='quest-map-shell'><div class='quest-map'>""" + "".join(cards) + "</div></div>",
        unsafe_allow_html=True,
    )


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
    scenario: dict[str, str]


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
    scenario = state.get("scenario", {})
    prompt = f"""You are the planning node in an adaptive Python Coding Lab.
Create one fresh {state.get('level', 'Beginner')} Python challenge for a learner who has completed {state.get('completed_count', 0)} verified challenges.
Do not repeat these previous titles: {prior}.
The task must be small, practical, solvable without external packages, and teach one clear idea.
Frame the mission as the reusable scenario '{scenario.get('name', 'Forest Path')}'. Story direction: {scenario.get('story', '')}. Focus first on {scenario.get('concept_focus', 'a suitable Python concept')}.
Use this optional research context only to choose an appropriate concept: {state.get('research', '')}.
Return JSON only with title, prompt, concept, requirements (array of 2-4 strings), and starter_code.
Do not include a solution, tests, answer, or markdown fences."""
    if state.get("level") == "Beginner":
        completed = int(state.get("completed_count", 0))
        guardrail = (
            "BEGINNER SAFETY LADDER: This learner may know nothing. "
            "For challenges 0-1 use only print(), strings, or one variable; no input(), if, loops, lists, functions, or math. "
            "For challenges 2-3 allow one input() or one variable plus print(). "
            "For challenges 4-5 allow exactly one simple if comparison. "
            "Use a single sentence mission, at most two requirements, and give a tiny starter-code comment. "
            f"Current completed count is {completed}; obey the matching rung exactly."
        )
        prompt += "\n" + guardrail
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
        "scenario": scenario,
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
    user_id = _student_id()
    if not user_id:
        st.info("Sign in as a student to start your personal Coding Lab.")
        return

    completed = _count_completed(user_id)
    coins = max(0, completed // 3 - _count_unlocks(user_id))
    progress_in_coin_cycle = completed % 3
    _render_game_hud(completed, coins)
    st.markdown("<div style='display:flex;justify-content:space-between;align-items:center'><h3 style='margin:.25rem 0;color:#073b70'>🗺️ Your Python Quest Map</h3><span style='background:#fff0a1;padding:.35rem .75rem;border-radius:99px;color:#5a3800;font-weight:700'>Complete quests · collect coins · unlock worlds</span></div>", unsafe_allow_html=True)
    _render_journey(completed)

    info, bar, next_up = st.columns([1, 3, 1])
    with info:
        st.metric("Verified quests", completed)
    with bar:
        st.markdown("**Coin progress**")
        coin_progress = st.progress(progress_in_coin_cycle / 3, text=f"{progress_in_coin_cycle}/3 correct answers toward the next 🪙")
    with next_up:
        st.metric("Next coin", 3 - progress_in_coin_cycle if progress_in_coin_cycle else 3)

    st.markdown("### 🎮 Mission Control")
    level = st.selectbox("Choose your current level", ["Beginner", "Intermediate", "Advanced"], key="coding_lab_level")
    session_key = f"coding_lab_task_{user_id}"
    history_key = f"coding_lab_titles_{user_id}"
    task = st.session_state.get(session_key)

    if st.button("✨ Start my next quest", type="primary", use_container_width=True):
        with st.spinner("The LangGraph planner is researching and creating a challenge…"):
            try:
                scenario = _next_scenario(level, completed)
                result = run_coding_agent("generate", level=level, completed_count=completed, previous_titles=st.session_state.get(history_key, []), scenario=scenario)
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
        st.info("Choose a level, then start a fresh AI-generated quest. Every mission teaches one small Python idea before you code.")
        return

    safe_title = html.escape(task["title"])
    st.markdown("<div style='background:linear-gradient(100deg,#063563,#0878bf);border-radius:16px;padding:1rem 1.2rem;color:#fff;margin-top:.8rem'><h3 style='color:#ffe95a;margin:0'>🏆 " + safe_title + "</h3><small>Complete this mission to earn progress toward a coin.</small></div>", unsafe_allow_html=True)
    scenario = task.get("scenario") or _scenario_for(task.get("concept", ""), task.get("category", level), completed)
    scene, briefing = st.columns([1, 1.35], gap="large")
    with scene:
        _render_scenario_art(scenario)
        st.info(f"🎮 **Mission world: {scenario.get('name', 'Forest Path')}**")
    with briefing:
        st.markdown("#### Quest briefing")
        st.write(scenario.get("story", "Build your Python skill one step at a time."))
        st.write(task["prompt"])
        st.caption(f"Skill unlocked: {task['concept']}")
        st.markdown("**Win this quest by**")
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
