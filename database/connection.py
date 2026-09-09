"""Supabase PostgreSQL persistence for HCL Intern Nexus."""
import os
import re
from urllib.parse import quote_plus

import psycopg2
from psycopg2.extras import RealDictCursor


def _secret(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def _database_url():
    url = _secret("SUPABASE_DB_URL")
    if url:
        return url
    host = _secret("SUPABASE_DB_HOST")
    password = _secret("SUPABASE_DB_PASSWORD")
    if host and password:
        return "postgresql://postgres:{}@{}:5432/postgres".format(quote_plus(password), host)
    raise RuntimeError("Supabase is not configured. Add SUPABASE_DB_URL to Streamlit secrets.")


def _translate(statement):
    sql = statement.strip()
    if sql.upper().startswith("PRAGMA TABLE_INFO("):
        table = sql.split("(", 1)[1].split(")", 1)[0].strip(" '\"")
        return "SELECT column_name AS name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s", (table,)
    return sql.replace("?", "%s"), None


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, statement, parameters=None):
        sql, generated = _translate(statement)
        values = generated if generated is not None else parameters
        upper = sql.lstrip().upper()
        needs_id = upper.startswith("INSERT INTO") and " RETURNING " not in upper
        if needs_id:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        self._cursor.execute(sql, values)
        if needs_id:
            row = self._cursor.fetchone()
            self.lastrowid = row["id"] if row else None
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class Connection:
    def __init__(self):
        self._conn = psycopg2.connect(_database_url(), cursor_factory=RealDictCursor, sslmode="require")

    def cursor(self):
        return Cursor(self._conn.cursor())

    def execute(self, statement, parameters=None):
        return self.cursor().execute(statement, parameters)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_connection():
    """Return a durable Supabase PostgreSQL connection."""
    return Connection()


def init_db():
    """Verify that the Supabase schema is reachable."""
    conn = get_connection()
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
