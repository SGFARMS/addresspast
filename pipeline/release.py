"""Release held records: spot-check holds and the old boarding house / hotel / business hold (dropped
Oct 26) become normal records, so the publish step puts them on the map. Removal disputes are untouched.

    python -m pipeline.release
"""
from __future__ import annotations

from .common.db import db
from .common.runlog import PipelineRun


def main() -> int:
    with PipelineRun("release_spot_check") as run:
        rows = (
            db().table("ap_incidents").update({"needs_review": False, "review_reason": None})
            .eq("needs_review", True)
            .in_("review_reason", ["spot-check", "boarding house or hotel", "business address"]).execute().data
        ) or []
        run.items_out = len(rows)
    print(f"released {len(rows)} held records")
    return len(rows)


if __name__ == "__main__":
    main()
