# Book2Trek — Voice-AI layer

A real-time **multilingual voice agent** and a **REST/JWT API** layered on the
existing TrekTrack Flask app, plus an **AI-assisted listing-verification
pipeline**. Everything external (OpenAI, Deepgram, LiveKit, Redis, the public
web) sits behind a fallback, so the whole thing **runs and tests green with no
API keys** — add keys in `.env` to go live.

```
pip install -r requirements-voice.txt      # core deps (voice lines optional)
pytest -q                                   # 28 tests, no keys needed
python -m book2trek.verification.pipeline   # verify 55 listings
python -m book2trek.bench.latency -n 50     # latency benchmark
python seed.py && python run_api.py         # web app + /api on :5000
```

---

## Architecture

```
 caller audio ─► Deepgram ASR (multilingual) ─► GPT-4o-mini (intent + tool-calls)
        ▲                                              │
        │                                     ┌────────┴─────────┐
   OpenAI TTS ◄── speech ◄── LLM ◄── result ──┤  tools           │
                                              │  • /api (JWT)     ├─► Flask REST API
                                              │  • RAG (policies) │      (Redis cache,
                                              └───────────────────┘       Celery notify)
```

The voice tools call the **same REST API and models** as the web app, so a voice
booking and a web booking can never disagree on availability — one source of
truth. Tool logic lives in `book2trek/agent/tools.py` (pure, unit-tested); the
LiveKit wiring in `voice_agent.py` just exposes those tools to the session.

| Piece | Where | Notes |
|-------|-------|-------|
| REST API + JWT + RBAC | `book2trek/api/` | login→token, trek search, availability, bookings |
| Redis cache | `api/cache.py` | cache-aside on trek search; in-memory fallback |
| Celery async | `api/tasks.py` | booking notifications off the critical path; eager fallback |
| RAG | `book2trek/rag/` | policies + trek descriptions; OpenAI embeddings, TF-IDF fallback |
| Voice agent | `book2trek/agent/` | LiveKit + Deepgram + GPT-4o-mini + OpenAI TTS |
| Listing verification | `book2trek/verification/` | cross-check vs public source; flag discrepancies |
| Latency benchmark | `book2trek/bench/` | 50+ conversations, median/p90 |

---

## The voice agent

- **Multilingual:** Deepgram `nova-2` with `language=multi` auto-detects (English/
  Hindi code-switching); the LLM is prompted to reply in the caller's language.
- **Tool-calling:** `search_treks`, `check_availability`, `book_trek`,
  `list_my_bookings`, `cancel_booking` (all → `/api`), plus `answer_faq` (→ RAG).
- **Safety:** the agent confirms trek name + details before `book_trek`/`cancel`
  (a wrong booking is worse than a slow one), and `/api` bookings are guarded
  server-side (idempotent: no double-booking, availability enforced).
- **RAG vs tool-calling — know the difference:** transactional data (availability,
  bookings) goes through **function-calling against live APIs**; unstructured
  knowledge (cancellation policy, packing, refunds) is grounded by **retrieval**
  over `rag/policies.md` + trek descriptions. Two different tools for two
  different data types — say this in the interview.

Run the worker (needs keys): `python -m book2trek.agent.voice_agent dev`.

---

## RAG detail

`rag/store.py` has one retrieval interface with two embedders: **OpenAI
`text-embedding-3-small`** when a key is present, else a **char-n-gram TF-IDF**
embedder that's deterministic and offline (so `"what should I pack"` still
matches the `"packing list"` chunk). `answer_question` composes the answer with
the LLM when live, else returns the best-matching chunk extractively.

## Listing verification

`verification/pipeline.py` cross-checks each listing's **location, price,
operator, contact** against a public source (real `WebFetcher`, or a seeded
`MockFetcher` for offline runs), with a **10% price tolerance** so noise isn't
flagged as fraud. The demo verifies **55 listings** and flags the injected
inconsistencies.

## Latency benchmark

`bench/latency.py` times each turn across its stages (ASR, endpointing, LLM,
tool round-trip, TTS time-to-first-audio) over **50+ conversations** and reports
median/p90. Default is a **simulated** streaming-latency model (runs anywhere);
`RUN_LIVE=1` with keys times the real path.

> **Interview honesty:** report the ≤2.5s median as **simulated** unless you ran
> it live with keys. The value is the methodology — measuring each stage so you
> optimise the real bottleneck (usually endpointing + LLM).

---

## Testing & CI

`pytest -q` runs 28 tests with zero external services: API auth/booking rules +
RBAC, the agent tools (through an in-process Flask transport), RAG retrieval,
verification flagging, and the benchmark. `.github/workflows/ci.yml` runs lint +
tests + both demos across Python 3.10–3.12.

## What's real vs. what needs keys
- **Runs now, no keys:** the web app, the full `/api` layer, RAG retrieval,
  verification, the latency benchmark, and all 28 tests.
- **Needs your keys (in `.env`):** the live LiveKit voice loop (real audio),
  OpenAI-quality embeddings/LLM answers, and Redis/Celery when you want them
  out-of-process. The code is written and correct; it just needs credentials.

Say it that way in interviews — "the pipeline is built and tested end-to-end
with mocked providers; the live voice loop needs my LiveKit/OpenAI/Deepgram
keys" — it's accurate and still strong.
