#!/usr/bin/env python3
"""Quick test: connect to Telegram via Telethon and print raw recent
messages from the configured group. No link extraction, no scoring, no
dedup yet - just a sanity check that the connection and message fetch work.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()  # loads .env into the environment for local runs, if present

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
MAX_MESSAGES = 500  # safety cap regardless of the time window


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_recent_messages(client, group, hours_lookback):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_lookback)
    entity = client.get_entity(group)

    recent = []
    for message in client.iter_messages(entity, limit=MAX_MESSAGES):
        if message.date < cutoff:
            break  # Telethon returns newest-first; anything older, stop
        if message.text:
            recent.append(message)
    return recent


def print_messages(messages):
    print(f"\n{len(messages)} message(s) found\n")
    for message in messages:
        preview = message.text.replace("\n", " ")[:200]
        print(f"[{message.id}] {message.date.isoformat()}")
        print(f"  {preview}")
        print()


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
    if not group:
        sys.exit("ERROR: config.yaml telegram.group is empty - fill in the group username or chat ID.")

    with TelegramClient(StringSession(session_string), int(api_id), api_hash) as client:
        messages = fetch_recent_messages(client, group, hours_lookback)
        print_messages(messages)


if __name__ == "__main__":
    main()
