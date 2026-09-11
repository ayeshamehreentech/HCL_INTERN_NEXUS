"""Supabase persistence for Helping Bot conversations and memory snapshots."""
import json
from datetime import datetime, timezone

from .connection import get_connection

NEW_CHAT_MARKER = "__HCL_NEW_CHAT__"
MEMORY_PREFIX = "__HCL_BOT_MEMORY__:"


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


def save_helping_bot_memory(user_id, kind, payload):
    """Persist a private memory/profile record using the existing Supabase table.

    Keeping these records in the student's message stream avoids a breaking schema
    migration while preserving user isolation and permanent storage.
    """
    if kind not in {"profile", "working", "summary"}:
        return None
    record = {
        "kind": kind,
        "payload": payload,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    return save_helping_bot_message(
        user_id,
        "assistant",
        MEMORY_PREFIX + json.dumps(record, ensure_ascii=False),
    )


def latest_helping_bot_memory(rows, kind):
    """Read the newest permanent record of one memory type from loaded rows."""
    for row in reversed(rows):
        content = str(row.get("content", ""))
        if not content.startswith(MEMORY_PREFIX):
            continue
        try:
            record = json.loads(content[len(MEMORY_PREFIX):])
            if record.get("kind") == kind:
                return record
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def is_helping_bot_internal_record(row):
    """Hide control/memory records from the conversational transcript."""
    content = str(row.get("content", ""))
    return content == NEW_CHAT_MARKER or content.startswith(MEMORY_PREFIX)


def clear_helping_bot_history(user_id):
    """Delete only the signed-in student's Helping Bot history."""
    try:
        _client().table("helping_bot_messages").delete().eq("user_id", int(user_id)).execute()
        return True
    except Exception:
        return False
