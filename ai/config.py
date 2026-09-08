import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_setting(name, default=""):
    """Read deployment secrets first from environment, then Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value.strip()

    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value else default
    except Exception:
        return default


def get_groq_api_key():
    return get_setting("GROQ_API_KEY")


def get_groq_model():
    return get_setting("GROQ_MODEL", "openai/gpt-oss-120b")
