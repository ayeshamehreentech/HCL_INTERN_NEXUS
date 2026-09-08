import json
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


def generate_learning_plan(
    topic,
    level,
    hours_per_day,
    days=7
):
    """
    Generate a structured learning plan.

    Returns:
        (data, error)
    """

    prompt = f"""
You are an expert technical learning planner.

Create a practical learning plan for:

Topic: {topic}
Level: {level}
Hours per day: {hours_per_day}
Duration: {days} days

Return ONLY valid JSON.

Use this structure:

{{
    "topic": "{topic}",
    "level": "{level}",
    "days": [
        {{
            "day": 1,
            "title": "...",
            "topics": ["...", "..."],
            "tasks": ["...", "..."],
            "hours": 2
        }}
    ],
    "final_project": "...",
    "interview_topics": ["...", "..."]
}}

Make the plan realistic for a student.
"""

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create structured technical "
                        "learning plans."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()

        # Remove markdown code fences if the model adds them
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(
                line for line in lines
                if line.strip() not in {"```", "```json"}
            ).strip()

        data = json.loads(content)

        return data, None

    except json.JSONDecodeError as e:
        return None, f"AI returned invalid JSON: {e}"

    except Exception as e:
        return None, str(e)