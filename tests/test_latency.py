"""Latency benchmark tests: runs 50+ simulated conversations, sane median."""
from book2trek.bench.latency import load_scenarios, run


def test_scenarios_present():
    s = load_scenarios()
    assert len(s) >= 15
    assert all("utterance" in x for x in s)


def test_benchmark_reaches_50_conversations():
    r = run(n_min=50, seed=1)
    assert r["conversations"] >= 50
    assert r["mode"] == "simulated"


def test_median_latency_reasonable():
    r = run(n_min=50, seed=1)
    # simulated model should land in a plausible sub-2.5s streaming range
    assert 0.5 < r["median_s"] <= 2.5
    assert r["p90_s"] >= r["median_s"]
