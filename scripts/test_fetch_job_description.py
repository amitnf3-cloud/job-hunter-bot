#!/usr/bin/env python3
"""Diagnostic: fetch recent messages, filter them, then run each matched
message through get_job_description() to see which career pages fetch
successfully vs. fall back to Telegram-only text, broken down by career
platform (Workday, Greenhouse, etc). Read-only - no scoring, no dedup,
nothing gets sent.

Use --hours to look back further than the production config's
hours_lookback, to get a bigger sample for this diagnostic without
changing the real setting (e.g. --hours 72 for a 3-day sample).
"""

import argparse
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from fetch_telegram_messages import load_config, fetch_recent_messages
from filter_messages import filter_messages
from fetch_job_description import get_job_description

load_dotenv()  # loads .env into the environment for local runs, if present

PREVIEW_LENGTH = 300

PLATFORM_DOMAINS = {
    "myworkdayjobs.com": "Workday",
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "workable.com": "Workable",
    "smartrecruiters.com": "SmartRecruiters",
    "icims.com": "iCIMS",
    "taleo.net": "Taleo",
    "successfactors.com": "SuccessFactors",
    "comeet.co": "Comeet",
    "comeet.com": "Comeet",
    "breezy.hr": "Breezy",
    "jobvite.com": "Jobvite",
    "ashbyhq.com": "Ashby",
    "linkedin.com": "LinkedIn",
}


def classify_platform(url):
    if not url:
        return "(no link)"
    host = urlparse(url).netloc.lower()
    for domain, name in PLATFORM_DOMAINS.items():
        if host.endswith(domain):
            return name
    return f"Other ({host})"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help="Override the lookback window in hours (default: config.yaml's telegram.hours_lookback)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

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
    hours_lookback = args.hours or config["telegram"]["hours_lookback"]

    with TelegramClient(StringSession(session_string), int(api_id), api_hash) as client:
        messages = fetch_recent_messages(client, group, hours_lookback)

    matched_pairs = filter_messages(messages, config)
    print(f"Looking back {hours_lookback}h: {len(matched_pairs)} matched (message, track) pair(s) to test\n")

    platform_counts = {}  # platform -> {"fetched": N, "fallback": N}
    fetched_count = 0
    fallback_count = 0

    for message, track in matched_pairs:
        description, url = get_job_description(message.text)
        used_fetch = bool(url) and description != message.text
        platform = classify_platform(url)

        stats = platform_counts.setdefault(platform, {"fetched": 0, "fallback": 0})
        if used_fetch:
            fetched_count += 1
            stats["fetched"] += 1
        else:
            fallback_count += 1
            stats["fallback"] += 1

        status = "FETCHED" if used_fetch else "FALLBACK (Telegram text only)"
        print(f"[{message.id}] track={track['id']} platform={platform} | {status}")
        print(f"  url: {url or '(none found)'}")
        print(f"  description length: {len(description)} chars")
        print(f"  preview: {description[:PREVIEW_LENGTH].replace(chr(10), ' ')}")
        print()

    print("=== Breakdown by platform ===")
    for platform, stats in sorted(platform_counts.items(), key=lambda kv: -(kv[1]["fetched"] + kv[1]["fallback"])):
        total = stats["fetched"] + stats["fallback"]
        print(f"  {platform}: {total} total - {stats['fetched']} fetched, {stats['fallback']} fell back")

    print(f"\n=== Overall: {fetched_count} fetched, {fallback_count} fell back to Telegram text only ===")


if __name__ == "__main__":
    main()
