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


def mentor_ai_response(
    question,
    student_context=""
):
    """Generate an AI response for a mentor."""

    prompt = f"""
You are an AI assistant for a technical mentor.

Student context:
{student_context}

Mentor question:
{question}

Give a practical and professional answer.

Consider:
- Student progress
- Technical learning
- Weak areas
- Recommended next steps
- Interview preparation

Do not invent student information that is not provided.
"""

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful mentor assistant."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4
        )

        return response.choices[0].message.content.strip(), None

    except Exception as e:
        return None, str(e)


def generate_student_feedback(
    student_name,
    progress,
    completed_topics,
    pending_topics
):
    """Generate mentor feedback for a student."""

    prompt = f"""
Create concise mentor feedback for this student.

Student: {student_name}
Progress: {progress}%

Completed topics:
{completed_topics}

Pending topics:
{pending_topics}

Give:
1. What the student is doing well
2. What needs improvement
3. Recommended next steps
4. One interview preparation suggestion

Keep it constructive and practical.
"""

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a technical mentor."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4
        )

        return response.choices[0].message.content.strip(), None

    except Exception as e:
        return None, str(e)