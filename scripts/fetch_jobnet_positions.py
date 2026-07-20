#!/usr/bin/env python3
"""Fetch job postings from JobNet (jobnet.co.il) as a second job source
alongside Telegram - both feed the same score_job()/dedup/email pipeline
so the result is one combined daily digest, not two separate emails.

JobNet organizes postings into "sub-profession" categories (a `subprofid`
query param) with simple GET-based, server-rendered results pages - no
login/session/JS-rendering required (confirmed by manually exploring
https://www.jobnet.co.il/AllCategories and https://www.jobnet.co.il/jobs).
There is no dedicated "Project Manager" category in JobNet's taxonomy
(the only project-related category is a narrow AI-specific one), so this
source only covers Operations postings for that track - Telegram already
covers general PM roles reasonably well.

There's also no region/location URL parameter, so location filtering
reuses the same permissive keyword approach as the Telegram source
(filter_messages.matches_location) rather than a server-side filter.
"""

import re

import requests
from bs4 import BeautifulSoup

from fetch_job_description import fetch_job_description
from filter_messages import matches_location

BASE_URL = "https://www.jobnet.co.il"
USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"
REQUEST_TIMEOUT_SECONDS = 10
MAX_PAGES_PER_CATEGORY = 5  # safety cap - real categories rarely exceed this

# subprofid values per track, found by manually exploring
# https://www.jobnet.co.il/AllCategories. JobNet has no generic "Project
# Manager" category (only a narrow AI-specific one) - Telegram already
# covers general PM roles, so project_manager only gets the
# Operations-family categories here.
CATEGORY_IDS_BY_TRACK = {
    "data_analyst": [1561, 683],  # Data Analyst; DWH / BO / BI
    "project_manager": [1202, 1203, 1204, 1205, 1206, 732, 1057, 1088, 1509],  # תפעול (Operations) family
}

POSITIONID_RE = re.compile(r"positionid=(\d+)")


def _category_url(subprofid, page):
    if page == 1:
        return f"{BASE_URL}/jobs?subprofid={subprofid}"
    return f"{BASE_URL}/jobs?subprofid={subprofid}&p={page}"


def fetch_category_listings(subprofid, timeout=REQUEST_TIMEOUT_SECONDS):
    """Yield (positionid, title, link) for every listing in a category,
    paging through results until a page returns nothing new."""
    seen_ids = set()
    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        url = _category_url(subprofid, page)
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
        except requests.RequestException:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"positionid=\d+"))

        new_this_page = 0
        for a in links:
            match = POSITIONID_RE.search(a["href"])
            if not match:
                continue
            positionid = match.group(1)
            if positionid in seen_ids:
                continue
            seen_ids.add(positionid)
            new_this_page += 1
            title = a.get_text(strip=True)
            link = f"{BASE_URL}/jobs?positionid={positionid}"
            yield positionid, title, link

        if new_this_page == 0:
            break  # no more results - reached the last page


def build_job_dict(title, link, description):
    """Shaped identically to Telegram's build_job_dict() output in
    run_daily_pipeline.py, so both sources feed the same score_job() call
    and email rendering."""
    return {
        "title": title,
        "company_name": "N/A",
        "location": "Israel (via JobNet)",
        "company_description": None,
        "description": description,
        "link": link,
    }


def fetch_jobnet_jobs(config):
    """Return a list of (job, track, positionid) tuples for JobNet
    postings matching a track's mapped categories and the shared location
    filter. positionid is returned separately (not embedded in the job
    dict) so the caller can build a dedup key namespaced from Telegram's
    message-id-based keys, e.g. f"jobnet:{positionid}:{track['id']}".
    """
    location_keywords = config["telegram"]["location_keywords"]
    location_exclude_keywords = config["telegram"]["location_exclude_keywords"]

    matched = []
    for track in config["tracks"]:
        for subprofid in CATEGORY_IDS_BY_TRACK.get(track["id"], []):
            for positionid, title, link in fetch_category_listings(subprofid):
                description = fetch_job_description(link) or title
                if not matches_location(f"{title} {description}", location_keywords, location_exclude_keywords):
                    continue
                job = build_job_dict(title, link, description)
                matched.append((job, track, positionid))
    return matched
