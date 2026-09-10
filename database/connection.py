"""Supabase Data API adapter for the HCL Intern Nexus portal."""
import os
import re

from supabase import create_client

TABLES = {"users", "activity", "meetings", "meeting_transcriptions", "notices", "resources", "resource_history", "user_resources", "private_messages", "coding_lab_attempts", "learning_plans", "learning_checklist", "formulas", "student_reports", "deletion_requests"}
USER_COLUMNS = ["id", "name", "username", "email", "role", "password_hash", "password", "is_active", "start_date", "end_date", "last_login", "created_at"]


def _secret(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def _client():
    url = _secret("SUPABASE_URL") or "https://bmfpzfrzrvbkcmlvopoo.supabase.co"
    key = _secret("SUPABASE_SECRET_KEY")
    if not key:
        raise RuntimeError("Supabase is not configured. Add SUPABASE_SECRET_KEY to Streamlit secrets.")
    return create_client(url, key)


def _table(sql):
    found = re.search(r"(?:FROM|INTO|UPDATE|DELETE\s+FROM)\s+([a-z_]+)", sql, re.I)
    if not found or found.group(1) not in TABLES:
        raise ValueError("Unsupported database query")
    return found.group(1)


def _value(token, values):
    token = token.strip()
    if token == "%s":
        return next(values)
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    if token in ("0", "1"):
        return int(token)
    return token


def _where(rows, sql, parameters):
    match = re.search(r"\bWHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)", sql, re.I | re.S)
    if not match:
        return rows
    text = re.sub(r"\b[a-z_]+\.", "", match.group(1), flags=re.I)
    text = re.sub(r"\((?!lower\()", "", text, flags=re.I)
    text = re.sub(r"(?<!\w)\)", "", text)
    values = iter(parameters or ())
    groups = re.split(r"\s+OR\s+", text, flags=re.I)
    tests = []
    for group in groups:
        rules = []
        for piece in re.split(r"\s+AND\s+", group, flags=re.I):
            piece = piece.strip()
            lower = re.match(r"lower\((\w+)\)\s*=\s*lower\(%s\)", piece, re.I)
            lower_literal = re.match(r"lower\((\w+)\)\s*=\s*'?([^']+?)'?\s*$", piece, re.I)
            equal = re.match(r"(\w+)\s*=\s*%s", piece, re.I)
            literal = re.match(r"(\w+)\s*=\s*('?\w+'?|[01])", piece, re.I)
            null = re.match(r"(\w+)\s+IS\s+NULL", piece, re.I)
            if lower:
                key, value = lower.group(1), next(values)
                rules.append(lambda row, k=key, v=value: str(row.get(k, "")).lower() == str(v).lower())
            elif lower_literal:
                key, value = lower_literal.group(1), lower_literal.group(2)
                rules.append(lambda row, k=key, v=value: str(row.get(k, "")).lower() == v.lower())
            elif equal:
                key, value = equal.group(1), next(values)
                rules.append(lambda row, k=key, v=value: row.get(k) == v)
            elif literal:
                key, value = literal.group(1), literal.group(2).strip("'")
                value = int(value) if value in ("0", "1") else value
                rules.append(lambda row, k=key, v=value: row.get(k) == v)
            elif null:
                key = null.group(1)
                rules.append(lambda row, k=key: row.get(k) is None)
        tests.append(rules)
    return [row for row in rows if any(all(rule(row) for rule in group) for group in tests)]


class Cursor:
    def __init__(self, client):
        self.client, self.rows, self.lastrowid = client, [], None

    def execute(self, statement, parameters=None):
        sql = " ".join(statement.strip().replace("?", "%s").split())
        if sql.upper().startswith("PRAGMA TABLE_INFO("):
            self.rows = [{"name": item} for item in USER_COLUMNS]
            return self
        table = _table(sql)
        upper = sql.upper()
        if upper.startswith("SELECT"):
            response = self.client.table(table).select("*").execute()
            rows = _where(response.data or [], sql, parameters)
            if "LEFT JOIN USERS" in upper:
                users = {item["id"]: item for item in self.client.table("users").select("*").execute().data}
                rows = [{**row, "name": users.get(row.get("user_id"), {}).get("name"), "email": users.get(row.get("user_id"), {}).get("email")} for row in rows]
            if "COUNT(DISTINCT QUESTION_KEY)" in upper:
                self.rows = [{"total": len({row.get("question_key") for row in rows})}]
            elif "COUNT(*) AS COUNT" in upper:
                self.rows = [{"count": len(rows)}]
            else:
                order = re.search(r"ORDER BY\s+(\w+)(?:\s+(DESC|ASC))?", sql, re.I)
                if order:
                    rows.sort(key=lambda row: str(row.get(order.group(1), "")), reverse=(order.group(2) or "").upper() == "DESC")
                limit = re.search(r"LIMIT\s+(\d+)", sql, re.I)
                parameter_limit = re.search(r"LIMIT\s+%s", sql, re.I)
                if limit:
                    self.rows = rows[:int(limit.group(1))]
                elif parameter_limit and parameters:
                    self.rows = rows[:int(parameters[-1])]
                else:
                    self.rows = rows
            return self
        if upper.startswith("INSERT"):
            match = re.search(r"INSERT INTO\s+\w+\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)", sql, re.I)
            columns = [item.strip() for item in match.group(1).split(",")]
            values = iter(parameters or ())
            record = {key: _value(token, values) for key, token in zip(columns, match.group(2).split(","))}
            conflict = re.search(r"ON CONFLICT\s*\(([^)]+)\)", sql, re.I)
            response = self.client.table(table).upsert(record, on_conflict=conflict.group(1) if conflict else None).execute() if conflict else self.client.table(table).insert(record).execute()
            data = response.data or []
            self.lastrowid = data[0].get("id") if data else None
            return self
        if upper.startswith("UPDATE"):
            set_match = re.search(r"SET\s+(.+?)\s+WHERE", sql, re.I)
            values = iter(parameters or ())
            updates = {}
            for item in set_match.group(1).split(","):
                key, token = item.split("=", 1)
                updates[key.strip()] = _value(token, values)
            targets = _where(self.client.table(table).select("*").execute().data or [], "SELECT * FROM {} WHERE {}".format(table, sql.split("WHERE", 1)[1]), list(values))
            for row in targets:
                self.client.table(table).update(updates).eq("id", row["id"]).execute()
            return self
        if upper.startswith("DELETE"):
            targets = _where(self.client.table(table).select("*").execute().data or [], "SELECT * FROM {} WHERE {}".format(table, sql.split("WHERE", 1)[1]), parameters)
            for row in targets:
                self.client.table(table).delete().eq("id", row["id"]).execute()
            return self
        raise ValueError("Unsupported database query")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.client = _client()

    def cursor(self):
        return Cursor(self.client)

    def execute(self, statement, parameters=None):
        return self.cursor().execute(statement, parameters)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def get_connection():
    return Connection()


def init_db():
    """Verify the required Supabase table without creating local SQLite data."""
    try:
        _client().table("users").select("id").limit(1).execute()
    except Exception as error:
        raise RuntimeError("Supabase is unavailable. Check SUPABASE_URL, SUPABASE_SECRET_KEY, and run database/schema.sql in the Supabase SQL Editor.") from error
