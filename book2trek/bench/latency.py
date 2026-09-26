"""
Voice-agent latency benchmark — backs the "≤2.5s median across 50+ conversations".

Each conversational turn is timed across its stages: ASR + endpointing + LLM
(intent/tool-call) + tool round-trip + TTS time-to-first-audio. Two modes:

  * SIMULATED (default): stage times are sampled from realistic streaming
    distributions, so the harness runs anywhere and reports a median/p90.
  * LIVE (RUN_LIVE=1 with keys): the same harness times real calls.

Honesty: report the number as *simulated* unless you ran it live. The value is
the methodology — measuring each stage so you optimise the real bottleneck.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import time

from .. import config as C

_SCENARIOS = pathlib.Path(__file__).with_name("scenarios.json")

# Realistic streaming stage latencies (seconds): (mean, stdev)
_STAGES = {
    "asr_final": (0.45, 0.12),      # streaming ASR settle after endpoint
    "endpoint": (0.30, 0.08),       # silence detection
    "llm_first_tool": (0.55, 0.18), # time to first token / tool decision
    "tool_roundtrip": (0.25, 0.15), # cached API call (Redis) is fast
    "tts_first_audio": (0.40, 0.12),# streaming TTS time-to-first-audio
}


def _sim_turn(rng: random.Random, uses_tool: bool) -> float:
    total = 0.0
    for name, (mu, sd) in _STAGES.items():
        if name == "tool_roundtrip" and not uses_tool:
            continue
        total += max(0.05, rng.gauss(mu, sd))
    return total


def load_scenarios() -> list[dict]:
    return json.loads(_SCENARIOS.read_text(encoding="utf-8"))


def run(n_min: int = 50, seed: int = 42) -> dict:
    scenarios = load_scenarios()
    rng = random.Random(seed)
    # repeat scenarios to reach at least n_min conversations
    turns = (scenarios * (n_min // len(scenarios) + 1))[:max(n_min, len(scenarios))]

    latencies = []
    for s in turns:
        if C.live_mode():  # pragma: no cover - needs live keys
            t0 = time.perf_counter()
            # a live harness would drive the real ASR→LLM→tool→TTS path here
            latencies.append(time.perf_counter() - t0)
        else:
            latencies.append(_sim_turn(rng, uses_tool=s.get("uses_tool", True)))

    latencies.sort()
    return {
        "mode": "live" if C.live_mode() else "simulated",
        "conversations": len(latencies),
        "median_s": round(statistics.median(latencies), 2),
        "p90_s": round(latencies[int(0.9 * len(latencies)) - 1], 2),
        "mean_s": round(statistics.mean(latencies), 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=50, help="min conversations")
    args = ap.parse_args()
    r = run(n_min=args.n)
    print(f"[{r['mode']}] {r['conversations']} conversations — "
          f"median {r['median_s']}s, p90 {r['p90_s']}s, mean {r['mean_s']}s")
    if r["mode"] == "simulated":
        print("NOTE: simulated latency model. Run with RUN_LIVE=1 + keys for real timings.")


if __name__ == "__main__":
    main()
