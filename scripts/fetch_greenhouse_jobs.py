#!/usr/bin/env python3
"""Fetch job postings from Greenhouse's public Job Board API - a third job
source alongside Telegram and JobNet, feeding the same
score_job()/dedup/email pipeline for one combined daily digest.

Covers the 7 companies confirmed (via manual research) to use Greenhouse.
Uses the documented, unauthenticated Job Board API
(https://developers.greenhouse.io/job-board.html) rather than scraping -
one GET per company with `content=true` returns every open job's full
HTML description in a single call, no per-job requests needed.
"""

import requests

from fetch_job_description import extract_visible_text, MAX_DESCRIPTION_LENGTH
from filter_messages import matches_location, matching_tracks

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"
REQUEST_TIMEOUT_SECONDS = 10

# (display name, Greenhouse board token) - tokens confirmed by finding each
# company's real job-boards.greenhouse.io / boards.greenhouse.io URLs.
COMPANIES = [
    ("Wiz", "wizinc"),
    ("Riskified", "riskified"),
    ("Taboola", "taboola"),
    ("Armis", "armissecurity"),
    ("MyHeritage", "MyHeritage"),
    ("JFrog", "jfrog"),
    ("Payoneer", "payoneer"),
]


def fetch_company_jobs(token, timeout=REQUEST_TIMEOUT_SECONDS):
    """Return the raw job list (with full HTML content) for one company's
    Greenhouse board, or an empty list if the token is wrong, the board is
    empty, or the request fails."""
    url = f"{API_BASE}/{token}/jobs?content=true"
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return []
    return response.json().get("jobs", [])


def build_job_dict(title, company_name, location, description, link):
    """Shaped identically to Telegram's/JobNet's build_job_dict() output,
    so all sources feed the same score_job() call and email rendering."""
    return {
        "title": title,
        "company_name": company_name,
        "location": location,
        "company_description": None,
        "description": description,
        "link": link,
    }


def get_job_id(greenhouse_job_id, track):
    """Namespaced like JobNet's jobnet: keys, to avoid collisions with
    Telegram's bare-integer message-id keys and JobNet's jobnet: keys."""
    return f"greenhouse:{greenhouse_job_id}:{track['id']}"


def fetch_greenhouse_jobs(config, seen=None):
    """Return a list of (job_id, job, track) tuples for Greenhouse postings
    matching a track's keywords and the shared location filter. Postings
    whose job_id is already in `seen` are skipped before scoring."""
    seen = seen or {}
    location_keywords = config["telegram"]["location_keywords"]
    location_exclude_keywords = config["telegram"]["location_exclude_keywords"]
    tracks = config["tracks"]

    matched = []
    for company_name, token in COMPANIES:
        for job in fetch_company_jobs(token):
            title = job.get("title", "")
            location = (job.get("location") or {}).get("name") or "N/A"
            link = job.get("absolute_url", "")
            raw_content = job.get("content", "")
            description = extract_visible_text(raw_content)[:MAX_DESCRIPTION_LENGTH] if raw_content else title

            text_for_filtering = f"{title} {location} {description}"
            if not matches_location(text_for_filtering, location_keywords, location_exclude_keywords):
                continue

            for track in matching_tracks(text_for_filtering, tracks):
                job_id = get_job_id(job.get("id"), track)
                if job_id in seen:
                    continue
                job_dict = build_job_dict(title, company_name, location, description, link)
                matched.append((job_id, job_dict, track))
    return matched
