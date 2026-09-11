"""Supabase-backed mentor and student reports."""
from datetime import datetime
from .connection import get_connection


def _client():
    return get_connection().client


def list_reports(student_id):
    return _client().table("student_reports").select("*").eq("student_id", student_id).order("updated_at", desc=True).execute().data or []


def save_report(student_id, mentor_id, title, content, attachment_name=None, attachment_data=None):
    """Store report text safely. Binary uploads require Supabase Storage, not JSON rows."""
    record = {
        "student_id": student_id,
        "mentor_id": mentor_id,
        "title": (title or "Student report").strip(),
        "content": (content or "").strip(),
        "attachment_name": attachment_name,
        "attachment_data": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    rows = _client().table("student_reports").insert(record).execute().data or []
    return rows[0].get("id") if rows else None


def get_report(report_id):
    rows = _client().table("student_reports").select("*").eq("id", report_id).limit(1).execute().data or []
    return rows[0] if rows else None
