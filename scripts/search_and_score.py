#!/usr/bin/env python3
"""Search both tracks for real jobs, score each one against its resume, skip
jobs already seen in a previous run, and email a digest of the rest.

Wires together search_jobs.py (SerpApi Google Jobs search), score_job.py
(Claude API scoring), seen_jobs.py (duplicate tracking), and send_email.py
(the Gmail SMTP digest) into the full daily pipeline.
"""

import os
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from search_jobs import load_config, search_track, get_job_link, get_job_id
from score_job import score_job
from seen_jobs import load_seen, save_seen, prune_old_entries
from send_email import build_email_html, send_email

load_dotenv()  # loads .env into the environment for local runs, if present

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_resume(resume_file):
    return (REPO_ROOT / resume_file).read_text(encoding="utf-8")


def print_scored_jobs(track_name, scored_jobs):
    print(f"\n=== {track_name} ({len(scored_jobs)} jobs scored) ===")
    if not scored_jobs:
        print("  No jobs found.")
        return

    for score, reason, job in scored_jobs:
        title = job.get("title", "N/A")
        company = job.get("company_name", "N/A")
        location = job.get("location", "N/A")

        print(f"\n[{score}/10] {title} | {company} | {location}")
        print(f"  Reason: {reason}")
        print(f"  Link: {get_job_link(job)}")


def main():
    serpapi_key = os.environ.get("SERPAPI_API_KEY")
    if not serpapi_key:
        sys.exit("ERROR: SERPAPI_API_KEY environment variable is not set.")

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
    location = config["location"]["city"]
    min_score = config["scoring"]["min_score_to_include"]
    client = anthropic.Anthropic()

    seen_jobs_path = REPO_ROOT / config["storage"]["seen_jobs_file"]
    seen = prune_old_entries(load_seen(seen_jobs_path))
    today = date.today().isoformat()

    track_results = []
    for track in config["tracks"]:
        resume_text = load_resume(track["resume_file"])
        jobs = search_track(track, location, config["serpapi"], serpapi_key)

        scored_jobs = []
        for job in jobs:
            job_id = get_job_id(job)
            if job_id in seen:
                continue  # already found in a previous run - skip

            result = score_job(job, resume_text, client)
            scored_jobs.append((result["score"], result["reason"], job))
            seen[job_id] = today

        scored_jobs.sort(key=lambda entry: entry[0], reverse=True)
        print_scored_jobs(track["name"], scored_jobs)
        track_results.append((track["name"], scored_jobs))

    save_seen(seen_jobs_path, seen)

    html_body, included_count = build_email_html(track_results, min_score)
    subject = f"{config['email']['subject_prefix']} - {today}"
    send_email(subject, html_body, gmail_address, gmail_app_password, email_to)
    print(f"\nEmail sent to {email_to}: {included_count} job(s) scoring {min_score}+.")


if __name__ == "__main__":
    main()
