#!/usr/bin/env python3
"""One-off diagnostic - NOT part of the production pipeline.

Verifies each candidate Greenhouse board token in fetch_greenhouse_jobs.py
actually resolves against the real API (not a 404/typo'd token), and shows
how many jobs it returns and how many match our tracks/location filter.
No secrets needed - the Job Board API is public and unauthenticated.

Safe to delete once the token list is confirmed correct.
"""

import sys

import requests

from fetch_greenhouse_jobs import API_BASE, COMPANIES, USER_AGENT, fetch_greenhouse_jobs
from run_daily_pipeline import load_config


def check_token(token):
    """Return (status_code_or_None, job_count) for one board token, making
    exactly one request (unlike fetch_company_jobs, this surfaces the raw
    status code so a 404 typo is distinguishable from a valid board with
    zero open jobs right now)."""
    url = f"{API_BASE}/{token}/jobs?content=true"
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as e:
        return None, 0, str(e)
    if response.status_code != 200:
        return response.status_code, 0, None
    jobs = response.json().get("jobs", [])
    return response.status_code, len(jobs), None


def main():
    config = load_config()
    bad_tokens = []

    for company_name, token in COMPANIES:
        status, job_count, error = check_token(token)
        if error:
            print(f"{company_name:15s} token={token:15s} -> REQUEST FAILED: {error}")
            bad_tokens.append(token)
        elif status != 200:
            print(f"{company_name:15s} token={token:15s} -> HTTP {status} (likely wrong token)")
            bad_tokens.append(token)
        else:
            print(f"{company_name:15s} token={token:15s} -> HTTP 200, {job_count} open job(s)")

    print("\n--- Track/location-matched jobs (what the pipeline would actually score) ---")
    matched = fetch_greenhouse_jobs(config)
    by_company = {}
    for job_id, job, track in matched:
        by_company.setdefault(job["company_name"], []).append((job["title"], track["id"], job["location"]))

    for company_name, _ in COMPANIES:
        rows = by_company.get(company_name, [])
        print(f"\n{company_name}: {len(rows)} matched")
        for title, track_id, location in rows[:5]:
            print(f"  [{track_id}] {title}  ({location})")
        if len(rows) > 5:
            print(f"  ... and {len(rows) - 5} more")

    print(f"\nTotal matched across all 7 companies: {len(matched)}")

    if bad_tokens:
        sys.exit(f"\nERROR: these tokens are wrong/failing: {bad_tokens}")


if __name__ == "__main__":
    main()
