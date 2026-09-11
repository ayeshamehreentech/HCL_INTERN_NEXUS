"""Deterministic teaching and remediation specialist for PyQuest.

This module deliberately has no UI, database, model, or network dependency.
The coordinator can store its small, JSON-serialisable results in Streamlit
session state or Supabase and render them in any view.
"""
from __future__ import annotations

from typing import Any


_ALIASES = {
    "print()": "print",
    "first words": "print",
    "taking input": "input",
    "input()": "input",
    "if / else": "conditions",
    "if/else": "conditions",
    "for loops": "loops",
    "function": "functions",
}


_LESSONS: dict[str, dict[str, Any]] = {
    "print": {
        "title": "Python Village · First Words",
        "world": "Shopping Cart",
        "goal": "Tell Python to display one message.",
        "pages": (
            {
                "heading": "Meet print()",
                "story": "At the village shop, the notice board stays blank until you tell it exactly what to show.",
                "example": 'print("Hello, explorer!")',
                "check": "print() writes a value to the screen.",
            },
            {
                "heading": "Words, numbers, and comments",
                "story": "Words need quotes. Numbers do not. A comment is a note for humans, starting with #.",
                "example": '# A friendly shop sign\nprint("Apples")\nprint(3)',
                "check": "Use quotes around text such as \"Apples\".",
            },
            {
                "heading": "Your first quest",
                "story": "Make a sign for the shopper. One clear line is enough.",
                "example": 'print("Welcome to the mall!")',
                "check": "Run a print() line and read its output.",
            },
        ),
        "camp": {
            "mission": "Write three tiny messages: your name, a favourite food, and Welcome!",
            "starter_code": 'print("My name is ...")\nprint("I like ...")\nprint("Welcome!")',
            "success_signals": ("print(",),
        },
    },
    "input": {
        "title": "Airport Check-in · Taking Input",
        "world": "Locked Door",
        "goal": "Ask a traveller for information, then use it.",
        "pages": (
            {
                "heading": "Ask a question",
                "story": "At airport check-in, the desk asks for a passenger name before printing a boarding greeting.",
                "example": 'name = input("What is your name? ")',
                "check": "input() waits for the learner to type a value.",
            },
            {
                "heading": "Save the answer",
                "story": "The answer is stored in a labelled box called a variable.",
                "example": 'name = input("Name: ")\nprint("Hello", name)',
                "check": "Put input() on the right side of =.",
            },
            {
                "heading": "Your check-in quest",
                "story": "Ask for one value and greet the traveller using it.",
                "example": 'city = input("Your city: ")\nprint("Welcome from", city)',
                "check": "Use input(), then print the saved value.",
            },
        ),
        "camp": {
            "mission": "Ask for a name and print a greeting using that name.",
            "starter_code": 'name = input("Name: ")\nprint("Hello", name)',
            "success_signals": ("input(", "print("),
        },
    },
    "variables": {
        "title": "Mall Mission · Variables",
        "world": "Fuel Station",
        "goal": "Keep a useful value in a named box.",
        "pages": (
            {
                "heading": "Name the box",
                "story": "A mall cashier labels each shelf so the right item can be found later.",
                "example": 'price = 50\nprint(price)',
                "check": "A variable name goes on the left of =.",
            },
            {
                "heading": "Update it",
                "story": "As an item enters a cart, the total changes. Python can replace the value in the same box.",
                "example": 'coins = 2\ncoins = coins + 1\nprint(coins)',
                "check": "Read the old value, calculate, then store the new one.",
            },
            {
                "heading": "Your mall quest",
                "story": "Save one item and one price, then show a receipt.",
                "example": 'item = "Notebook"\nprice = 40\nprint(item, price)',
                "check": "Use meaningful names such as item or price.",
            },
        ),
        "camp": {
            "mission": "Store a snack name and price, then print both values.",
            "starter_code": 'snack = "Sandwich"\nprice = 30\nprint(snack, price)',
            "success_signals": ("=", "print("),
        },
    },
    "conditions": {
        "title": "Castle Kingdom · Conditions",
        "world": "Castle Gate",
        "goal": "Make one decision with if and else.",
        "pages": (
            {
                "heading": "The gate asks a question",
                "story": "The castle guard opens the gate only when the rule is true.",
                "example": 'age = 18\nif age >= 18:\n    print("Gate open")',
                "check": "The colon after an if condition is required.",
            },
            {
                "heading": "Give both outcomes",
                "story": "A fair guard explains what happens when the rule is not true as well.",
                "example": 'if age >= 18:\n    print("Gate open")\nelse:\n    print("Gate locked")',
                "check": "Indent the lines inside if and else by four spaces.",
            },
            {
                "heading": "Your gate quest",
                "story": "Check one simple rule and print the correct result.",
                "example": 'has_pass = True\nif has_pass:\n    print("Enter")',
                "check": "Start with one condition before combining rules.",
            },
        ),
        "camp": {
            "mission": "Set age to 18. Print Adult when age is at least 18; otherwise print Child.",
            "starter_code": 'age = 18\nif age >= 18:\n    print("Adult")\nelse:\n    print("Child")',
            "success_signals": ("if ", ":"),
        },
    },
    "loops": {
        "title": "Loop Forest · Repetition",
        "world": "Treasure Collection",
        "goal": "Repeat a safe action a small number of times.",
        "pages": (
            {
                "heading": "Repeat without rewriting",
                "story": "In the forest, a lantern lights each step on the same trail.",
                "example": 'for step in range(3):\n    print("Step", step)',
                "check": "range(3) repeats three times: 0, 1, and 2.",
            },
            {
                "heading": "Loop body",
                "story": "Everything indented beneath for happens on every turn.",
                "example": 'for _ in range(3):\n    print("Collect a coin")',
                "check": "Use four spaces before the repeated action.",
            },
            {
                "heading": "Your trail quest",
                "story": "Collect three safe treasures, one at a time.",
                "example": 'for number in range(1, 4):\n    print("Treasure", number)',
                "check": "Start with a short range while learning.",
            },
        ),
        "camp": {
            "mission": "Print Practice three times with a for loop.",
            "starter_code": 'for _ in range(3):\n    print("Practice")',
            "success_signals": ("for ", "range("),
        },
    },
    "functions": {
        "title": "Function Factory · Reuse",
        "world": "Robot Repair",
        "goal": "Create one reusable helper function.",
        "pages": (
            {
                "heading": "Teach the robot a skill",
                "story": "Instead of repeating repair instructions, give the robot a named routine.",
                "example": 'def greet():\n    print("Hello")',
                "check": "def creates a function; the colon is required.",
            },
            {
                "heading": "Use the skill",
                "story": "A robot only performs its routine when you call its name.",
                "example": 'def greet():\n    print("Hello")\n\ngreet()',
                "check": "Calling greet() runs the function body.",
            },
            {
                "heading": "Your repair quest",
                "story": "Create a helper that prints a completed repair message, then call it.",
                "example": 'def repair():\n    print("Robot fixed")\n\nrepair()',
                "check": "Define first, call second.",
            },
        ),
        "camp": {
            "mission": "Define show_tip() that prints one tip, then call show_tip().",
            "starter_code": 'def show_tip():\n    print("Take one small step")\n\nshow_tip()',
            "success_signals": ("def ", "()"),
        },
    },
}


