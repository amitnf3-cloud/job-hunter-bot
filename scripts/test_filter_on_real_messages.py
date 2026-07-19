#!/usr/bin/env python3
"""Diagnostic: fetch real messages from the Telegram group and run them
through filter_messages(), to see match counts per track and spot keyword
gaps in messages that matched neither track. Read-only - no scoring, no
dedup, nothing gets sent.

By default uses config.yaml's telegram.hours_lookback. Override with the
HOURS_LOOKBACK_OVERRIDE environment variable to check a longer window
without touching the production config, e.g.:

    HOURS_LOOKBACK_OVERRIDE=72 python scripts/test_filter_on_real_messages.py
"""

import os
import sys

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from fetch_telegram_messages import load_config, fetch_recent_messages
from filter_messages import filter_messages

load_dotenv()  # loads .env into the environment for local runs, if present


def main():
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    if not all([api_id, api_hash, session_string]):
        sys.exit(
            "ERROR: TELEGRAM_API_ID, TELEGRAM_API_HASH, and "
            "TELEGRAM_SESSION_STRING environment variables must all be set."
        )

    config = load_config()
    group = config["telegram"]["group"]
    hours_override = os.environ.get("HOURS_LOOKBACK_OVERRIDE")
    hours_lookback = int(hours_override) if hours_override else config["telegram"]["hours_lookback"]

    with TelegramClient(StringSession(session_string), int(api_id), api_hash) as client:
        messages = fetch_recent_messages(client, group, hours_lookback)

    print(f"Fetched {len(messages)} message(s) from the last {hours_lookback}h\n")

    matched_pairs = filter_messages(messages, config)

    counts = {}
    for _, track in matched_pairs:
        counts[track["name"]] = counts.get(track["name"], 0) + 1

    print("=== Matched messages, by track ===")
    for message, track in matched_pairs:
        preview = message.text.replace("\n", " ")[:200]
        print(f"\n[{message.id}] {message.date.isoformat()} -> {track['name']}")
        print(f"  {preview}")

    print("\n=== Matches per track (summary) ===")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    if not counts:
        print("  (no matches at all)")

    matched_ids = {message.id for message, _ in matched_pairs}
    unmatched = [m for m in messages if m.id not in matched_ids]

    print(f"\n=== Unmatched messages ({len(unmatched)} total - review these for keyword gaps) ===")
    for message in unmatched:
        preview = message.text.replace("\n", " ")[:300]
        print(f"\n[{message.id}] {message.date.isoformat()}")
        print(f"  {preview}")


if __name__ == "__main__":
    main()
