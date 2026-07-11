#!/usr/bin/env python3
"""Track which jobs have already been found, so the same job is never
included twice. Jobs are keyed by a stable ID mapped to the date they were
first seen. Entries older than MAX_AGE_DAYS are dropped so the file
doesn't grow forever.
"""

import json
from datetime import date, timedelta
from pathlib import Path

MAX_AGE_DAYS = 60


def load_seen(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_seen(path: Path, seen: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, sort_keys=True)
        f.write("\n")


def prune_old_entries(seen: dict, max_age_days: int = MAX_AGE_DAYS) -> dict:
    cutoff = date.today() - timedelta(days=max_age_days)
    return {
        job_id: seen_date
        for job_id, seen_date in seen.items()
        if date.fromisoformat(seen_date) >= cutoff
    }
