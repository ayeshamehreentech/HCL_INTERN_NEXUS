"""Private, transparent LangChain RAG for Helping Bot.

Portal notices/resources and a student's uploaded documents are retrieved at
answer time. Uploaded document text is durable in Supabase; the FAISS index is
derived and cached only for the running process. A lexical fallback keeps chat
available when the optional embedding model cannot load.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import re

from database.connection import get_connection
from database.helping_bot import list_helping_bot_documents


def _terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", (text or "").lower())}


def _portal_records() -> list[dict[str, str]]:
    queries = (
        ("notice", "SELECT title, message, created_at FROM notices ORDER BY created_at DESC"),
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


def _uploaded_records(user_id: int | None) -> list[dict[str, str]]:
    if not user_id:
        return []
    records = []
    for document in list_helping_bot_documents(user_id):
        text = str(document.get("text", "")).strip()
        if text:
            records.append({
                "label": "uploaded document · {}".format(document.get("filename", "document")),
                "text": text,
                "url": "",
            })
    return records


def _lexical_retrieve(question: str, records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    terms = _terms(question)
    if not terms:
        return []
    ranked = []
    for record in records:
        score = sum(2 for term in terms if term in record["text"].lower())
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in ranked[:limit]]


def _fingerprint(records: list[dict[str, str]]) -> str:
    material = "\n".join("{}\n{}".format(record["label"], record["text"]) for record in records)
    return hashlib.sha256(material.encode("utf-8", "ignore")).hexdigest()


@lru_cache(maxsize=12)
def _build_faiss_index(fingerprint: str, corpus: tuple[tuple[str, str, str], ...]):
    """Build a derived in-process LangChain/FAISS index from durable text."""
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    documents = [Document(page_content=text, metadata={"label": label, "url": url}) for label, text, url in corpus]
    chunks = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120).split_documents(documents)
    if not chunks:
        return None
    return FAISS.from_documents(chunks, FastEmbedEmbeddings(), normalize_L2=True)


def _langchain_retrieve(question: str, records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    if not records:
        return []
    corpus = tuple((record["label"], record["text"], record["url"]) for record in records)
    try:
        index = _build_faiss_index(_fingerprint(records), corpus)
        if index is None:
            return []
        matches = index.similarity_search(question, k=limit)
        return [
            {"label": str(match.metadata.get("label", "portal source")), "text": match.page_content, "url": str(match.metadata.get("url", ""))}
            for match in matches
        ]
    except Exception:
        return []


def retrieve_portal_context(question: str, user_id: int | None = None, limit: int = 4) -> tuple[str, list[str]]:
    """Retrieve grounded context from portal data and the student's own files."""
    records = _portal_records() + _uploaded_records(user_id)
    selected = _langchain_retrieve(question, records, limit) or _lexical_retrieve(question, records, limit)
    if not selected:
        return "", []
    context = "\n".join("- [{}] {}".format(record["label"], record["text"][:900]) for record in selected)
    sources = ["{}{}".format(record["label"].title(), " · " + record["url"] if record["url"] else "") for record in selected]
    return context, sources
