"""Prints how many New Mexico bulk-OCR batches the harvester hasn't read to the end yet.

The scheduled harvest (harvest.yml) runs this first: 0 means the backlog is done, and the workflow
switches its own schedule off instead of starting a multi-hour run every 6 hours.
"""
from __future__ import annotations


def main() -> None:
    from .harvest import bulk_batches_done
    from .sources.bulk_ocr import nm_batches

    done = bulk_batches_done()
    left = [b for b in nm_batches() if b["batch"] not in done]
    print(f"bulk batches: {len(done)} read, {len(left)} left", flush=True)
    print(len(left))


if __name__ == "__main__":
    main()
