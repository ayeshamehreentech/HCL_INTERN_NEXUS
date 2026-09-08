import os
from io import BytesIO
from textwrap import wrap

from dotenv import load_dotenv
from groq import Groq
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from database.connection import get_connection
from database.reports import save_report
from .chains import build_performance_chain


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
INTERNSHIP_TITLE = os.getenv("INTERNSHIP_TITLE", "Gen AI Internship")
LAST_MIDDLEWARE_TRACE = []


def get_last_middleware_trace():
    """Return the most recent report-chain middleware events."""
    return list(LAST_MIDDLEWARE_TRACE)


def _collect_student_data(student_id, start_date, end_date):
    conn = get_connection()
    activity = conn.execute(
        "SELECT COALESCE(SUM(seconds), 0) AS seconds, COUNT(*) AS sessions "
        "FROM activity WHERE user_id = ? AND started_at BETWEEN ? AND ?",
        (student_id, start_date, end_date),
    ).fetchone()
    plans = conn.execute(
        "SELECT topic, level, days, created_at FROM learning_plans "
        "WHERE user_id = ? AND created_at BETWEEN ? AND ? ORDER BY created_at DESC",
        (student_id, start_date, end_date),
    ).fetchall()
    checklist = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(completed), 0) AS completed "
        "FROM learning_checklist WHERE user_id = ?",
        (student_id,),
    ).fetchone()
    meetings = conn.execute(
        "SELECT transcript, summary, created_at FROM meeting_transcriptions "
        "WHERE user_id = ? AND created_at BETWEEN ? AND ? ORDER BY created_at DESC",
        (student_id, start_date, end_date),
    ).fetchall()
    conn.close()
    return {
        "activity": dict(activity),
        "plans": [dict(row) for row in plans],
        "checklist": dict(checklist),
        "meetings": [dict(row) for row in meetings],
    }


def _generate_analysis(student, period, start_date, end_date, data):
    if not GROQ_API_KEY:
        return "Groq analysis unavailable because GROQ_API_KEY is missing."
    prompt = f"""
Write a concise mentor performance report for one internship student.
Internship: {INTERNSHIP_TITLE}
Student: {student['name']}
Internship start: {student.get('start_date') or 'Not recorded'}
Internship end: {student.get('end_date') or 'Not recorded'}
Report period: {period} ({start_date} to {end_date})

Measured data:
{data}

Use these headings exactly:
Overall Assessment
What Is Going Well
Where The Student Is Lagging
Meeting Insights
Recommended Mentor Actions
Next Review Focus

Use evidence from the measurements and meeting notes. Do not invent scores.
"""
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a careful internship performance analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def _make_pdf(student, period, start_date, end_date, content):
    buffer = BytesIO()
    document = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 48
    document.setTitle(f"{student['name']} - {period} Performance Report")
    document.setFont("Helvetica-Bold", 16)
    document.drawString(42, y, f"{INTERNSHIP_TITLE} Performance Report")
    y -= 26
    document.setFont("Helvetica", 10)
    for line in [
        f"Student: {student['name']}",
        f"Internship: {INTERNSHIP_TITLE}",
        f"Internship dates: {student.get('start_date') or 'N/A'} to {student.get('end_date') or 'N/A'}",
        f"Period: {period} ({start_date} to {end_date})",
    ]:
        document.drawString(42, y, line)
        y -= 16
    y -= 10
    document.setFont("Helvetica", 10)
    for paragraph in content.splitlines():
        for line in wrap(paragraph, 94) or [""]:
            if y < 48:
                document.showPage()
                y = height - 48
                document.setFont("Helvetica", 10)
            document.drawString(42, y, line)
            y -= 14
        y -= 4
    document.save()
    return buffer.getvalue()


def create_performance_report(student, mentor_id, period, start_date, end_date):
    global LAST_MIDDLEWARE_TRACE
    context = {
        "student": student,
        "mentor_id": mentor_id,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
    }

    def collect(payload):
        payload["signals"] = _collect_student_data(
            payload["student"]["id"],
            payload["start_date"],
            payload["end_date"],
        )
        return payload

    def analyze(payload):
        payload["analysis"] = _generate_analysis(
            payload["student"],
            payload["period"],
            payload["start_date"],
            payload["end_date"],
            payload["signals"],
        )
        return payload

    def render_pdf(payload):
        payload["pdf_data"] = _make_pdf(
            payload["student"],
            payload["period"],
            payload["start_date"],
            payload["end_date"],
            payload["analysis"],
        )
        return payload

    def persist(payload):
        payload["report_id"] = save_report(
            payload["student"]["id"],
            payload["mentor_id"],
            f"{payload['period']} Performance Report - {payload['student']['name']}",
            payload["analysis"],
            f"{payload['student']['name'].replace(' ', '_')}_"
            f"{payload['period'].lower()}_report.pdf",
            payload["pdf_data"],
        )
        return payload

    chain, trace = build_performance_chain(collect, analyze, render_pdf, persist)
    result = chain.invoke(context)
    result["middleware_trace"] = trace.events
    LAST_MIDDLEWARE_TRACE = trace.events
    return result["report_id"], result["analysis"]