"""Log every pipeline run to pipeline_runs and every Claude call to ai_usage.

Usage:
    with PipelineRun("dedupe") as run:
        ...
        run.ai("dedupe", model, msg.usage)
        run.items_in += 1
"""
from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone

from .config import MAX_RUN_COST_USD, cost_usd


class BudgetExceeded(RuntimeError):
    pass


class PipelineRun:
    def __init__(self, job: str, trigger: str = "cron", meta: dict | None = None, max_cost: float | None = None):
        self.job = job
        self.max_cost = MAX_RUN_COST_USD if max_cost is None else max_cost
        self._lock = threading.Lock()
        self.by_model: dict[str, float] = {}
        self.trigger = trigger
        self.meta = meta or {}
        self.items_in = 0
        self.items_out = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost = 0.0
        self.batch_id: str | None = None
        self.id: int | None = None
        self.status = "ok"

    def __enter__(self):
        from .db import db

        row = db().table("ap_pipeline_runs").insert({"job": self.job, "trigger": self.trigger, "meta": self.meta}).execute()
        self.id = row.data[0]["id"]
        return self

    def remaining(self) -> float:
        return self.max_cost - self.cost

    def _account(self, model: str, usage, batched: bool) -> float:
        c = cost_usd(model, usage, batched)
        with self._lock:
            self.cost += c
            self.tokens_in += getattr(usage, "input_tokens", 0) or 0
            self.tokens_out += getattr(usage, "output_tokens", 0) or 0
            self.by_model[model] = self.by_model.get(model, 0.0) + c
        return c

    def ai(self, feature: str, model: str, usage, batched: bool = False):
        from .db import db

        c = self._account(model, usage, batched)
        db().table("ap_ai_usage").insert({
            "feature": feature,
            "model": model,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "batched": batched,
            "cost_usd": round(c, 5),
            "run_id": self.id,
        }).execute()
        if self.cost > self.max_cost:
            self.status = "partial"
            raise BudgetExceeded(f"{self.job} passed ${self.max_cost:.2f}; stopping early")

    def __exit__(self, exc_type, exc, tb):
        from .db import db

        err = None
        if exc_type is BudgetExceeded:
            self.status = "partial"
            err = str(exc)
        elif exc_type is not None:
            self.status = "error"
            err = "".join(traceback.format_exception(exc_type, exc, tb))[-4000:]
        db().table("ap_pipeline_runs").update({
            "status": self.status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "items_in": self.items_in,
            "items_out": self.items_out,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost, 4),
            "batch_id": self.batch_id,
            "error": err,
        }).eq("id", self.id).execute()
        return exc_type is BudgetExceeded  # swallow budget stops, re-raise real errors


class LocalRun(PipelineRun):
    """Same interface, no database: usage goes to a JSONL file. Used for dry runs and spot-check samples."""

    def __init__(self, job: str, usage_path: str, max_cost: float | None = None, meta: dict | None = None):
        super().__init__(job, trigger="dry_run", meta=meta, max_cost=max_cost)
        self.usage_path = usage_path

    def __enter__(self):
        self.id = 0
        self._f = open(self.usage_path, "a", encoding="utf-8")
        return self

    def ai(self, feature: str, model: str, usage, batched: bool = False):
        c = self._account(model, usage, batched)
        with self._lock:
            self._f.write(json.dumps({
                "feature": feature, "model": model, "cost_usd": round(c, 6),
                "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            }) + "\n")
        if self.cost > self.max_cost:
            self.status = "partial"
            raise BudgetExceeded(f"{self.job} passed ${self.max_cost:.2f}; stopping early")

    def __exit__(self, exc_type, exc, tb):
        self._f.close()
        if exc_type is BudgetExceeded:
            self.status = "partial"
        elif exc_type is not None:
            self.status = "error"
        return exc_type is BudgetExceeded


def spent_so_far(features_prefix: str = "harvest_") -> float:
    """Total logged spend for a feature family (for caps that span many runs)."""
    from .db import db

    total = 0.0
    start = 0
    while True:
        rows = (
            db().table("ap_ai_usage").select("cost_usd").like("feature", f"{features_prefix}%")
            .range(start, start + 999).execute().data
        )
        total += sum(float(r["cost_usd"] or 0) for r in rows)
        if len(rows) < 1000:
            return total
        start += 1000
