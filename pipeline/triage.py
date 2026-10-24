"""Haiku first pass: only pages that likely contain an NM death with a location go to Sonnet.

    from pipeline.triage import worth_extracting
    if lang.has_keyword(text) and worth_extracting(text, run):
        ... send to Sonnet extraction (live) or queue for batches.py ...
"""
from anthropic import Anthropic

from .common.ai import create_with_tool, tool_input
from .common.config import MODEL_FAST
from .lang import TRIAGE_SYSTEM

_client = Anthropic()

TOOL = {
    "name": "triage",
    "description": "Report whether the page is worth full extraction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "has_nm_death_with_location": {"type": "boolean"},
            "language": {"type": "string", "enum": ["en", "es", "mixed"]},
        },
        "required": ["has_nm_death_with_location", "language"],
    },
}


def worth_extracting(text: str, run=None, max_chars: int = 24000) -> bool:
    msg = create_with_tool(
        _client,
        "triage",
        model=MODEL_FAST,
        max_tokens=60,
        # The system prompt is identical for every page, so it's cached
        system=[{"type": "text", "text": TRIAGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[TOOL],
        messages=[{"role": "user", "content": text[:max_chars]}],
    )
    if run is not None:
        run.ai("triage", MODEL_FAST, msg.usage)
    return bool((tool_input(msg) or {}).get("has_nm_death_with_location"))
