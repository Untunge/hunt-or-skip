"""Load the curated program dataset (ships with the package)."""

from __future__ import annotations

import json
from pathlib import Path

DATA_FILE = Path(__file__).with_name("programs.json")


def load_programs() -> tuple[dict, list[dict]]:
    """Return (meta, programs) from the bundled programs.json."""
    with open(DATA_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("meta", {}), data.get("programs", [])


def find_program(programs: list[dict], query: str) -> dict | None:
    """Find a program by id or name (case-insensitive, exact then prefix)."""
    q = query.strip().lower()
    for p in programs:
        if p["id"].lower() == q or p["name"].lower() == q:
            return p
    matches = [p for p in programs if p["id"].lower().startswith(q)]
    if len(matches) == 1:
        return matches[0]
    matches = [p for p in programs if q in p["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def suggest_programs(programs: list[dict], query: str) -> list[str]:
    """Return ids of programs whose id or name contains the query."""
    q = query.strip().lower()
    return [p["id"] for p in programs if q in p["id"].lower() or q in p["name"].lower()]
