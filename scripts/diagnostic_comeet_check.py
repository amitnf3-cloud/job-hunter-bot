#!/usr/bin/env python3
"""One-off diagnostic - NOT part of the production pipeline.

Verifies each candidate Comeet (uid, token) pair in fetch_comeet_jobs.py
actually resolves against the real API, shows how many jobs match our
tracks/location filter, and - critically - fetches a real description for
a couple of matched jobs to confirm fetch_job_description() actually
extracts usable text from Comeet's hosted job pages (the API itself has
no description field at all, confirmed via explore_comeet.py). No
secrets needed - the Careers API uses a public read-only token.

Safe to delete once the token list and description-fetch approach are
confirmed correct.
"""

import sys

from fetch_comeet_jobs import COMPANIES, fetch_company_positions, fetch_comeet_jobs
from fetch_job_description import fetch_job_description
from run_daily_pipeline import load_config


def main():
    config = load_config()
    bad_companies = []

    for company_name, uid, token in COMPANIES:
        positions = fetch_company_positions(uid, token)
        if not positions:
            print(f"{company_name:22s} uid={uid:8s} -> 0 positions (EMPTY OR FAILED - check uid/token!)")
            bad_companies.append(company_name)
        else:
            print(f"{company_name:22s} uid={uid:8s} -> {len(positions)} open position(s)")

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

    # Description-fetch sanity check: for up to 3 matched jobs, confirm
    # the fetched description is real content, not just the bare title
    # fallback (which would mean fetch_job_description() isn't actually
    # extracting anything from Comeet's hosted pages).
    print("\n--- Description fetch quality check ---")
    checked = 0
    thin_descriptions = 0
    for job_id, job, track in matched:
        if checked >= 5:
            break
        checked += 1
        is_fallback = job["description"] == job["title"]
        status = "FALLBACK TO TITLE (fetch_job_description returned nothing usable)" if is_fallback else "real description fetched"
        print(f"  {job['title']} -> {status} ({len(job['description'])} chars)")
        if is_fallback:
            thin_descriptions += 1

    if bad_companies:
        sys.exit(f"\nERROR: these companies are wrong/failing: {bad_companies}")
    if checked and thin_descriptions == checked:
        print(
            "\nWARNING: every checked job fell back to the bare title - "
            "fetch_job_description() may not be extracting real content "
            "from Comeet's hosted job pages. Investigate before relying "
            "on this for scoring quality."
        )


if __name__ == "__main__":
    main()
