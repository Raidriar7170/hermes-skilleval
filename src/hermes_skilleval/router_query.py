from __future__ import annotations


def router_query_text(prompt: str) -> str:
    """Return the sole task-side router input without adding benchmark metadata."""

    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")
    if not prompt.strip():
        raise ValueError("prompt must be non-empty")
    return prompt
