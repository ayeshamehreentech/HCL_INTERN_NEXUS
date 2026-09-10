from datetime import datetime

import streamlit as st
from langchain_community.tools import DuckDuckGoSearchRun
from database.connection import get_connection

SEEDS = [
    ("Beginner", "Print your name", "Write Python that prints your name.", ["print", "("], "print() sends text to the screen."),
    ("Beginner", "Add two numbers", "Store 5 and 7, then print their sum.", ["=", "print", "+"], "Variables store values and + adds numbers."),
    ("Beginner", "Greeting", "Create name and print a greeting using it.", ["name", "=", "print"], "A variable can be reused in an output."),
    ("Beginner", "Favourite colour", "Ask for a favourite colour and print it.", ["input", "print"], "input() collects text."),
    ("Beginner", "Rectangle area", "Store length and width, then print their area.", ["=", "print", "*"], "Multiply two measurements."),
    ("Beginner", "First list", "Create a list of three fruits and print it.", ["[", "]", "print"], "Lists keep several values together."),
    ("Intermediate", "Even or odd", "Ask for a number and print whether it is even or odd.", ["input", "%", "if", "else"], "Use remainder (%) and if/else."),
    ("Intermediate", "Count to five", "Use a loop to print 1 through 5.", ["for", "range", "print"], "A for loop repeats an instruction."),
    ("Intermediate", "Largest of two", "Read two numbers and print the larger one.", ["input", "if", "else"], "A comparison controls a decision."),
    ("Intermediate", "Sum a list", "Create a list of numbers and print their sum.", ["[", "sum", "print"], "sum() adds a collection."),
    ("Intermediate", "Multiplication table", "Print the multiplication table for 3.", ["for", "range", "print", "*"], "Change one value each loop pass."),
    ("Intermediate", "Password check", "Ask for a password and print success or retry.", ["input", "if", "else"], "Compare input to the expected value."),
    ("Advanced", "Right triangle", "Print a right triangle of stars with five rows.", ["for", "range", "*", "print"], "Patterns grow one row at a time."),
    ("Advanced", "Number pyramid", "Print 1, 22, 333, 4444, 55555 using a loop.", ["for", "range", "str", "print"], "Convert a number to text and repeat it."),
    ("Advanced", "FizzBuzz", "Print 1 to 20; use Fizz for 3 and Buzz for 5.", ["for", "%", "if", "elif"], "Test combined conditions first."),
    ("Advanced", "Palindrome", "Check whether a word reads the same backwards.", ["if", "[::-1]"], "Compare text with its reverse."),
    ("Advanced", "Prime check", "Decide whether a number is prime.", ["for", "range", "%", "if"], "Try possible divisors."),
    ("Advanced", "Nested pattern", "Print a 4 by 4 square of stars.", ["for", "range", "print"], "One loop creates rows; another builds a row."),
]

SOLUTIONS = {
    "Print your name": 'print("Ayesha")',
    "Add two numbers": "first = 5\nsecond = 7\nprint(first + second)",
    "Greeting": 'name = "Ayesha"\nprint("Hello, " + name)',
    "Favourite colour": 'colour = input("Favourite colour: ")\nprint(colour)',
    "Rectangle area": "length = 5\nwidth = 3\nprint(length * width)",
    "First list": 'fruits = ["apple", "banana", "mango"]\nprint(fruits)',
    "Even or odd": 'number = int(input("Number: "))\nif number % 2 == 0:\n    print("Even")\nelse:\n    print("Odd")',
    "Count to five": "for number in range(1, 6):\n    print(number)",
    "Largest of two": 'first = int(input("First number: "))\nsecond = int(input("Second number: "))\nif first > second:\n    print(first)\nelse:\n    print(second)',
    "Sum a list": "numbers = [2, 4, 6]\nprint(sum(numbers))",
    "Multiplication table": "for number in range(1, 11):\n    print(3 * number)",
    "Password check": 'password = input("Password: ")\nif password == "python":\n    print("Success")\nelse:\n    print("Retry")',
    "Right triangle": "for row in range(1, 6):\n    print("*" * row)",
    "Number pyramid": "for number in range(1, 6):\n    print(str(number) * number)",
    "FizzBuzz": "for number in range(1, 21):\n    if number % 15 == 0:\n        print("FizzBuzz")\n    elif number % 3 == 0:\n        print("Fizz")\n    elif number % 5 == 0:\n        print("Buzz")\n    else:\n        print(number)",
    "Palindrome": 'word = input("Word: ")\nif word == word[::-1]:\n    print("Palindrome")\nelse:\n    print("Not a palindrome")',
    "Prime check": 'number = int(input("Number: "))\nis_prime = number > 1\nfor divisor in range(2, number):\n    if number % divisor == 0:\n        is_prime = False\n        break\nprint("Prime" if is_prime else "Not prime")',
    "Nested pattern": "for row in range(4):\n    for column in range(4):\n        print("*", end="")\n    print()",
}


