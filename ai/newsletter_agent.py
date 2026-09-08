import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


def get_client():
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not configured in .env"
        )

    return Groq(api_key=GROQ_API_KEY)


def generate_newsletter(
    title,
    topics,
    audience="students"
):
    """Generate a technical learning newsletter."""

    prompt = f"""
Create a professional technical newsletter.

Title:
{title}

Audience:
{audience}

Topics:
{topics}

The newsletter should contain:

1. Introduction
2. Key technical concepts
3. Why the concepts matter
4. Practical learning tips
5. Mini challenge
6. Interview questions
7. Final takeaway

Keep it suitable for GenAI/technology internship students.
"""

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a technical newsletter writer."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5
        )

        return response.choices[0].message.content.strip(), None

    except Exception as e:
        return None, str(e)


def format_notice(title, message):
    """Correct grammar and clarify a mentor's draft notice."""
    try:
        response = get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You edit school notices for grammar and clarity."},
                {"role": "user", "content": (
                    "Correct this notice. Return exactly two lines:\n"
                    "TITLE: ...\nMESSAGE: ...\n\n"
                    f"TITLE: {title}\nMESSAGE: {message}"
                )},
            ],
            temperature=0.1,
        )
        lines = response.choices[0].message.content.strip().splitlines()
        values = {
            line.split(":", 1)[0].strip().upper(): line.split(":", 1)[1].strip()
            for line in lines
            if ":" in line
        }
        return values.get("TITLE", title.strip()), values.get("MESSAGE", message.strip())
    except Exception:
        return title.strip(), message.strip()