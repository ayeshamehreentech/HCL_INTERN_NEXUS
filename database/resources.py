"""Resource and video-progress persistence through Supabase Data API."""
from datetime import datetime
from .connection import get_connection


def _client():
    return get_connection().client


def list_resources(topic=None):
    request = _client().table("resources").select("*").order("updated_at", desc=True)
    if topic: request = request.eq("topic", topic.strip())
    return request.execute().data or []


def add_resource(topic, title, url, resource_type, created_by=None):
    now = datetime.now().isoformat()
    data = _client().table("resources").insert({"topic":topic.strip(),"title":title.strip(),"url":url.strip(),"resource_type":resource_type,"created_by":created_by,"created_at":now,"updated_at":now}).execute().data or []
    return data[0].get("id") if data else None


def update_resource(resource_id, topic, title, url, resource_type):
    _client().table("resources").update({"topic":topic.strip(),"title":title.strip(),"url":url.strip(),"resource_type":resource_type,"updated_at":datetime.now().isoformat()}).eq("id", resource_id).execute()


def delete_resource(resource_id):
    _client().table("resources").delete().eq("id", resource_id).execute()


def save_topic_history(user_id, topic):
    client, now = _client(), datetime.now().isoformat()
    rows = client.table("resource_history").select("id").eq("user_id", user_id).eq("topic", topic.strip()).limit(1).execute().data or []
    if rows: client.table("resource_history").update({"opened_at":now}).eq("id", rows[0]["id"]).execute()
    else: client.table("resource_history").insert({"user_id":user_id,"topic":topic.strip(),"opened_at":now}).execute()


def list_topic_history(user_id):
    return _client().table("resource_history").select("topic,opened_at").eq("user_id", user_id).order("opened_at", desc=True).execute().data or []


def get_user_resource(user_id, resource_key):
    rows = _client().table("user_resources").select("*").eq("user_id", user_id).eq("resource_key", resource_key).limit(1).execute().data or []
    return rows[0] if rows else None


def _store_resource(user_id, resource_key, data):
    client = _client(); existing = get_user_resource(user_id, resource_key)
    if existing: client.table("user_resources").update(data).eq("id", existing["id"]).execute()
    else: client.table("user_resources").insert({"user_id":user_id,"resource_key":resource_key, **data}).execute()


def save_user_resource(user_id, resource_key, resource_type, title, url, topic):
    existing = get_user_resource(user_id, resource_key) or {}
    _store_resource(user_id, resource_key, {"resource_type":resource_type,"title":title,"url":url,"topic":topic,"saved":1,"viewed":existing.get("viewed",0),"progress_seconds":existing.get("progress_seconds",0),"completed":existing.get("completed",0)})


def save_video_progress(user_id, resource_key, title, url, topic, seconds, completed=False):
    existing = get_user_resource(user_id, resource_key) or {}
    _store_resource(user_id, resource_key, {"resource_type":"video","title":title,"url":url,"topic":topic,"saved":existing.get("saved",0),"viewed":1,"last_viewed_at":datetime.now().isoformat(),"progress_seconds":int(seconds),"completed":int(bool(completed))})


def mark_resource_viewed(user_id, resource_key, resource_type, title, url, topic):
    save_video_progress(user_id, resource_key, title, url, topic, 0, False)


def list_saved_resources(user_id):
    return _client().table("user_resources").select("*").eq("user_id", user_id).eq("saved", 1).order("last_viewed_at", desc=True).execute().data or []
