"""Pure-logic tests for the harvester (no network, no API keys)."""
from pipeline.extract import needs_sonnet, to_rows
from pipeline.harvest import clean_title
from pipeline.places_nm import find_towns, is_pilot_paper, mentions_pilot_area, town_by_name
from pipeline.prefilter import MAX_CHARS, candidate_windows
from pipeline.sources.loc import normalize_url, parse_result

FILLER = "The territorial fair opened with a parade and the band played. " * 40


def test_window_needs_keyword_and_town():
    text = FILLER + "A man was shot and killed last night at a saloon on Railroad avenue in Albuquerque." + FILLER
    w = candidate_windows(text)
    assert len(w) == 1 and "Albuquerque" in w[0]
    assert candidate_windows(FILLER + "A miner was killed in Silver City." + FILLER) == []
    assert candidate_windows(FILLER + "Albuquerque welcomed visitors." + FILLER) == []


def test_local_paper_accepts_street_cue_without_town():
    text = FILLER + "He was found dead at his home on North Fourth street." + FILLER
    assert candidate_windows(text) == []
    assert candidate_windows(text, local_paper=True)


def test_spanish_and_ocr_variants():
    assert candidate_windows(FILLER + "Fue asesinado en Los Lunas el domingo." + FILLER)
    assert mentions_pilot_area("en el condado de Valencia")
    assert [t.name for t in find_towns("ALBUQUERQNE, N. M., March 3")] == ["Albuquerque"]
    assert not find_towns("a tome of poetry")  # 'Tomé' is case-sensitive


def test_windows_merge_and_cap():
    text = ("He drowned near Belen. " * 3000)
    w = candidate_windows(text)
    assert sum(len(x) for x in w) <= MAX_CHARS


def test_parse_loc_result():
    r = {
        "id": "http://www.loc.gov/resource/sn84031081/1912-03-08/ed-1/?sp=5&q=killed+shot",
        "date": "1912-03-08",
        "partof_title": ["albuquerque morning journal. [volume] (albuquerque, n.m.) 1903-1922"],
        "location_city": ["albuquerque"],
        "language": ["english"],
        "full_text": "MAN KILLED ...",
    }
    p = parse_result(r)
    assert p.url == "https://www.loc.gov/resource/sn84031081/1912-03-08/ed-1/?sp=5"
    assert p.date == "1912-03-08" and p.text.startswith("MAN")
    assert is_pilot_paper(p.paper_cities)
    assert clean_title(p.paper) == "Albuquerque Morning Journal"
    assert normalize_url("https://www.loc.gov/resource/x/?q=a") == "https://www.loc.gov/resource/x/"


def test_rows_scrub_review_and_units():
    page = {"url": "https://example.org/a", "source_name": "Paper", "published_date": "1912-03-08", "language": "en"}
    items = [
        {"address_raw": "412 N. Fifth St.", "unit": "Apt 3", "city": "Albuquerque", "county": "Bernalillo County",
         "location_precision": "street_address", "place_kind": "apartment_building", "cause_category": "suicide",
         "summary": "John Smith died at an apartment.", "confidence": 0.9},
        {"address_raw": "Sturges Hotel", "city": "Albuquerque", "location_precision": "landmark",
         "place_kind": "boarding_house_or_hotel", "cause_category": "homicide", "summary": "A fatal shooting at a hotel.",
         "confidence": 0.8},
        {"address_raw": "Sturges Hotel", "city": "Albuquerque", "location_precision": "landmark",
         "place_kind": "boarding_house_or_hotel", "cause_category": "homicide", "summary": "dup", "confidence": 0.5},
    ]
    rows = to_rows(page, items, "m")
    assert len(rows) == 2
    apt = rows[0]
    assert "Smith" not in apt["summary"] and apt["county"] == "Bernalillo" and apt["unit"] == "Apt 3"
    assert apt["cause_category"] == "suicide" and not apt["needs_review"]
    hotel = rows[1]
    assert hotel["needs_review"] and hotel["review_reason"] == "boarding house or hotel" and hotel["confidence"] == 0.8


def test_sonnet_escalation_rules():
    assert needs_sonnet([{"confidence": 0.5, "location_precision": "city_only"}])
    assert needs_sonnet([{"confidence": 0.7, "location_precision": "street_address"}])
    assert not needs_sonnet([{"confidence": 0.9, "location_precision": "street_address"}])
    assert not needs_sonnet([{"confidence": 0.7, "location_precision": "city_only"}])


def test_town_lookup():
    assert town_by_name("Los Lunas").county == "valencia"
    assert town_by_name("albuquerque").lat > 35


def test_geocode_rules(monkeypatch):
    from pipeline import geocode as g

    monkeypatch.setattr(g, "census", lambda a: (35.09, -106.65, "412 N 5TH ST, ALBUQUERQUE, NM, 87102"))
    monkeypatch.setattr(g, "photon", lambda q: {"geometry": {"coordinates": [-106.66, 35.08]},
                                                 "properties": {"name": "KiMo Theatre", "type": "house"}})
    modern = g.geocode_row({"address_raw": "412 N. Fifth St.", "city": "Albuquerque", "location_precision": "street_address", "incident_year": 1998})
    assert modern["geocode_precision"] == "street" and modern["geocode_status"] == "ok"
    old = g.geocode_row({"address_raw": "412 N. Fifth St.", "city": "Albuquerque", "location_precision": "street_address", "incident_year": 1912})
    assert old["geocode_precision"] == "city" and old["geocode_status"] == "fallback" and "census candidate" in old["matched_address"]
    lm = g.geocode_row({"address_raw": "KiMo Theater", "city": "Albuquerque", "location_precision": "landmark", "incident_year": 1951})
    assert lm["geocode_precision"] == "landmark"
    wrong = g.geocode_row({"address_raw": "Alvarado Hotel", "city": "Albuquerque", "location_precision": "landmark", "incident_year": 1920})
    assert wrong["geocode_precision"] == "city" and wrong["geocode_status"] == "fallback"
    town = g.geocode_row({"address_raw": "", "city": "Belen", "location_precision": "city_only", "incident_year": 1900})
    assert town["geocode_status"] == "ok" and town["county"] == "Valencia"
    far = g.geocode_row({"address_raw": "", "city": "Silver City", "location_precision": "city_only"})
    assert far["geocode_status"] == "failed"
