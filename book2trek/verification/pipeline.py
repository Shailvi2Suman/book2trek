"""
AI-assisted listing verification pipeline.

Cross-checks each DB listing against a public source and flags inconsistencies
in location, price, operator, and contact. Price uses a tolerance band (small
differences are noise, not fraud); text fields are compared with light
normalisation. Returns a per-listing report plus a summary — exactly the
"validate 50+ listings, flag inconsistencies" deliverable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sources import Listing, MockFetcher, SourceFetcher, make_sample_listings

PRICE_TOLERANCE = 0.10   # 10% price difference is tolerated as noise


@dataclass
class Discrepancy:
    field: str
    ours: object
    source: object


@dataclass
class Report:
    listing_id: int
    name: str
    status: str                       # "ok" | "flagged" | "unverified"
    discrepancies: list[Discrepancy] = field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def verify_listing(listing: Listing, fetcher: SourceFetcher) -> Report:
    source = fetcher.fetch(listing)
    if source is None:
        return Report(listing.id, listing.name, "unverified")

    diffs: list[Discrepancy] = []
    if _norm(listing.location) != _norm(source.get("location", listing.location)):
        diffs.append(Discrepancy("location", listing.location, source.get("location")))

    src_price = source.get("price_inr", listing.price_inr)
    if src_price and abs(src_price - listing.price_inr) / listing.price_inr > PRICE_TOLERANCE:
        diffs.append(Discrepancy("price_inr", listing.price_inr, src_price))

    if _norm(listing.operator) != _norm(source.get("operator", listing.operator)):
        diffs.append(Discrepancy("operator", listing.operator, source.get("operator")))

    if _norm(listing.contact) != _norm(source.get("contact", listing.contact)):
        diffs.append(Discrepancy("contact", listing.contact, source.get("contact")))

    status = "flagged" if diffs else "ok"
    return Report(listing.id, listing.name, status, diffs)


def verify_batch(listings: list[Listing], fetcher: SourceFetcher) -> dict:
    reports = [verify_listing(x, fetcher) for x in listings]
    flagged = [r for r in reports if r.status == "flagged"]
    unver = [r for r in reports if r.status == "unverified"]
    return {
        "total": len(reports),
        "ok": sum(1 for r in reports if r.status == "ok"),
        "flagged": len(flagged),
        "unverified": len(unver),
        "reports": reports,
    }


def run_demo() -> dict:
    """Verify a sample of 55 listings against the mock public source."""
    listings = make_sample_listings()
    summary = verify_batch(listings, MockFetcher(listings))
    return summary


if __name__ == "__main__":
    s = run_demo()
    print(f"Verified {s['total']} listings: {s['ok']} ok, "
          f"{s['flagged']} flagged, {s['unverified']} unverified")
    for r in s["reports"]:
        if r.status == "flagged":
            fields = ", ".join(d.field for d in r.discrepancies)
            print(f"  ⚑ {r.name} (id {r.listing_id}): {fields}")
