"""RAG tests: retrieval returns the right chunk, grounded and offline."""
from book2trek.rag.knowledge import answer_question, build_kb, trek_docs
from book2trek.rag.store import Doc, VectorStore


def test_kb_builds_from_policies():
    kb = build_kb()
    assert len(kb.docs) >= 5


def test_retrieval_finds_cancellation():
    kb = build_kb()
    res = answer_question(kb, "how do refunds and cancellations work")
    assert "cancel" in res["answer"].lower() or "refund" in res["answer"].lower()
    assert res["sources"]


def test_trek_docs_from_dicts():
    docs = trek_docs([{"id": 9, "name": "Roopkund", "location": "Uttarakhand",
                       "difficulty": "Hard", "duration_days": 6,
                       "description": "glacial lake"}])
    assert docs[0].meta["trek_id"] == 9
    assert "Roopkund" in docs[0].text


def test_vector_store_ranks_relevant_first():
    docs = [Doc("a", "packing list shoes water sunscreen headlamp"),
            Doc("b", "cancellation refund policy seven days"),
            Doc("c", "group size slots fully booked")]
    vs = VectorStore().index(docs)
    top = vs.query("what should I pack", k=1)
    assert top[0][0].id == "a"
