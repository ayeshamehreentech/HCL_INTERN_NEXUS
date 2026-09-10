"""Learning-plan and checklist persistence through Supabase Data API."""
import json
from datetime import datetime
from .connection import get_connection


def _client():
    return get_connection().client


def save_learning_plan(user_id, topic, level, hours_per_day, days, plan):
    record = {
        "user_id": user_id, "topic": topic, "level": level,
        "hours_per_day": int(hours_per_day), "days": int(days),
        "plan_json": json.dumps(plan), "created_at": datetime.now().isoformat(),
    }
    _client().table("learning_plans").insert(record).execute()


def get_latest_plan(user_id):
    rows = _client().table("learning_plans").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute().data or []
    if not rows:
        return None
    result = dict(rows[0])
    try:
        result["plan"] = json.loads(result.get("plan_json") or "{}")
    except (TypeError, ValueError):
        result["plan"] = {}
    return result


def save_checklist(user_id, topic, items):
    client = _client()
    client.table("learning_checklist").delete().eq("user_id", user_id).eq("topic", topic).execute()
    records = [{"user_id": user_id, "topic": topic, "item": item, "completed": 0, "created_at": datetime.now().isoformat()} for item in items]
    if records:
        client.table("learning_checklist").insert(records).execute()


def get_checklist(user_id, topic=None):
    request = _client().table("learning_checklist").select("*").eq("user_id", user_id).order("id")
    if topic is not None:
        request = request.eq("topic", topic)
    return request.execute().data or []


def set_checklist_item(item_id, completed):
    _client().table("learning_checklist").update({"completed": int(bool(completed))}).eq("id", item_id).execute()


def get_learning_progress(user_id):
    items = get_checklist(user_id)
    total = len(items)
    completed = sum(1 for item in items if item.get("completed"))
    return {"total": total, "completed": completed, "percentage": round((completed / total) * 100, 2) if total else 0}
