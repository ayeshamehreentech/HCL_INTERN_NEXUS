"""Private, transparent LangChain RAG for Helping Bot.

Portal notices/resources and a student's uploaded documents are retrieved at
answer time. Uploads are embedded immediately; text, chunks and vectors are
durable in Supabase. FAISS is built from saved vectors and cached in process.
A lexical fallback keeps chat
available when the optional embedding model cannot load.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import logging
import re

from database.connection import get_connection
from database.helping_bot import list_helping_bot_documents


def _terms(text: str) -> set[str]:
    stopwords = {"the", "what", "which", "does", "this", "that", "with", "from", "and", "are", "for", "please"}
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", (text or "").lower())) - stopwords


def _chunks(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Use identical bounded passages for semantic and offline retrieval."""
    result = []
    for record in records:
        stored = record.get("vector_index")
        if stored and stored.get("model") == EMBEDDING_MODEL:
            result.extend({"label": record["label"], "url": record["url"],
                           "text": chunk, "embedding": vector}
                          for chunk, vector in zip(stored["chunks"], stored["vectors"]))
        else:
            result.extend(dict(record, text=record["text"][start:start + 900])
                          for start in range(0, len(record["text"]), 780))
    return result


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def _embeddings():
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    return FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)


def prepare_document(filename: str, text: str) -> dict:
    """Embed and build the vector store before declaring an upload ready."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or len(text) > 60_000:
        raise ValueError("Document must contain between 1 and 60,000 characters.")
    records = _chunks([{"label": "uploaded document · " + filename, "text": text, "url": ""}])
    chunks = [record["text"] for record in records]
    vectors = _embeddings().embed_documents(chunks)
    if len(vectors) != len(chunks) or not all(vectors):
        raise ValueError("Embedding generation did not complete.")
    for record, vector in zip(records, vectors):
        record["embedding"] = vector
    _build_faiss_index(_fingerprint(records), _corpus(records))
    return {"model": EMBEDDING_MODEL, "chunks": chunks, "vectors": vectors}


def _corpus(records):
    return tuple((record["label"], record["text"], record["url"],
                  tuple(record.get("embedding", ()))) for record in records)


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
                "vector_index": document.get("vector_index"),
            })
    return records


def _lexical_retrieve(question: str, records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    terms = _terms(question)
    if not terms:
        return []
    ranked = []
    for record in records:
        score = len(terms & _terms(record["text"]))
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in ranked[:limit]]


def _fingerprint(records: list[dict[str, str]]) -> str:
    material = "\n".join("{}\n{}".format(record["label"], record["text"]) for record in records)
    return hashlib.sha256(material.encode("utf-8", "ignore")).hexdigest()


@lru_cache(maxsize=12)
def _build_faiss_index(fingerprint: str, corpus: tuple):
    """Build a derived in-process LangChain/FAISS index from durable text."""
    from langchain_community.vectorstores import FAISS
    if not corpus:
        return None
    model = _embeddings()
    missing = [text for _, text, _, vector in corpus if not vector]
    generated = iter(model.embed_documents(missing) if missing else [])
    pairs = [(text, list(vector) if vector else next(generated)) for _, text, _, vector in corpus]
    return FAISS.from_embeddings(pairs, model,
        metadatas=[{"label": label, "url": url} for label, _, url, _ in corpus], normalize_L2=True)


def _langchain_retrieve(question: str, records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    if not records:
        return []
    corpus = _corpus(records)
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
        logging.getLogger(__name__).warning("Semantic retrieval unavailable; using lexical passages", exc_info=True)
        return []


def retrieve_portal_context(question: str, user_id: int | None = None, limit: int = 4) -> tuple[str, list[str]]:
    """Retrieve grounded context from portal data and the student's own files."""
    if limit <= 0:
        return "", []
    uploads = _uploaded_records(user_id)
    records = _chunks(_portal_records() + uploads)
    semantic = _langchain_retrieve(question, records, limit)
    lexical = _lexical_retrieve(question, records, limit)
    # Reciprocal rank fusion preserves exact matches as well as semantic matches.
    scores, passages = {}, {}
    for ranking in (semantic, lexical):
        for rank, record in enumerate(ranking, 1):
            key = (record["label"], record["text"])
            passages[key] = record
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    selected = [passages[key] for key in sorted(scores, key=scores.get, reverse=True)[:limit]]
    # Generic bibliographic queries rarely resemble the actual title. Supply
    # opening evidence explicitly instead of asking embeddings to guess it.
    if re.search(r"\b(title|authors?|doi)\b|\bwho wrote\b|\bname of (?:the |this )?(?:research )?(?:paper|document)\b", question, re.I):
        openings = [dict(record, text=record["text"][:1800]) for record in uploads]
    else:
        labels = {record["label"] for record in selected}
        openings = [dict(record, text=record["text"][:900]) for record in uploads if record["label"] in labels]
    # Include openings separately so the evidence is not displaced by top-k.
    selected = openings + [record for record in selected if not any(
        record["label"] == opening["label"] and record["text"] in opening["text"]
        for opening in openings)]
    if not selected:
        return "", []
    context = "\n".join("- [{}] {}".format(record["label"], record["text"]) for record in selected)
    sources = list(dict.fromkeys("{}{}".format(record["label"], " · " + record["url"] if record["url"] else "") for record in selected))
    return context, sources
