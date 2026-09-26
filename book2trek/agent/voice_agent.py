"""
LiveKit voice agent — the real-time voice loop.

    caller audio → Deepgram ASR (multilingual) → GPT-4o-mini (intent + tool
    calls) → tool hits the /api layer or RAG → OpenAI TTS → caller audio

Run a worker (needs LiveKit creds + OpenAI + Deepgram keys):
    python -m book2trek.agent.voice_agent dev

The LiveKit imports are guarded so the rest of the package (and CI) works
without livekit-agents installed; the tool logic lives in tools.py and is
tested independently of this file.
"""
from __future__ import annotations

import logging

from .. import config as C
from . import tools as T

log = logging.getLogger("book2trek.agent")

try:
    from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, function_tool
    from livekit.plugins import deepgram, openai, silero
    _HAS_LIVEKIT = True
except Exception:  # pragma: no cover - absent in CI
    _HAS_LIVEKIT = False
    def function_tool(fn=None, **_):   # no-op decorator so the class body imports
        return (lambda f: f)(fn) if fn else (lambda f: f)
    Agent = object  # type: ignore


INSTRUCTIONS = (
    "You are Book2Trek's voice concierge. Help users discover treks, check "
    "availability, book and cancel, and answer policy questions. Detect the "
    "user's language and reply in it. Keep replies short and natural for speech. "
    "ALWAYS confirm the trek name and details out loud before calling book_trek "
    "or cancel_booking — a wrong booking is worse than a slow one. Use answer_faq "
    "for policy/how-to questions, not your own guesses."
)


class TrekConcierge(Agent):  # pragma: no cover - requires LiveKit runtime
    """Wraps the pure tools in tools.py as LiveKit function tools."""

    def __init__(self, client: "T.ApiClient", kb) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self._client = client
        self._kb = kb

    @function_tool
    async def search_treks(self, query: str = "", location: str = "",
                           difficulty: str = "") -> str:
        return T.search_treks(self._client, query, location, difficulty)["speech"]

    @function_tool
    async def check_availability(self, trek_id: int) -> str:
        return T.check_availability(self._client, trek_id)["speech"]

    @function_tool
    async def book_trek(self, trek_id: int) -> str:
        return T.book_trek(self._client, trek_id)["speech"]

    @function_tool
    async def list_my_bookings(self) -> str:
        return T.list_my_bookings(self._client)["speech"]

    @function_tool
    async def cancel_booking(self, booking_id: int) -> str:
        return T.cancel_booking(self._client, booking_id)["speech"]

    @function_tool
    async def answer_faq(self, question: str) -> str:
        return T.answer_faq(self._kb, question)["speech"]


async def entrypoint(ctx: "JobContext") -> None:  # pragma: no cover - runtime
    """LiveKit job entrypoint: build the session and start the conversation."""
    from ..rag.knowledge import build_kb

    client = T.ApiClient(T.RequestsTransport(C.API_BASE_URL))
    # In production the caller's identity token would be minted per session;
    # here we authenticate a service/user account for booking on their behalf.
    client.login(C.__dict__.get("AGENT_USER_EMAIL", ""),
                 C.__dict__.get("AGENT_USER_PASSWORD", ""))
    kb = build_kb()  # policies; trek docs can be added from a warm API call

    session = AgentSession(
        stt=deepgram.STT(model=C.ASR_MODEL, language=C.ASR_LANGUAGE),
        llm=openai.LLM(model=C.LLM_MODEL),
        tts=openai.TTS(voice=C.TTS_VOICE),
        vad=silero.VAD.load(),          # voice-activity detection / endpointing
    )
    await session.start(agent=TrekConcierge(client, kb), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user and ask how you can help with their trek.")


def main() -> None:  # pragma: no cover - runtime
    if not _HAS_LIVEKIT:
        raise SystemExit(
            "livekit-agents not installed. `pip install -r requirements-voice.txt` "
            "and set LiveKit/OpenAI/Deepgram keys in .env to run the voice worker."
        )
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":  # pragma: no cover
    main()
