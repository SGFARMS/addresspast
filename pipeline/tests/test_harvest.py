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
    assert candidate_windows(FILLER + "A miner was killed in Silver City." + FILLER)  # statewide now
    assert candidate_windows(FILLER + "A miner was killed in Denver yesterday." + FILLER) == []
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
    assert not hotel["needs_review"] and hotel["place_kind"] == "boarding_house_or_hotel" and hotel["confidence"] == 0.8


def test_sonnet_escalation_rules():
    assert not needs_sonnet([{"confidence": 0.5, "location_precision": "city_only"}])  # town-level: Haiku's read stands
    assert not needs_sonnet([{"confidence": 0.1, "location_precision": "street_address"}])  # clearly junk
    assert needs_sonnet([{"confidence": 0.7, "location_precision": "street_address"}])
    assert not needs_sonnet([{"confidence": 0.9, "location_precision": "street_address"}])
    assert not needs_sonnet([{"confidence": 0.7, "location_precision": "city_only"}])


def test_town_lookup():
    assert town_by_name("Los Lunas").county == "valencia"
    assert town_by_name("albuquerque").lat > 35


def test_geocode_rules(monkeypatch):
    from pipeline import geocode as g

    monkeypatch.setattr(g, "census", lambda a: (35.09, -106.65, "412 N 5TH ST, ALBUQUERQUE, NM, 87102"))
    monkeypatch.setattr(g, "photon", lambda q, places_only=False: {"geometry": {"coordinates": [-106.66, 35.08]},
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
    far = g.geocode_row({"address_raw": "", "city": "El Paso", "location_precision": "city_only"})
    assert far["geocode_status"] == "failed"  # Photon's answer isn't a New Mexico place named El Paso

    # Anywhere else in New Mexico: the town comes from Photon (OpenStreetMap).
    monkeypatch.setattr(g, "photon", lambda q, places_only=False: {"geometry": {"coordinates": [-108.2742, 32.7701]},
                                                 "properties": {"name": "Silver City", "osm_key": "place", "osm_value": "town",
                                                                "county": "Grant County"}})
    sc = g.geocode_row({"address_raw": "", "city": "Silver City", "location_precision": "city_only", "incident_year": 1912})
    assert sc["geocode_status"] == "ok" and sc["county"] == "Grant" and sc["geocode_precision"] == "city"

    # A wire story from New York must not land on the tiny "New York" in Cibola County, NM.
    monkeypatch.setattr(g, "photon", lambda q, places_only=False: {"geometry": {"coordinates": [-107.527, 35.058]},
                                                 "properties": {"name": "New York", "osm_value": "hamlet", "county": "Cibola County"}})
    ny = g.geocode_row({"address_raw": "", "city": "New York", "county": None, "location_precision": "city_only", "incident_year": 1912})
    assert ny["geocode_status"] == "failed" and ny["lat"] is None
    # ...nor on a re-check, after the first placement wrote Photon's county onto the record.
    again = g.geocode_row({"address_raw": "", "city": "New York", "county": "Cibola", "location_precision": "city_only",
                           "incident_year": 1912}, recheck=True)
    assert again["geocode_status"] == "failed"


def test_spot_check_holds_every_record(monkeypatch):
    monkeypatch.setenv("AP_HOLD_FOR_REVIEW", "1")
    page = {"url": "https://example.org/b", "language": "en"}
    items = [
        {"address_raw": "412 N. Fifth St.", "city": "Albuquerque", "location_precision": "street_address",
         "place_kind": "house", "cause_category": "accident", "summary": "A fall.", "confidence": 0.9},
        {"address_raw": "Sturges Hotel", "city": "Albuquerque", "location_precision": "landmark",
         "place_kind": "boarding_house_or_hotel", "cause_category": "homicide", "summary": "A shooting.", "confidence": 0.8},
    ]
    house, hotel = to_rows(page, items)
    assert house["needs_review"] and house["review_reason"] == "spot-check"
    assert hotel["review_reason"] == "spot-check"  # spot-check holds everything, hotels included


def test_tool_choice_fits_the_model():
    from types import SimpleNamespace

    from pipeline.common.ai import create_with_tool, tool_input, tool_params
    from pipeline.extract import extraction_params, items_from_message

    assert extraction_params("x", "claude-haiku-5-5")["tool_choice"] == {"type": "tool", "name": "record_deaths"}
    smart = extraction_params("x", "claude-sonnet-5-5")
    assert smart["tool_choice"] == {"type": "auto"} and "record_deaths" in smart["system"][-1]["text"]
    assert len(tool_params({"model": "m", "system": "s"}, "t")["system"]) == 2

    text_only = SimpleNamespace(content=[SimpleNamespace(type="text", text="no deaths")])
    assert tool_input(text_only) is None and items_from_message(text_only) == []

    class Client:  # a model that rejects forced tool use, like Sonnet 5.5
        def __init__(self):
            self.calls = []
            self.messages = self

        def create(self, **p):
            self.calls.append(p["tool_choice"])
            if p["tool_choice"]["type"] == "tool":
                raise RuntimeError('tool_choice: type "tool" and "any" are not supported for this model.')
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"ok": True})])

    c = Client()
    assert tool_input(create_with_tool(c, "t", model="claude-haiku-9", messages=[])) == {"ok": True}
    assert c.calls == [{"type": "tool", "name": "t"}, {"type": "auto"}]


