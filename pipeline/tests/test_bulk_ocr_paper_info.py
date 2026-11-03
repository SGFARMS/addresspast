"""paper_info asks loc.gov first; the retired chroniclingamerica.loc.gov address is only a last resort (no network)."""
import requests

from pipeline.sources import bulk_ocr

LOC_ITEM = {"item": {"title": "The Albuquerque Morning Journal", "place": ["New Mexico--Bernalillo--Albuquerque"],
                     "languages": ["english"]}}


def _run(monkeypatch, responses):
    calls = []

    def fake_get_json(url, params=None):
        calls.append(url)
        r = responses.get(url.split("?")[0])
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise requests.RequestException("unexpected url")
        return r

    monkeypatch.setattr(bulk_ocr, "_get_json", fake_get_json)
    monkeypatch.setattr(bulk_ocr.time, "sleep", lambda _s: None)
    bulk_ocr.paper_info.cache_clear()
    return calls


def test_loc_gov_answers_without_touching_the_legacy_host(monkeypatch):
    calls = _run(monkeypatch, {"https://www.loc.gov/item/sn1/": LOC_ITEM})
    info = bulk_ocr.paper_info("sn1")
    assert info["title"] == "The Albuquerque Morning Journal"
    assert info["cities"] == ["albuquerque"]
    assert calls == ["https://www.loc.gov/item/sn1/"]


def test_legacy_host_is_used_only_when_loc_gov_fails(monkeypatch):
    legacy = {"name": "Old Paper", "place_of_publication": "Las Vegas, N.M."}
    calls = _run(monkeypatch, {
        "https://www.loc.gov/item/sn2/": requests.RequestException("down"),
        "https://chroniclingamerica.loc.gov/lccn/sn2.json": legacy,
    })
    info = bulk_ocr.paper_info("sn2")
    assert info["title"] == "Old Paper" and info["cities"] == ["las vegas"]
    assert calls[0].startswith("https://www.loc.gov/") and calls[1].startswith("https://chroniclingamerica.loc.gov/")


def test_both_fail_returns_empty_info(monkeypatch):
    _run(monkeypatch, {})
    assert bulk_ocr.paper_info("sn3") == {"title": None, "cities": [], "languages": []}
