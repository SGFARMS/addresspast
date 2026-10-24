"""Release the spot-check holds: records that waited in /admin only because of the spot-check
(review_reason 'spot-check') become normal records, so the nightly step can publish them.
Boarding houses, hotels and businesses keep waiting for a person, as before.

    python -m pipeline.release
"""
from __future__ import annotations

from .common.db import db
from .common.runlog import PipelineRun


def main() -> int:
    with PipelineRun("release_spot_check") as run:
        rows = (
            db().table("ap_incidents").update({"needs_review": False, "review_reason": None})
            .eq("needs_review", True).eq("review_reason", "spot-check").execute().data
        ) or []
        run.items_out = len(rows)
    print(f"released {len(rows)} spot-check records")
    return len(rows)


if __name__ == "__main__":
    main()
