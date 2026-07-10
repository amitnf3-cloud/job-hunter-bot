#!/usr/bin/env python3
"""Diagnostic: fetch today's real messages, filter them, then run each
matched message through get_job_description() to see which career pages
fetch successfully vs. fall back to Telegram-only text. Read-only - no
scoring, no dedup, nothing gets sent.
"""

import os
import sys

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from fetch_telegram_messages import load_config, fetch_recent_messages
from filter_messages import filter_messages
from fetch_job_description import get_job_description

load_dotenv()  # loads .env into the environment for local runs, if present

PREVIEW_LENGTH = 300


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
    hours_lookback = config["telegram"]["hours_lookback"]

    with TelegramClient(StringSession(session_string), int(api_id), api_hash) as client:
        messages = fetch_recent_messages(client, group, hours_lookback)

    matched_pairs = filter_messages(messages, config)
    print(f"{len(matched_pairs)} matched (message, track) pair(s) to test\n")

    fetched_count = 0
    fallback_count = 0

    for message, track in matched_pairs:
        description, url = get_job_description(message.text)
        used_fetch = bool(url) and description != message.text
        if used_fetch:
            fetched_count += 1
        else:
            fallback_count += 1

        status = "FETCHED" if used_fetch else "FALLBACK (Telegram text only)"
        print(f"[{message.id}] track={track['id']} | {status}")
        print(f"  url: {url or '(none found)'}")
        print(f"  description length: {len(description)} chars")
        print(f"  preview: {description[:PREVIEW_LENGTH].replace(chr(10), ' ')}")
        print()

    print(f"=== Summary: {fetched_count} fetched, {fallback_count} fell back to Telegram text only ===")


if __name__ == "__main__":
    main()
