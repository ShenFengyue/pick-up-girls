"""Structured, cumulative long-term relationship memory.

The character's long-term memory is stored as three lists that accumulate over
time instead of being replaced after each review:

- ``facts``: stable facts about the user and the relationship.
- ``preferences``: likes, dislikes and preferences either side expressed.
- ``milestones``: relationship progress, promises and notable moments.

Legacy records store ``relationship_memory`` as a single string. Every helper
here coerces that legacy shape into ``{"facts": [text], ...}`` so existing data
is preserved and upgraded lazily on the next write.
"""

from __future__ import annotations

from typing import Any

CATEGORIES = ("facts", "preferences", "milestones")
CATEGORY_LABELS = {
    "facts": "关于彼此的事实",
    "preferences": "偏好与好恶",
    "milestones": "关系节点",
}
MAX_PER_CATEGORY = 20
MAX_ENTRY_CHARS = 200
MAX_LEGACY_CHARS = 1000


def empty_memory() -> dict[str, list[str]]:
    return {category: [] for category in CATEGORIES}


def _clean_entry(value: Any, limit: int = MAX_ENTRY_CHARS) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    return text[:limit]


def _dedupe_entries(items: list[str]) -> list[str]:
    seen: set[str] = set()
    entries: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        entries.append(item)
    return entries


def normalize_memory(data: Any) -> dict[str, list[str]]:
    """Normalize model output into the structured memory shape."""
    memory = empty_memory()
    if not isinstance(data, dict):
        return memory
    for category in CATEGORIES:
        raw = data.get(category)
        if not isinstance(raw, list):
            continue
        cleaned = []
        for item in raw:
            entry = _clean_entry(item)
            if entry is not None:
                cleaned.append(entry)
        memory[category] = _dedupe_entries(cleaned)[:MAX_PER_CATEGORY]
    return memory


def _coerce(value: Any) -> dict[str, list[str]]:
    """Coerce stored or model memory (dict, legacy string, or None) to structured form."""
    if value is None:
        return empty_memory()
    if isinstance(value, str):
        entry = _clean_entry(value, limit=MAX_LEGACY_CHARS)
        memory = empty_memory()
        if entry:
            memory["facts"] = [entry]
        return memory
    if isinstance(value, dict):
        return normalize_memory(value)
    return empty_memory()


def merge_memory(existing: Any, incoming: Any) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Merge newly extracted memory into existing memory without replacing it.

    Returns ``(merged, added)`` where ``added`` contains only the entries that
    were actually new, for display in the review snapshot.
    """
    old = _coerce(existing)
    new = _coerce(incoming)
    merged = empty_memory()
    added = empty_memory()
    for category in CATEGORIES:
        combined: list[str] = []
        added_entries: list[str] = []
        seen: set[str] = set()
        for entry in old[category]:
            seen.add(entry.casefold())
            combined.append(entry)
        for entry in new[category]:
            key = entry.casefold()
            if key in seen:
                continue
            seen.add(key)
            combined.append(entry)
            added_entries.append(entry)
        merged[category] = combined[-MAX_PER_CATEGORY:]
        added[category] = added_entries[-MAX_PER_CATEGORY:]
    return merged, added


def render_memory(memory: Any) -> str:
    """Render memory as readable text for prompts and the profile page."""
    data = _coerce(memory)
    parts = []
    for category in CATEGORIES:
        entries = data[category]
        if entries:
            parts.append(f"{CATEGORY_LABELS[category]}：" + "；".join(entries))
    return "\n\n".join(parts)
