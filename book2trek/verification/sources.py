"""
Public-source fetchers for listing verification.

A listing is cross-checked against an external "public source" (operator site,
directory, maps). That source is reached through a pluggable fetcher:
  * WebFetcher  — real HTTP lookups (best-effort; network may be restricted).
  * MockFetcher — a canned public dataset with a few injected discrepancies,
                  so the pipeline is fully runnable and testable offline.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Listing:
    id: int
    name: str
    location: str
    price_inr: int
    operator: str
    contact: str
    meta: dict = field(default_factory=dict)


class SourceFetcher(Protocol):
    def fetch(self, listing: Listing) -> dict | None: ...


class WebFetcher:  # pragma: no cover - network is often restricted here
    """Best-effort real lookup. Returns None when the source can't be reached."""

    def fetch(self, listing: Listing) -> dict | None:
        try:
            import requests
            # A real impl would query a maps/operator API; kept minimal on purpose.
            r = requests.get("https://example.com", timeout=5)
            r.raise_for_status()
            return None
        except Exception:
            return None


class MockFetcher:
    """Deterministic canned 'public source' with seeded discrepancies."""

    def __init__(self, listings: list[Listing], discrepancy_rate: float = 0.18,
                 seed: int = 7) -> None:
        rng = random.Random(seed)
        self._data: dict[int, dict] = {}
        for lst in listings:
            rec = {"location": lst.location, "price_inr": lst.price_inr,
                   "operator": lst.operator, "contact": lst.contact}
            r = rng.random()
            if r < discrepancy_rate / 3:                     # price drift
                rec["price_inr"] = int(lst.price_inr * rng.uniform(1.15, 1.4))
            elif r < 2 * discrepancy_rate / 3:               # location mismatch
                rec["location"] = lst.location + " (Old Town)"
            elif r < discrepancy_rate:                       # contact mismatch
                rec["contact"] = "+91-90000-00000"
            self._data[lst.id] = rec

    def fetch(self, listing: Listing) -> dict | None:
        return self._data.get(listing.id)


def make_sample_listings(n: int = 55, seed: int = 3) -> list[Listing]:
    """Generate a deterministic set of listings to verify (backs the '50+' claim)."""
    rng = random.Random(seed)
    places = ["Manali", "Rishikesh", "Munnar", "Leh", "Gangtok", "Coorg",
              "Nainital", "Shimla", "Kasol", "Dharamshala", "Auli", "Chopta"]
    operators = ["HimalayanTrails", "PeakSeekers", "TrailBlaze", "SummitCo",
                 "WildRoutes", "BaseCampIndia"]
    out = []
    for i in range(1, n + 1):
        loc = rng.choice(places)
        out.append(Listing(
            id=i,
            name=f"{rng.choice(['Roopkund','Hampta','Kedarkantha','Valley of Flowers','Triund'])} #{i}",
            location=loc,
            price_inr=rng.choice([6500, 8500, 9999, 12500, 15000]),
            operator=rng.choice(operators),
            contact=f"+91-9{rng.randint(100000000, 999999999)}",
        ))
    return out
