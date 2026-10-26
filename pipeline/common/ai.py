"""Tool-use helpers shared by every pipeline step that asks Claude for structured output.

Some models (Sonnet 5.5 among them) reject a forced tool_choice ({"type": "tool"} or "any") with
400 "tool_choice: type "tool" and "any" are not supported for this model". For those we ask with
tool_choice "auto" plus a one-line instruction to answer through the tool, and callers treat a
reply without a tool call as "no answer" rather than crashing.
"""
from __future__ import annotations

import copy

# Models known to accept a forced tool call. Anything else gets "auto" up front; a forced call that a
# model rejects anyway is retried once with "auto" and remembered for the rest of the run.
_NO_FORCED: set[str] = set()


def supports_forced(model: str) -> bool:
    return "haiku" in model and model not in _NO_FORCED


def tool_params(params: dict, name: str) -> dict:
    """Return params with the right tool_choice for params["model"] (copied, never mutated)."""
    p = copy.copy(params)
    if supports_forced(p["model"]):
        p["tool_choice"] = {"type": "tool", "name": name}
        return p
    p["tool_choice"] = {"type": "auto"}
    system = list(p.get("system") or [])
    if isinstance(p.get("system"), str):
        system = [{"type": "text", "text": p["system"]}]
    system.append({"type": "text", "text": f"Always answer by calling the {name} tool exactly once. Do not reply with plain text."})
    p["system"] = system
    return p


def create_with_tool(client, name: str, **params):
    """messages.create that asks for exactly one call to tool `name`, whatever the model allows."""
    p = tool_params(params, name)
    try:
        return client.messages.create(**p)
    except Exception as e:  # anthropic.BadRequestError; imported lazily so tests run without the SDK
        if p["tool_choice"].get("type") == "tool" and "tool_choice" in str(e):
            _NO_FORCED.add(p["model"])
            return client.messages.create(**tool_params(params, name))
        raise


def tool_input(msg) -> dict | None:
    """The input of the first tool call in a reply, or None when the model answered without one."""
    block = next((b for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
    return (block.input or {}) if block else None