def _attempt_count(user_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(DISTINCT question_key) AS total FROM coding_lab_attempts WHERE user_id = ? AND passed = 1", (user_id,)).fetchone()
        return row["total"] if row else 0
    finally:
        conn.close()


def _solution_reveal_count(user_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS total FROM coding_lab_attempts WHERE user_id = ? AND feedback = ?", (user_id, "solution_unlock")).fetchone()
        return row["total"] if row else 0
    finally:
        conn.close()


def _save_attempt(user_id, question, code, passed, feedback):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO coding_lab_attempts (user_id, question_key, category, code, passed, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, question["key"], question["category"], code, int(passed), feedback, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def _next_question(completed, level):
    pool = [seed for seed in SEEDS if seed[0] == level]
    category, title, prompt, checks, concept = pool[completed % len(pool)]
    return {"key": "python-{}-{}".format(level.lower(), completed + 1), "category": category, "title": "{} · Practice {}".format(title, completed // len(pool) + 1), "prompt": prompt, "checks": checks, "concept": concept, "base_title": title}


def _coach(question, code):
    if not code.strip():
        return False, "Plan first: write one small line that solves the first step. Predict what it will output."
    missing = [token for token in question["checks"] if token not in code]
    if missing:
        return False, "Next small fix: add {}. {} Then trace the code one line at a time.".format(missing[0], question["concept"])
    return True, "Core logic found. {} Explain each line, then unlock the next challenge.".format(question["concept"])


def _web_guidance(question):
    try:
        return DuckDuckGoSearchRun().run("Python tutorial {} {}".format(question["title"], question["concept"]))
    except Exception:
        return "Web guidance is temporarily unavailable. Use the plan and write one line at a time."


def _deep_agent_hint(question, code):
    passed, feedback = _coach(question, code)
    status = "Your attempt is close." if passed else "Your attempt needs one more step."
    return "{} {} The full reference answer remains locked until you earn a solution credit.".format(status, feedback)


def render_coding_lab():
    st.subheader("🧪 Continuous Python Coding Lab")
    st.caption("Deep Agent loop: plan → write → inspect → research → improve → next question. Every 3 correct challenges earns one full-answer credit.")
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("Please sign in again to save your practice.")
        return

    completed = _attempt_count(user_id)
    reveals_used = _solution_reveal_count(user_id)
    available_reveals = max(0, completed // 3 - reveals_used)
    st.progress(min(completed / 50, 1.0), text="{}/50 foundation questions completed · practice continues".format(completed))
    st.info("🏆 Solution credits: {} available. Earn 1 after every 3 distinct correct challenges; each credit reveals one full answer.".format(available_reveals))

    level = st.selectbox("Starting level", ["Beginner", "Intermediate", "Advanced"], key="coding_lab_level")
    question = _next_question(completed, level)
    st.markdown("### " + question["title"])
    st.write(question["prompt"])
    with st.expander("Deep Agent plan before coding", expanded=True):
        st.write("Concept: " + question["concept"])
        st.write("1. Name the input. 2. Decide the output. 3. Write the smallest working line. 4. Trace it. 5. Improve after feedback.")

    code = st.text_area("Write Python code", height=220, placeholder="# Your attempt goes here", key=question["key"])
    check_col, hint_col, agent_col, web_col = st.columns(4)
    with check_col:
        if st.button("Check my logic", use_container_width=True):
            passed, feedback = _coach(question, code)
            _save_attempt(user_id, question, code, passed, feedback)
            (st.success if passed else st.info)(feedback)
            if passed:
                st.rerun()
    with hint_col:
        if st.button("Give a gentle hint", use_container_width=True):
            st.warning("Hint: " + question["concept"] + " Do not copy an answer; write one line and predict its output.")
    with agent_col:
        if st.button("Get answer (1 coin)", use_container_width=True):
            if available_reveals > 0:
                _save_attempt(user_id, question, "", False, "solution_unlock")
                st.session_state["coding_lab_full_answer"] = SOLUTIONS[question["base_title"]]
                st.session_state["coding_lab_answer_question"] = question["key"]
                st.rerun()
            st.session_state["coding_lab_agent_guidance"] = _deep_agent_hint(question, code)
    with web_col:
        if st.button("Find web guidance", use_container_width=True):
            st.session_state["coding_lab_web_guidance"] = _web_guidance(question)

    if st.session_state.get("coding_lab_agent_guidance"):
        with st.expander("💡 Study guidance", expanded=True):
            st.write(st.session_state["coding_lab_agent_guidance"])
    if st.session_state.get("coding_lab_full_answer") and st.session_state.get("coding_lab_answer_question") == question["key"]:
        with st.expander("✅ Earned reference answer", expanded=True):
            st.code(st.session_state["coding_lab_full_answer"], language="python")
            st.caption("Read it line by line, then write your own version before moving on.")
    if st.session_state.get("coding_lab_web_guidance"):
        with st.expander("DuckDuckGo learning guidance", expanded=True):
            st.write(st.session_state["coding_lab_web_guidance"])
