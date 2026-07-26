"""Persistent state: seen jobs, user filters, tracked-company edits, Telegram
offset. Stored as one JSON file that the GitHub Actions workflow commits back
to the repo after each run."""

import json
from datetime import datetime, timedelta, timezone

from .config import STATE_FILE

SEEN_RETENTION_DAYS = 120

DEFAULT_STATE = {
    "initialized": False,
    "seen": {},              # uid -> ISO date first seen
    "filters": {
        "keywords": [],      # title must contain one of these (empty = any)
        "locations": [],     # location must contain one of these (empty = any)
        "remote_only": False,
        "paused": False,
    },
    "subscribers": [],       # extra chat ids subscribed via /start (owner is implicit)
    "extra_companies": {},   # ats -> [slug] added via /addcompany
    "removed_companies": [],  # "ats:slug" removed via /delcompany
    "tg_offset": 0,          # Telegram getUpdates offset
}


def load_state() -> dict:
    state = json.loads(json.dumps(DEFAULT_STATE))  # deep copy of defaults
    if STATE_FILE.exists():
        state.update(json.loads(STATE_FILE.read_text()))
        for key, value in DEFAULT_STATE["filters"].items():
            state["filters"].setdefault(key, value)
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True))


def prune_seen(state: dict) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)).date().isoformat()
    state["seen"] = {uid: d for uid, d in state["seen"].items() if d >= cutoff}


def merged_companies(base: dict[str, list[str]], state: dict) -> dict[str, list[str]]:
    """companies.json plus /addcompany additions, minus /delcompany removals."""
    removed = set(state.get("removed_companies", []))
    merged: dict[str, list[str]] = {}
    for ats in set(base) | set(state.get("extra_companies", {})):
        slugs = list(base.get(ats, [])) + [
            s for s in state.get("extra_companies", {}).get(ats, [])
            if s not in base.get(ats, [])
        ]
        merged[ats] = [s for s in slugs if f"{ats}:{s}" not in removed]
    return merged
