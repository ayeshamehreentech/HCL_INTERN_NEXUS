"""Supabase persistence for student and mentor meetings."""
from datetime import datetime
from .connection import get_connection


def _client(): return get_connection().client

def save_meeting(student_id, mentor_id, title, meeting_date, meeting_time, meeting_link=""):
    data = _client().table("meetings").insert({"student_id":student_id,"mentor_id":mentor_id,"title":title,"meeting_date":str(meeting_date),"meeting_time":meeting_time,"meeting_link":meeting_link,"status":"scheduled","created_at":datetime.now().isoformat()}).execute().data or []
    return data[0].get("id") if data else None

def save_recurring_meetings(student_id, mentor_id, title, start_date, meeting_time, meeting_link, occurrences=12):
    from datetime import timedelta
    day = start_date
    while day.weekday() not in (1, 3): day += timedelta(days=1)
    ids = []
    while len(ids) < occurrences:
        ids.append(save_meeting(student_id, mentor_id, title, day, meeting_time, meeting_link))
        day += timedelta(days=2 if day.weekday() == 1 else 5)
    return ids

def list_meetings(user_id, role="student"):
    column = "mentor_id" if role == "mentor" else "student_id"
    return _client().table("meetings").select("*").eq(column, user_id).order("meeting_date").execute().data or []

def get_meeting(meeting_id):
    rows = _client().table("meetings").select("*").eq("id", meeting_id).limit(1).execute().data or []
    return rows[0] if rows else None

def update_meeting(meeting_id, title, meeting_date, meeting_time, meeting_link):
    _client().table("meetings").update({"title":title.strip(),"meeting_date":str(meeting_date),"meeting_time":meeting_time,"meeting_link":meeting_link.strip()}).eq("id", meeting_id).execute()

def mark_joined(meeting_id): _client().table("meetings").update({"status":"joined"}).eq("id", meeting_id).execute()
def cancel_meeting(meeting_id): _client().table("meetings").update({"status":"cancelled"}).eq("id", meeting_id).execute()
def save_meeting_transcription(user_id, transcript, summary):
    data = _client().table("meeting_transcriptions").insert({"user_id":user_id,"transcript":transcript,"summary":summary,"created_at":datetime.now().isoformat()}).execute().data or []
    return data[0].get("id") if data else None
