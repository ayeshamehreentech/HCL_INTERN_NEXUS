"""User repository backed directly by Supabase's Data API."""
from datetime import datetime

from .connection import get_connection

_last_create_error = ""


def _client():
    return get_connection().client


def _normalise(row):
    if not row:
        return None
    user = dict(row)
    user["password_hash"] = user.get("password_hash") or user.get("password") or ""
    user["is_active"] = int(user.get("is_active", 1) or 0)
    user.setdefault("name", user.get("username") or user.get("email", ""))
    return user


def get_last_create_error():
    return _last_create_error


def create_user(name, email, role, password_hash, start_date=None, end_date=None):
    """Create an account with Supabase directly; no SQLite emulation is used."""
    global _last_create_error
    _last_create_error = ""
    email = email.strip().lower()
    record = {
        "name": name.strip(), "username": email, "email": email, "role": role,
        "password_hash": password_hash, "password": password_hash, "is_active": 1,
        "start_date": start_date, "end_date": end_date, "last_login": None,
        "created_at": datetime.now().isoformat(),
    }
    try:
        data = _client().table("users").insert(record).execute().data or []
        return data[0].get("id") if data else None
    except Exception as error:
        _last_create_error = str(error)[:240]
        print("Supabase user creation error:", _last_create_error)
        return None


def get_user(email):
    if not email:
        return None
    data = _client().table("users").select("*").eq("email", email.strip().lower()).limit(1).execute().data or []
    return _normalise(data[0]) if data else None


def get_user_by_id(user_id):
    data = _client().table("users").select("*").eq("id", user_id).limit(1).execute().data or []
    return _normalise(data[0]) if data else None


def get_user_by_email(email):
    return get_user(email)


def update_last_login(user_id):
    try:
        _client().table("users").update({"last_login": datetime.now().isoformat()}).eq("id", user_id).execute()
        return True
    except Exception:
        return False


def authenticate_user(email, password_hash):
    user = get_user(email)
    return user if user and user["is_active"] and user["password_hash"] == password_hash else None


def activate_user(user_id):
    _client().table("users").update({"is_active": 1}).eq("id", user_id).execute()
    return True


def deactivate_user(user_id):
    _client().table("users").update({"is_active": 0}).eq("id", user_id).execute()
    return True


def update_user(user_id, name=None, email=None, role=None, start_date=None, end_date=None):
    changes = {}
    if name is not None: changes["name"] = name.strip()
    if email is not None: changes["email"] = email.strip().lower()
    if role is not None: changes["role"] = role
    if start_date is not None: changes["start_date"] = str(start_date)
    if end_date is not None: changes["end_date"] = str(end_date)
    if changes: _client().table("users").update(changes).eq("id", user_id).execute()
    return True


def delete_user(user_id):
    _client().table("users").delete().eq("id", user_id).execute()
    return True


def list_users(role=None):
    request = _client().table("users").select("*").order("created_at", desc=True)
    if role: request = request.eq("role", role)
    return [_normalise(row) for row in (request.execute().data or [])]
