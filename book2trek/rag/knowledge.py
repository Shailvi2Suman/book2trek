"""
Build the RAG knowledge base and answer questions from it.

The KB has two sources:
  1. Policy / FAQ text (policies.md), chunked by section.
  2. Live trek descriptions from the DB (so "tell me about the Roopkund trek"
     is answered from real data, not the model's imagination).

answer_question() retrieves the top chunks and composes an answer — via the LLM
when a key is present, else an extractive fallback (return the best chunk) so it
still works offline. This is the difference from plain tool-calling: unstructured
knowledge (policies, descriptions) is grounded by retrieval, not fetched by API.
"""
from __future__ import annotations

import pathlib

from .. import config as C
from .store import Doc, VectorStore

_POLICIES = pathlib.Path(__file__).with_name("policies.md")


def _chunk_policies() -> list[Doc]:
    text = _POLICIES.read_text(encoding="utf-8")
    docs, current, title = [], [], "intro"
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                docs.append(Doc(id=f"policy:{title}", text="\n".join(current).strip(),
                                meta={"source": "policy", "title": title}))
            title = line[3:].strip()
            current = [line[3:].strip()]
        else:
            current.append(line)
    if current:
        docs.append(Doc(id=f"policy:{title}", text="\n".join(current).strip(),
                        meta={"source": "policy", "title": title}))
    return [d for d in docs if d.text]


def trek_docs(treks) -> list[Doc]:
    """Turn ORM Trek rows (or dicts) into retrievable docs."""
    out = []
    for t in treks:
        g = (lambda k: t.get(k)) if isinstance(t, dict) else (lambda k: getattr(t, k, None))
        text = (f"{g('name')} — a {g('difficulty')} trek in {g('location')}, "
                f"{g('duration_days')} days. {g('description') or ''}").strip()
        out.append(Doc(id=f"trek:{g('id')}", text=text,
                       meta={"source": "trek", "trek_id": g("id"), "name": g("name")}))
    return out


def build_kb(treks=None) -> VectorStore:
    docs = _chunk_policies() + (trek_docs(treks) if treks else [])
    return VectorStore().index(docs)


def answer_question(kb: VectorStore, question: str, k: int = 3) -> dict:
    hits = kb.query(question, k=k)
    if not hits:
        return {"answer": "I don't have information on that yet.", "sources": []}
    context = "\n\n".join(f"[{d.meta.get('title') or d.meta.get('name')}] {d.text}"
                          for d, _ in hits)
    sources = [d.id for d, _ in hits]

    if C.live_mode():  # pragma: no cover - needs a live key
        from openai import OpenAI
        client = OpenAI(api_key=C.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=C.LLM_MODEL,
            messages=[
                {"role": "system", "content": "Answer ONLY from the context. "
                 "If it isn't there, say you don't know. Be concise."},
                {"role": "user", "content": f"Context:\n{context}\n\nQ: {question}"},
            ],
            temperature=0,
        )
        return {"answer": resp.choices[0].message.content.strip(), "sources": sources}

    # Offline extractive fallback: return the best-matching chunk.
    best_doc, best_score = hits[0]
    return {"answer": best_doc.text, "sources": sources, "score": best_score}
