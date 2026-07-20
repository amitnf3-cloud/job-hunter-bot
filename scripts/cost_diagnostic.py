#!/usr/bin/env python3
"""One-off diagnostic - NOT part of the production pipeline.

Measures REAL input token counts (via the free /v1/messages/count_tokens
endpoint - no generation cost) for a sample of actual Telegram and JobNet
job descriptions, using the exact system prompt/schema/job_summary shape
score_job() sends. Answers: how many tokens does each source actually
cost per job, and what would that cost at Opus vs Sonnet pricing.

Safe to delete once the cost question is answered.
"""

import os
import sys

import anthropic
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from fetch_telegram_messages import fetch_recent_messages, load_config
from filter_messages import filter_messages
from fetch_job_description import get_job_description
from fetch_jobnet_positions import fetch_category_listings, build_job_dict as jobnet_build_job_dict
from fetch_job_description import fetch_job_description as fetch_url_description
from score_job import MODEL, SYSTEM_PROMPT, SCORE_SCHEMA, build_job_summary

# Pricing per 1M tokens (input/output) - from the current model pricing table.
PRICING = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-5 (introductory, through 2026-08-31)": (2.00, 10.00),
}

SAMPLE_SIZE = 5


def measure(client, resume_text, job, label):
    job_summary = build_job_summary(job)
    user_content = f"RESUME:\n{resume_text}\n\nJOB POSTING:\n{job_summary}"

    count = client.messages.count_tokens(
        model=MODEL,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    desc_len = len(job.get("description", ""))
    print(f"  [{label}] description_chars={desc_len}  input_tokens={count.input_tokens}  title={job['title'][:60]!r}")
    return count.input_tokens


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable is not set.")

    telegram_api_id = os.environ.get("TELEGRAM_API_ID")
    telegram_api_hash = os.environ.get("TELEGRAM_API_HASH")
    telegram_session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    if not all([telegram_api_id, telegram_api_hash, telegram_session_string]):
        sys.exit("ERROR: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING must be set.")

    client = anthropic.Anthropic()
    config = load_config()
    resume_text = open("resumes/data_analyst_resume.txt", encoding="utf-8").read()

    print(f"Model under test: {MODEL}\n")

    # --- Telegram sample ---
    print("=== Telegram sample ===")
    with TelegramClient(StringSession(telegram_session_string), int(telegram_api_id), telegram_api_hash) as tclient:
        messages = fetch_recent_messages(tclient, config["telegram"]["group"], config["telegram"]["hours_lookback"])
    matched_pairs = filter_messages(messages, config)

    telegram_tokens = []
    for message, track in matched_pairs[:SAMPLE_SIZE]:
        description, url = get_job_description(message.text)
        job = {
            "title": message.text.strip().splitlines()[0][:120],
            "company_name": "N/A",
            "location": "Israel (via Telegram)",
            "description": description,
        }
        telegram_tokens.append(measure(client, resume_text, job, "Telegram"))

    # --- JobNet sample ---
    print("\n=== JobNet sample ===")
    jobnet_tokens = []
    count_so_far = 0
    for positionid, title, link in fetch_category_listings(1561):
        if count_so_far >= SAMPLE_SIZE:
            break
        description = fetch_url_description(link) or title
        job = jobnet_build_job_dict(title, link, description)
        jobnet_tokens.append(measure(client, resume_text, job, "JobNet"))
        count_so_far += 1

    # --- Summary ---
    def summarize(name, tokens):
        if not tokens:
            print(f"\n{name}: no samples")
            return
        avg = sum(tokens) / len(tokens)
        print(f"\n{name}: {len(tokens)} sample(s), avg input_tokens={avg:.0f}, min={min(tokens)}, max={max(tokens)}")
        for model, (in_price, out_price) in PRICING.items():
            # assume ~150 output tokens per job (small structured JSON reply)
            est_output_tokens = 150
            cost_per_job = (avg / 1_000_000) * in_price + (est_output_tokens / 1_000_000) * out_price
            print(f"    at {model}: ~${cost_per_job:.5f}/job (input ${in_price}/MTok, output ${out_price}/MTok, assuming ~{est_output_tokens} output tokens)")

    summarize("Telegram", telegram_tokens)
    summarize("JobNet", jobnet_tokens)

    all_tokens = telegram_tokens + jobnet_tokens
    if all_tokens:
        avg_all = sum(all_tokens) / len(all_tokens)
        print(f"\nCombined average input_tokens/job: {avg_all:.0f}")

        print("\nExtrapolated to yesterday's 120-job backlog run:")
        for model, (in_price, out_price) in PRICING.items():
            est_output_tokens = 150
            per_job = (avg_all / 1_000_000) * in_price + (est_output_tokens / 1_000_000) * out_price
            print(f"    at {model}: ~${per_job * 120:.2f} for 120 jobs")

        # "Normal day" batch size: Telegram has consistently matched ~4-5
        # pairs/day in real runs so far. JobNet's ongoing (non-backlog) daily
        # volume is NOT yet known - today's 115 was a one-time catch-up of
        # every currently-open listing. 5 is an illustrative placeholder,
        # not a measured number - tomorrow's real run will confirm it.
        normal_day_telegram = 5
        normal_day_jobnet_placeholder = 5
        normal_day_total = normal_day_telegram + normal_day_jobnet_placeholder
        print(f"\nIllustrative 'normal day' ({normal_day_telegram} Telegram + {normal_day_jobnet_placeholder} JobNet placeholder = {normal_day_total} jobs/day - JobNet's ongoing rate is unconfirmed until tomorrow's real run):")
        for model, (in_price, out_price) in PRICING.items():
            est_output_tokens = 150
            per_job = (avg_all / 1_000_000) * in_price + (est_output_tokens / 1_000_000) * out_price
            print(f"    at {model}: ~${per_job * normal_day_total:.4f}/day (~${per_job * normal_day_total * 30:.2f}/30-day month)")


if __name__ == "__main__":
    main()
