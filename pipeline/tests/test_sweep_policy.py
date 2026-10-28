import datetime as dt

from pipeline.sweep_policy import next_meta, skip_reason

NOW = dt.datetime(2026, 10, 28, 12, tzinfo=dt.timezone.utc)


def test_a_pass_under_way_continues():
    assert skip_reason({"last_id": 1234, "pass_done_at": NOW.isoformat(), "last_pass_merges": 5}, NOW) is None


def test_old_runs_without_pass_info_continue():
    assert skip_reason({"last_id": 0}, NOW) is None
    assert skip_reason(None, NOW) is None


def test_one_pass_per_week():
    meta = {"last_id": 0, "pass_done_at": (NOW - dt.timedelta(days=2)).isoformat(), "last_pass_merges": 3}
    assert "one pass a week" in skip_reason(meta, NOW)
    meta["pass_done_at"] = (NOW - dt.timedelta(days=8)).isoformat()
    assert skip_reason(meta, NOW) is None


def test_a_clean_pass_ends_the_cleanup_for_good():
    meta = {"last_id": 0, "pass_done_at": (NOW - dt.timedelta(days=30)).isoformat(), "last_pass_merges": 0}
    assert "finished" in skip_reason(meta, NOW)


def test_merges_add_up_over_a_pass_and_reset_when_it_ends():
    m1 = next_meta({}, last_id=500, merges=4, wrapped=False, now=NOW)
    m2 = next_meta(m1, last_id=900, merges=1, wrapped=False, now=NOW)
    assert (m2["last_id"], m2["pass_merges"]) == (900, 5)
    m3 = next_meta(m2, last_id=0, merges=0, wrapped=True, now=NOW)
    assert (m3["last_id"], m3["pass_merges"], m3["last_pass_merges"]) == (0, 0, 5)
    assert skip_reason(m3, NOW + dt.timedelta(days=1)) is not None
    clean = next_meta(next_meta(m3, 10, 0, False, NOW), 0, 0, True, NOW)
    assert clean["last_pass_merges"] == 0
    assert "finished" in skip_reason(clean, NOW + dt.timedelta(days=9))
