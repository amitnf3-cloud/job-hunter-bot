#!/usr/bin/env python3
"""One-off diagnostic - NOT part of the production pipeline.

Verifies each candidate Comeet (uid, token) pair in fetch_comeet_jobs.py
actually resolves against the real API, shows how many jobs match our
tracks/location filter, and - critically - fetches a real description for
a couple of matched jobs to confirm fetch_position_description() actually
extracts real per-job content (not duplicate site-chrome boilerplate)
from Comeet's hosted job pages. No secrets needed - the Careers API uses
a public read-only token.

Safe to delete once the token list and description-fetch approach are
confirmed correct.
"""

import sys

import requests

from fetch_comeet_jobs import API_BASE, COMPANIES, USER_AGENT, fetch_comeet_jobs
from run_daily_pipeline import load_config


def check_token(uid, token):
    """Return (status_code_or_None, position_count, error) for one
    uid/token pair, surfacing the raw status code so a wrong uid/token
    (non-200) is distinguishable from a valid board with zero open
    positions right now (which is not a failure)."""
    url = f"{API_BASE}/{uid}/positions"
    try:
        response = requests.get(url, params={"token": token}, timeout=10, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as e:
        return None, 0, str(e)
    if response.status_code != 200:
        return response.status_code, 0, None
    data = response.json()
    positions = data if isinstance(data, list) else data.get("positions", [])
    return response.status_code, len(positions), None


def main():
    config = load_config()
    bad_companies = []

    for company_name, uid, token in COMPANIES:
        status, position_count, error = check_token(uid, token)
        if error:
            print(f"{company_name:22s} uid={uid:8s} -> REQUEST FAILED: {error}")
            bad_companies.append(company_name)
        elif status != 200:
            print(f"{company_name:22s} uid={uid:8s} -> HTTP {status} (likely wrong uid/token)")
            bad_companies.append(company_name)
        else:
            print(f"{company_name:22s} uid={uid:8s} -> HTTP 200, {position_count} open position(s)")

    print("\n--- Track/location-matched jobs (what the pipeline would actually score) ---")
    matched = fetch_comeet_jobs(config)
    by_company = {}
    for job_id, job, track in matched:
        by_company.setdefault(job["company_name"], []).append((job["title"], track["id"], job["location"], job["description"]))

    for company_name, _, _ in COMPANIES:
        rows = by_company.get(company_name, [])
        print(f"\n{company_name}: {len(rows)} matched")
        for title, track_id, location, description in rows[:5]:
            desc_len = len(description)
            desc_preview = description[:100].replace("\n", " ")
            print(f"  [{track_id}] {title}  ({location})  desc_chars={desc_len}")
            print(f"    desc preview: {desc_preview!r}")
        if len(rows) > 5:
            print(f"  ... and {len(rows) - 5} more")

    print(f"\nTotal matched across all {len(COMPANIES)} companies: {len(matched)}")

    # Description-fetch quality check: a bare-title fallback is one
    # failure mode, but Abra's live run showed a sneakier one - the
    # fetch "succeeds" (passes the min-length check) but returns
    # identical site-chrome/error-shell boilerplate for every job, not
    # real per-job content. Check both.
    print("\n--- Description fetch quality check ---")
    checked_descriptions = []
    for job_id, job, track in matched[:5]:
        is_fallback = job["description"] == job["title"]
        status = "FALLBACK TO TITLE" if is_fallback else "fetched content"
        print(f"  {job['title']} -> {status} ({len(job['description'])} chars)")
        if not is_fallback:
            checked_descriptions.append(job["description"])

    duplicates_warning = False
    if len(checked_descriptions) >= 2 and len(set(checked_descriptions)) == 1:
        duplicates_warning = True
        print(
            "\nWARNING: every fetched description is IDENTICAL across different jobs - "
            "this is almost certainly site chrome/boilerplate (e.g. a JS-rendered page's "
            "static shell), not real per-job content, even though it passed the "
            "minimum-length check. Preview of the (bogus) shared content:"
        )
        print(f"  {checked_descriptions[0][:300]!r}")

    if bad_companies:
        sys.exit(f"\nERROR: these companies are wrong/failing: {bad_companies}")
    if duplicates_warning:
        sys.exit("\nERROR: description fetching is not producing real per-job content - do not wire this in yet.")


if __name__ == "__main__":
    main()
