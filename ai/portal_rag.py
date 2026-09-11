"""Small, transparent retrieval layer for Helping Bot.

This is retrieval-augmented generation over the portal's durable Supabase data.
It uses deterministic lexical ranking rather than claiming an embedding/vector index
that the project does not yet operate.
"""
from __future__ import annotations

import re
from typing import Any

from database.connection import get_connection


def _terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", (text or "").lower())}


def _records() -> list[dict[str, str]]:
    """Load a small, safe knowledge corpus from existing permanent portal tables."""
    queries = (
        ("notices", "SELECT title, message, created_at FROM notices ORDER BY created_at DESC"),
        ("mentor resource", "SELECT title, topic, url, updated_at FROM resources ORDER BY updated_at DESC"),
    )
    records: list[dict[str, str]] = []
    conn = get_connection()
    try:
        for label, query in queries:
            try:
                for row in conn.execute(query).fetchall()[:30]:
                    item = dict(row)
                    text = " ".join(str(value) for key, value in item.items() if key != "url" and value)
                    if text:
                        records.append({"label": label, "text": text, "url": str(item.get("url", ""))})
            except Exception:
                continue
    finally:
        conn.close()
    return records


def retrieve_portal_context(question: str, limit: int = 4) -> tuple[str, list[str]]:
    """Return relevant grounded context and compact source labels for a bot answer."""
    terms = _terms(question)
    if not terms:
        return "", []
    ranked: list[tuple[int, dict[str, str]]] = []
    for record in _records():
        text = record["text"].lower()
        score = sum(2 if term in text else 0 for term in terms)
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:limit]
    if not selected:
        return "", []
    context = "\n".join("- [{}] {}".format(record["label"], record["text"][:700]) for _, record in selected)
    sources = ["{}{}".format(record["label"].title(), " · " + record["url"] if record["url"] else "") for _, record in selected]
    return context, sources
