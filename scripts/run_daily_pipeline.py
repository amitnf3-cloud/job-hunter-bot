#!/usr/bin/env python3
"""Daily pipeline: fetch recent Telegram messages, filter by track/location
keywords, fetch each matching job's real description (falling back to the
Telegram text when that fails), score against the matching resume, skip
jobs already seen, and email a digest of the rest.

Replaces the earlier SerpApi/Google Jobs source, which had no usable
coverage for Israel.
"""

import os
import sys
from datetime import date
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from fetch_telegram_messages import fetch_recent_messages
from filter_messages import filter_messages
from fetch_job_description import get_job_description
from score_job import score_job
from seen_jobs import load_seen, save_seen, prune_old_entries
from send_email import build_email_html, send_email

load_dotenv()  # loads .env into the environment for local runs, if present

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_resume(resume_file):
    return (REPO_ROOT / resume_file).read_text(encoding="utf-8")


def build_job_dict(message, description, url, group):
    """Telegram messages aren't structured like SerpApi results - there's
    no separate title/company field, just free text plus whatever we could
    fetch. Use the message's first line as a human-readable headline and
    fall back to a link back to the Telegram post itself if no real URL
    was found."""
    first_line = message.text.strip().splitlines()[0][:120]
    link = url or f"https://t.me/{group}/{message.id}"
    return {
        "title": first_line,
        "company_name": "N/A",
        "location": "Israel (via Telegram)",
        "description": description,
        "link": link,
    }


def get_job_id(message, track):
    return f"{message.id}:{track['id']}"


def print_scored_jobs(track_name, scored_jobs):
    print(f"\n=== {track_name} ({len(scored_jobs)} jobs scored) ===")
    if not scored_jobs:
        print("  No jobs found.")
        return

    for score, reason, job in scored_jobs:
        print(f"\n[{score}/10] {job['title']}")
        print(f"  Reason: {reason}")
        print(f"  Link: {job['link']}")


def main():
    telegram_api_id = os.environ.get("TELEGRAM_API_ID")
    telegram_api_hash = os.environ.get("TELEGRAM_API_HASH")
    telegram_session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    if not all([telegram_api_id, telegram_api_hash, telegram_session_string]):
        sys.exit(
            "ERROR: TELEGRAM_API_ID, TELEGRAM_API_HASH, and "
            "TELEGRAM_SESSION_STRING environment variables must all be set."
        )

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable is not set.")

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    email_to = os.environ.get("EMAIL_TO")
    if not all([gmail_address, gmail_app_password, email_to]):
        sys.exit(
            "ERROR: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and EMAIL_TO "
            "environment variables must all be set."
        )

    config = load_config()
    group = config["telegram"]["group"]
    hours_lookback = config["telegram"]["hours_lookback"]
    min_score = config["scoring"]["min_score_to_include"]

    client_ai = anthropic.Anthropic()

    seen_jobs_path = REPO_ROOT / config["storage"]["seen_jobs_file"]
    seen = prune_old_entries(load_seen(seen_jobs_path))
    today = date.today().isoformat()

    with TelegramClient(StringSession(telegram_session_string), int(telegram_api_id), telegram_api_hash) as client:
        messages = fetch_recent_messages(client, group, hours_lookback)

    matched_pairs = filter_messages(messages, config)
    print(f"{len(messages)} message(s) fetched, {len(matched_pairs)} matched (message, track) pair(s)")

    resumes = {track["id"]: load_resume(track["resume_file"]) for track in config["tracks"]}
    scored_by_track_id = {track["id"]: [] for track in config["tracks"]}

    for message, track in matched_pairs:
        job_id = get_job_id(message, track)
        if job_id in seen:
            continue  # already scored in a previous run - skip

        description, url = get_job_description(message.text)
        job = build_job_dict(message, description, url, group)

        result = score_job(job, resumes[track["id"]], client_ai)
        scored_by_track_id[track["id"]].append((result["score"], result["reason"], job))
        seen[job_id] = today

    save_seen(seen_jobs_path, seen)

    track_results = []
    for track in config["tracks"]:
        scored_jobs = scored_by_track_id[track["id"]]
        scored_jobs.sort(key=lambda entry: entry[0], reverse=True)
        print_scored_jobs(track["name"], scored_jobs)
        track_results.append((track["name"], scored_jobs))

    html_body, included_count = build_email_html(track_results, min_score)
    subject = f"{config['email']['subject_prefix']} - {today}"
    send_email(subject, html_body, gmail_address, gmail_app_password, email_to)
    print(f"\nEmail sent to {email_to}: {included_count} job(s) scoring {min_score}+.")


if __name__ == "__main__":
    main()