def test_fars_rows():
    from pipeline.fars import to_incident

    row = {"STATE": "35", "ST_CASE": "350123", "MONTH": "3", "DAY": "8", "LATITUDE": "35.0844", "LONGITUD": "-106.6504",
           "FATALS": "2", "COUNTY": "1", "COUNTYNAME": "BERNALILLO (1)", "CITYNAME": "ALBUQUERQUE (40)", "TWAY_ID": "I-40", "TWAY_ID2": ""}
    i = to_incident(row, 2019)
    assert i["record_type"] == "road_death" and i["city"] == "Albuquerque" and i["county"] == "Bernalillo"
    assert i["incident_date"] == "2019-03-08" and "2 people died" in i["summary"] and i["address_raw"] == "I-40"
    assert to_incident({**row, "LATITUDE": "77.7777"}, 2019) is None  # coordinates not reported
    assert to_incident({**row, "STATE": "4"}, 2019) is None  # Arizona


def test_weak_keywords_need_company():
    town = "in Albuquerque yesterday."
    assert candidate_windows(FILLER + "The dead letter office " + town + FILLER) == []          # lone weak word
    assert candidate_windows(FILLER + "He was found dead at his home " + town + FILLER)       # strong phrase
    assert candidate_windows(FILLER + "She died after the shooting " + town + FILLER)          # two weak words together
    far = FILLER + "A man was killed. " + ("Unrelated news about the fair. " * 20) + "Albuquerque" + FILLER
    assert candidate_windows(far) == []  # the town is too far from the keyword


def test_rows_clean_odd_model_values():
    page = {"url": "https://example.org/c", "language": "en"}
    items = [
        {"address_raw": "", "city": "Gallup", "location_precision": "town", "place_kind": "x", "cause_category": "Murder",
         "summary": "A death.", "confidence": 0.7},
        {"address_raw": "Harvey House", "city": "Belen", "location_precision": None, "place_kind": "house",
         "cause_category": None, "summary": "A death.", "confidence": 0.7},
    ]
    a, b = to_rows(page, items)
    assert a["location_precision"] == "city_only" and a["cause_category"] == "unknown" and a["place_kind"] == "unknown"
    assert b["location_precision"] == "landmark" and b["cause_category"] == "unknown"


def test_fars_old_lowercase_columns():
    import io
    import zipfile

    from pipeline.fars import accident_rows, to_incident

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ACCIDENT.CSV", "STATE,ST_CASE,MONTH,DAY,latitude,longitud,FATALS,COUNTY\n35,350007,6,2,35.0418,-106.7137,1,1\n")
    rows = list(accident_rows(zipfile.ZipFile(buf)))
    i = to_incident(rows[0], 2001)
    assert i and i["lat"] == 35.0418 and i["county"] == "Bernalillo" and i["incident_date"] == "2001-06-02"