def canonical_stage(stage_key: str | None) -> str:
    """Return a supported, lower-case teaching stage; unknown stages use print."""
    candidate = (stage_key or "print").strip().lower()
    candidate = _ALIASES.get(candidate, candidate)
    return candidate if candidate in _LESSONS else "print"


def story_lesson(stage_key: str | None) -> dict[str, Any]:
    """Return the complete, serialisable story lesson for a PyQuest stage."""
    lesson = _LESSONS[canonical_stage(stage_key)]
    return {
        "stage": canonical_stage(stage_key),
        "title": lesson["title"],
        "world": lesson["world"],
        "goal": lesson["goal"],
        "pages": [dict(page) for page in lesson["pages"]],
        "page_count": len(lesson["pages"]),
    }


def story_page(stage_key: str | None, page_index: int) -> dict[str, Any]:
    """Get one story page while clamping an invalid page index safely."""
    lesson = story_lesson(stage_key)
    index = min(max(0, int(page_index)), lesson["page_count"] - 1)
    return {**lesson["pages"][index], "stage": lesson["stage"], "page": index + 1, "page_count": lesson["page_count"]}


def practice_camp(stage_key: str | None) -> dict[str, Any]:
    """Return a smaller, independently solvable practice task for the stage."""
    stage = canonical_stage(stage_key)
    camp = _LESSONS[stage]["camp"]
    return {"stage": stage, "title": f"{_LESSONS[stage]['world']} Practice Camp", **dict(camp)}


def _feedback_focus(feedback: str) -> str:
    text = (feedback or "").lower()
    if "indent" in text:
        return "Check the four spaces before code that belongs inside a block."
    if "syntax" in text or "invalid" in text:
        return "Read the punctuation carefully: quotes, parentheses, and colons all matter."
    if "nameerror" in text or "not defined" in text:
        return "Create the variable or function before using its name."
    if "input" in text:
        return "Start by collecting one value with input(), then print it to check it."
    return "Make the problem smaller: write one line, run it, and then add the next line."


def remediation_plan(stage_key: str | None, consecutive_failures: int, feedback: str = "") -> dict[str, Any]:
    """Choose a transparent, deterministic response to a learner's failures.

    At three failures the coordinator should pause the normal quest and offer
    the camp/review/continue options. It never locks a learner out.
    """
    failures = max(0, int(consecutive_failures))
    stage = canonical_stage(stage_key)
    if failures < 2:
        return {
            "action": "gentle_hint",
            "pause_quest": False,
            "message": _feedback_focus(feedback),
            "options": ("Keep trying",),
        }
    if failures < 3:
        return {
            "action": "guided_retry",
            "pause_quest": False,
            "message": "You are close. Compare your code with one tiny example, then retry the same quest.",
            "options": ("Show story example", "Keep trying"),
        }
    camp = practice_camp(stage)
    return {
        "action": "practice_camp",
        "pause_quest": True,
        "message": "Three attempts did not pass yet. Let’s rebuild this skill in a smaller practice camp—no penalty and no lost progress.",
        "focus": _feedback_focus(feedback),
        "camp": camp,
        "options": ("Enter Practice Camp", "Review concept story", "Keep trying"),
    }


def teaching_step(stage_key: str | None, consecutive_failures: int, feedback: str = "") -> dict[str, Any]:
    """Coordinator-friendly single response containing lesson and remediation data."""
    stage = canonical_stage(stage_key)
    return {
        "stage": stage,
        "lesson": story_lesson(stage),
        "remediation": remediation_plan(stage, consecutive_failures, feedback),
    }


__all__ = [
    "canonical_stage",
    "practice_camp",
    "remediation_plan",
    "story_lesson",
    "story_page",
    "teaching_step",
]
