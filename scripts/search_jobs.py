#!/usr/bin/env python3
"""Quick test: query SerpApi's Google Jobs search for both tracks and print
raw results (title, company, location, link). No scoring, no email, no
duplicate tracking yet - just a sanity check that the search works."""

import os
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()  # loads .env into the environment for local runs, if present

SERPAPI_URL = "https://serpapi.com/search"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def search_track(track, location, serpapi_cfg, api_key):
    params = {
        "engine": serpapi_cfg["engine"],
        "q": f"{track['search_query']} {location}",
        "location": location,
        "google_domain": serpapi_cfg["google_domain"],
        "hl": serpapi_cfg["hl"],
        "gl": serpapi_cfg["gl"],
        "api_key": api_key,
    }
    response = requests.get(SERPAPI_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"SerpApi error: {data['error']}")

    return data.get("jobs_results", [])


def get_job_link(job):
    apply_options = job.get("apply_options") or []
    return apply_options[0]["link"] if apply_options else job.get("share_link", "N/A")


def get_job_id(job):
    """A stable, unique key for a job posting, used for duplicate tracking."""
    return job.get("job_id") or get_job_link(job)


def print_jobs(track_name, jobs):
    print(f"\n=== {track_name} ({len(jobs)} results) ===")
    if not jobs:
        print("  No jobs found.")
        return

    for job in jobs:
        title = job.get("title", "N/A")
        company = job.get("company_name", "N/A")
        location = job.get("location", "N/A")

        print(f"- {title} | {company} | {location}")
        print(f"  {get_job_link(job)}")


def main():
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        sys.exit("ERROR: SERPAPI_API_KEY environment variable is not set.")

    config = load_config()
    location = config["location"]["city"]

    for track in config["tracks"]:
        jobs = search_track(track, location, config["serpapi"], api_key)
        print_jobs(track["name"], jobs)


if __name__ == "__main__":
    main()
