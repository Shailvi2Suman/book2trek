"""Verification pipeline tests: flags injected discrepancies, tolerates noise."""
from book2trek.verification.pipeline import (
    PRICE_TOLERANCE,
    run_demo,
    verify_batch,
    verify_listing,
)
from book2trek.verification.sources import Listing, MockFetcher, make_sample_listings


class _StubFetcher:
    def __init__(self, rec):
        self.rec = rec

    def fetch(self, listing):
        return self.rec


def _listing(**kw):
    base = dict(id=1, name="X", location="Manali", price_inr=10000,
                operator="PeakSeekers", contact="+91-9111111111")
    base.update(kw)
    return Listing(**base)


def test_clean_listing_is_ok():
    lst = _listing()
    rep = verify_listing(lst, _StubFetcher({"location": "Manali", "price_inr": 10000,
                                            "operator": "PeakSeekers",
                                            "contact": "+91-9111111111"}))
    assert rep.status == "ok" and not rep.discrepancies


def test_price_within_tolerance_not_flagged():
    lst = _listing(price_inr=10000)
    src_price = int(10000 * (1 + PRICE_TOLERANCE / 2))
    rep = verify_listing(lst, _StubFetcher({"price_inr": src_price}))
    assert rep.status == "ok"


def test_price_drift_flagged():
    lst = _listing(price_inr=10000)
    rep = verify_listing(lst, _StubFetcher({"price_inr": 13000}))
    assert rep.status == "flagged"
    assert any(d.field == "price_inr" for d in rep.discrepancies)


def test_location_mismatch_flagged():
    lst = _listing(location="Manali")
    rep = verify_listing(lst, _StubFetcher({"location": "Shimla"}))
    assert any(d.field == "location" for d in rep.discrepancies)


def test_unreachable_source_is_unverified():
    rep = verify_listing(_listing(), _StubFetcher(None))
    assert rep.status == "unverified"


def test_batch_over_50_listings():
    listings = make_sample_listings()
    assert len(listings) >= 50
    summary = verify_batch(listings, MockFetcher(listings))
    assert summary["total"] == len(listings)
    assert summary["flagged"] >= 1                 # mock injects discrepancies


def test_run_demo_summary():
    s = run_demo()
    assert s["ok"] + s["flagged"] + s["unverified"] == s["total"]
