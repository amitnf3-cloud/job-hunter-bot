#!/usr/bin/env python3
"""Search both tracks for real jobs and score each one against its resume.

Wires search_jobs.py (SerpApi Google Jobs search) into score_job.py (Claude
API scoring). Prints every job found, sorted by score, highest first. No
duplicate tracking or email yet - just the combined search+score pipeline.
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from search_jobs import load_config, search_track, get_job_link
from score_job import score_job

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

    config = load_config()
    location = config["location"]["city"]
    client = anthropic.Anthropic()

    for track in config["tracks"]:
        resume_text = load_resume(track["resume_file"])
        jobs = search_track(track, location, config["serpapi"], serpapi_key)

        scored_jobs = []
        for job in jobs:
            result = score_job(job, resume_text, client)
            scored_jobs.append((result["score"], result["reason"], job))

        scored_jobs.sort(key=lambda entry: entry[0], reverse=True)
        print_scored_jobs(track["name"], scored_jobs)


if __name__ == "__main__":
    main()
