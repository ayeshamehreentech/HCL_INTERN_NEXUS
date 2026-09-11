"""Supabase persistence for Helping Bot conversations."""
from datetime import datetime, timezone

from .connection import get_connection

NEW_CHAT_MARKER = "__HCL_NEW_CHAT__"


def _client():
    return get_connection().client


def list_helping_bot_messages(user_id, limit=200):
    """Return one student's permanent chat history in chronological order."""
    try:
        response = (_client().table("helping_bot_messages").select("id, role, content, created_at").eq("user_id", int(user_id)).order("created_at").limit(limit).execute())
        return response.data or []
    except Exception:
        return []


def save_helping_bot_message(user_id, role, content):
    """Persist one user or assistant message for one student only."""
    clean_content = str(content or "").strip()
    if not clean_content or role not in {"user", "assistant"}:
        return None
    try:
        response = _client().table("helping_bot_messages").insert({"user_id": int(user_id), "role": role, "content": clean_content, "created_at": datetime.now(timezone.utc).isoformat()}).execute()
        return (response.data or [None])[0]
    except Exception:
        return None


def start_helping_bot_chat(user_id):
    """Persist a private new-chat boundary without changing the Supabase schema."""
    return save_helping_bot_message(user_id, "assistant", NEW_CHAT_MARKER)


def clear_helping_bot_history(user_id):
    """Delete only the signed-in student's Helping Bot history."""
    try:
        _client().table("helping_bot_messages").delete().eq("user_id", int(user_id)).execute()
        return True
    except Exception:
        return False