def test_county_phrase_is_not_a_town(monkeypatch):
    from pipeline import geocode as g

    monkeypatch.setattr(g, "photon", lambda q, places_only=False: {"geometry": {"coordinates": [-107.8516, 35.1473]},
        "properties": {"name": "Grants", "osm_value": "town", "county": "Cibola County"}})
    r = g.geocode_row({"address_raw": "near Grants, Valencia county", "city": "Grants", "county": "Valencia",
                       "location_precision": "city_only", "incident_year": 1912})
    assert r["geocode_status"] == "ok" and abs(r["lng"] - -107.8516) < 0.01  # Grants, not the village of Valencia


def test_county_history_decides_town_fit():
    from pipeline import geocode as g

    assert g.county_fits("Valencia", "Cibola")        # Cubero, Valencia County, 1910: right for its time
    assert g.county_fits("Socorro", "Sierra")         # Chloride before Sierra County existed
    assert not g.county_fits("Grant", "bernalillo")   # a Grant County item pinned on Albuquerque
    assert g.county_fits("Dona Ana", "Doña Ana") and g.county_fits("DeBaca", "De Baca")  # spellings
    assert g.county_fits(None, "bernalillo") and g.county_fits("Maricopa", "bernalillo")  # nothing to compare
    r = g.geocode_row({"address_raw": "", "city": "Albuquerque", "county": "Grant", "location_precision": "city_only",
                       "incident_year": 1910})
    assert r["geocode_status"] == "failed"


def test_dedupe_date_rule():
    from pipeline.dedupe_rules import could_be_same

    assert could_be_same({"incident_date": "1912-03-08"}, {"incident_date": "1912-03-10"})
    assert not could_be_same({"incident_date": "1912-03-08"}, {"incident_date": "1912-09-02"})
    assert not could_be_same({"incident_date": "1912-03-01"}, {"incident_date": "1912-03-25"})
    assert could_be_same({"incident_date": "1912"}, {"incident_date": "1912-06"})  # too vague to rule out
    assert not could_be_same({"published_date": "1912-01-05"}, {"published_date": "1912-08-01"})


def test_dedupe_rule_verdicts():
    from pipeline.dedupe_rules import rule_verdict

    a = {"incident_date": "1912-03-08", "city": "Gallup", "cause_category": "homicide"}
    assert rule_verdict(a, {**a, "cause_category": "unknown"}) is True          # two papers, one killing
    assert rule_verdict(a, {**a, "incident_date": "1912-09-01"}) is False       # months apart
    assert rule_verdict(a, {**a, "incident_date": "1912-03"}) is None           # model decides
    assert rule_verdict(a, {**a, "cause_category": "accident"}) is None


def test_dedupe_same_story_rule():
    from pipeline.dedupe_rules import date_gap_days, rule_verdict

    w = {"incident_date": "1916-05", "city": "Gallup", "cause_category": "homicide",
         "summary": "The body of a young woman who had been assaulted and beaten was found near a road."}
    assert rule_verdict(w, dict(w)) is True                                       # same story, two papers
    other = {**w, "summary": "An Indian girl's body was found near a road outside Gallup after an assault."}
    assert rule_verdict(w, other) is None                                         # different wording: model
    short = {"incident_date": "1916-09", "city": "Gallup", "cause_category": "homicide",
             "summary": "A fatal shooting at a saloon in Gallup was reported."}
    assert rule_verdict(short, dict(short)) is None                               # too generic to be sure
    assert rule_verdict(w, {**w, "city": "Gibson"}) is None                       # other town
    assert date_gap_days({"incident_date": "1916-05-02"}, {"published_date": "1916-05-09"}) == 7


def test_not_a_death():
    from pipeline.quality import not_a_death

    assert not_a_death("A suicide attempt by a porter at a saloon in Gallup was reported.")
    assert not_a_death("A man was shot in a quarrel and is expected to recover.")
    assert not not_a_death("A man attempted suicide and died later at the hospital.")
    assert not not_a_death("Two men drowned in the river; a third survived.")
    assert not not_a_death("A fatal shooting at a saloon in Gallup was reported.")
    assert not not_a_death(None)
