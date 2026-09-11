"""LangChain Deep Agents services for guided learning and HCLTech discovery."""
from functools import lru_cache

from deepagents import create_deep_agent
from langchain_groq import ChatGroq

from .config import get_groq_api_key, get_groq_model


def web_learning_search(query: str) -> str:
    """Find concise educational web guidance for a programming concept."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except Exception:
        return "Web search is unavailable. Explain the concept from first principles."


def hcl_reference(question: str) -> str:
    """Provide trusted HCLTech context for the About HCLTech guide."""
    return ("HCL was founded in 1976 by Shiv Nadar. HCLTech is a global technology "
            "company. For current details, use https://www.hcltech.com. Question: " + question)


def _content(result) -> str:
    messages = result.get("messages", [])
    if not messages:
        return "I could not produce guidance yet. Try one smaller step."
    content = messages[-1].content
    return " ".join(str(item) for item in content) if isinstance(content, list) else str(content)


@lru_cache(maxsize=1)
def coding_tutor_agent():
    """Build a real Deep Agent with a research subagent for Python coaching."""
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for Deep Agent coaching.")
    model = ChatGroq(model=get_groq_model(), api_key=api_key, temperature=0.2)
    researcher = {
        "name": "python_learning_researcher",
        "description": "Find a short beginner-friendly explanation for a Python concept.",
        "system_prompt": "Research one Python concept and return a concise learning explanation.",
        "tools": [web_learning_search],
    }
    return create_deep_agent(
        model=model,
        tools=[web_learning_search],
        subagents=[researcher],
        system_prompt=("You are a patient Python tutor. Plan before answering, inspect the "
                       "student attempt, identify one next improvement, and explain why. "
                       "Do not give a full final solution unless asked after a genuine attempt."),
    )


def coach_python(question: str, concept: str, code: str) -> str:
    """Use the Deep Agent to provide adaptive non-spoiler coaching."""
    prompt = ("Student challenge: " + question + "\nCore concept: " + concept +
              "\nStudent code:\n" + (code or "(no code yet)") +
              "\nGive a short plan, the first missing logical step, and one next action.")
    return _content(coding_tutor_agent().invoke({"messages": [{"role": "user", "content": prompt}]}))


@lru_cache(maxsize=1)
def hcl_guide_agent():
    """Build a Deep Agent for the About HCLTech learning experience."""
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for the HCLTech Deep Agent.")
    model = ChatGroq(model=get_groq_model(), api_key=api_key, temperature=0.2)
    return create_deep_agent(
        model=model,
        tools=[hcl_reference],
        system_prompt=("You are the HCLTech internship guide. Use the reference tool, distinguish "
                       "facts from suggestions, and connect HCLTech values to an intern project."),
    )


def answer_hcl_question(question: str) -> str:
    return _content(hcl_guide_agent().invoke({"messages": [{"role": "user", "content": question}]}))
