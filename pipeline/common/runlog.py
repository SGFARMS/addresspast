"""Log every pipeline run to pipeline_runs and every Claude call to ai_usage.

Usage:
    with PipelineRun("dedupe") as run:
        ...
        run.ai("dedupe", model, msg.usage)
        run.items_in += 1
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone

from .config import MAX_RUN_COST_USD, cost_usd
from .db import db


class BudgetExceeded(RuntimeError):
    pass


class PipelineRun:
    def __init__(self, job: str, trigger: str = "cron", meta: dict | None = None):
        self.job = job
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
        row = db().table("ap_pipeline_runs").insert({"job": self.job, "trigger": self.trigger, "meta": self.meta}).execute()
        self.id = row.data[0]["id"]
        return self

    def ai(self, feature: str, model: str, usage, batched: bool = False):
        c = cost_usd(model, usage, batched)
        self.cost += c
        self.tokens_in += getattr(usage, "input_tokens", 0) or 0
        self.tokens_out += getattr(usage, "output_tokens", 0) or 0
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
        if self.cost > MAX_RUN_COST_USD:
            self.status = "partial"
            raise BudgetExceeded(f"{self.job} passed ${MAX_RUN_COST_USD:.2f}; stopping early")

    def __exit__(self, exc_type, exc, tb):
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
