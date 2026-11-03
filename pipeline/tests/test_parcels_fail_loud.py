"""A parcel load that finds nothing usable must fail, not pass quietly (no network, no database)."""
import sys
import types

import pytest

try:  # the real client isn't needed here; stand in for it only when it isn't installed
    from supabase import Client  # noqa: F401
except ImportError:
    _stub = types.ModuleType("supabase")
    _stub.Client = object
    _stub.create_client = lambda *a, **k: None
    sys.modules["supabase"] = _stub

from pipeline import parcels  # noqa: E402

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


class _Run:
    items_in = 0
    items_out = 0

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Table:
    def upsert(self, rows):
        self.rows = rows
        return self

    def execute(self):
        return self


class _DB:
    def table(self, name):
        return _Table()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(parcels, "PipelineRun", _Run)
    monkeypatch.setattr(parcels, "db", lambda: _DB())


def feat(**props):
    return {"type": "Feature", "properties": props, "geometry": SQUARE}


def test_good_features_load():
    parcels.load("bernalillo", "", "PIN", "ADDRESS", features=[feat(PIN="1", ADDRESS="1 Main St")])


def test_empty_source_fails():
    with pytest.raises(parcels.ParcelSourceError, match="no parcels at all"):
        parcels.load("bernalillo", "", "UPC", "SITUSADD", features=[])


def test_renamed_fields_fail():
    with pytest.raises(parcels.ParcelSourceError, match="field names may have changed"):
        parcels.load("bernalillo", "", "UPC", "SITUSADD", features=[feat(PIN="1", ADDRESS="1 Main St")])


def test_error_body_with_http_200_fails(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": {"code": 400, "message": "Invalid or missing input parameters."}}

    class Sess:
        headers = {}

        def get(self, *a, **k):
            return Resp()

    monkeypatch.setattr(parcels.requests, "Session", lambda: Sess())
    with pytest.raises(parcels.ParcelSourceError, match="returned an error"):
        list(parcels.fetch_arcgis("bernalillo"))


def test_clean_collapses_whitespace_and_empties():
    from pipeline import parcels
    assert parcels._clean("5704 Tinnin Rd Nw ") == "5704 Tinnin Rd Nw"
    assert parcels._clean("2941  Madison St   Ne") == "2941 Madison St Ne"
    assert parcels._clean("   ") is None
    assert parcels._clean(None) is None


def test_bernalillo_source_requests_no_owner_fields():
    from pipeline import parcels
    src = parcels.ARCGIS_SOURCES["bernalillo"]
    assert "gis.ose.nm.gov" in src["url"]
    assert not any("owner" in str(v).lower() or "mail" in str(v).lower() for v in src.values())
