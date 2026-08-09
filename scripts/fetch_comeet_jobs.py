#!/usr/bin/env python3
"""Fetch job postings from Comeet's public Careers API - a fourth job
source alongside Telegram, JobNet, and Greenhouse, feeding the same
score_job()/dedup/email pipeline for one combined daily digest.

Covers the 10 companies confirmed (via manual exploration, see
explore_comeet.py) to expose a working Comeet Careers API with a
resolvable company uid + token. mend.io and HiBob use a different HTML
template that our COMPANY_DATA extractor couldn't parse - tracked
separately rather than blocking the other ten.

Unlike Greenhouse, Comeet's API has no description field anywhere -
confirmed live on both the positions list AND the single-position detail
endpoint, for every company checked. Real description text only exists
on each position's own hosted page, so each track/location-matched
position's description is fetched from there via fetch_job_description()
(the same generic HTML extractor JobNet/Telegram already use), falling
back to the bare title if that fails - fetched only for matches, not the
full listing, to keep this cheap.
"""

import requests

from fetch_job_description import fetch_job_description
from filter_messages import matching_tracks

API_BASE = "https://www.comeet.co/careers-api/2.0/company"
USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"
REQUEST_TIMEOUT_SECONDS = 10

# (display name, Comeet company uid, Comeet public token) - both are
# deliberately embedded in that company's own public careers page HTML
# (client-side, for Comeet's own embed widget to call), so they're public
# read-only identifiers, not secrets. Confirmed via live exploration
# against the real API (see explore_comeet.py).
COMPANIES = [
    ("Lasso Security", "F9.008", "9F845C81DE813F045C84FC031D845C89F89F8"),
    ("mPrest", "38.005", "835313E290939730106A313E0189F2909"),
    ("Natural Intelligence", "71.001", "1715C47357355C45C4A17CF9CF9735"),
    ("Elementor", "A3.00F", "3AF126BB0D161A3AF161A00B0D126B"),
    ("Landa", "A4.000", "4A017201720250012802060DE0DE002060"),
    ("Skai", "22.00A", "22A8A81150454CFC115022AAD2F26137A"),
    ("BioCatch", "03.00E", "30EF4630E92A1562156292A92A61C92A"),
    ("CodeValue", "81.009", "1896249367AD189DD1C48ABFDD1189"),
    ("Pentera", "C5.00D", "5CD1D013435289B343501D012E682E68289B"),
    ("Abra", "12.003", "21384C109806394262131098213426"),
]


def fetch_company_positions(uid, token, timeout=REQUEST_TIMEOUT_SECONDS):
    """Return the raw position list for one company's Comeet board, or an
    empty list if the uid/token is wrong, the board is empty, or the
    request fails."""
    url = f"{API_BASE}/{uid}/positions"
    try:
        response = requests.get(url, params={"token": token}, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return []
    data = response.json()
    return data if isinstance(data, list) else data.get("positions", [])


def build_job_dict(title, company_name, location, description, link):
    """Shaped identically to the other sources' build_job_dict() output,
    so all sources feed the same score_job() call and email rendering."""
    return {
        "title": title,
        "company_name": company_name,
        "location": location,
        "company_description": None,
        "description": description,
        "link": link,
    }


def get_job_id(comeet_position_uid, track):
    """Namespaced like the other sources' dedup keys, to avoid
    collisions across sources."""
    return f"comeet:{comeet_position_uid}:{track['id']}"


def _location_is_relevant(location):
    """Same lesson learned from Greenhouse: Comeet-hosted boards can be
    global company-wide listings too (confirmed live - Skai's NYC
    posting has country='US'), with a clean structured location field
    per job - so, unlike Telegram/JobNet's Israel-only sources, default
    to EXCLUDE unless the location's country code is explicitly Israel."""
    return (location or {}).get("country") == "IL"


def fetch_comeet_jobs(config, seen=None):
    """Return a list of (job_id, job, track) tuples for Comeet postings
    matching a track's keywords and the Israel-only location filter.
    Postings whose job_id is already in `seen` are skipped before the
    (network-costly) description fetch, not just before scoring."""
    seen = seen or {}
    tracks = config["tracks"]

    matched = []
    for company_name, uid, token in COMPANIES:
        for position in fetch_company_positions(uid, token):
            location = position.get("location") or {}
            if not _location_is_relevant(location):
                continue

            title = position.get("name", "")
            department = position.get("department", "")
            for track in matching_tracks(f"{title} {department}", tracks):
                job_id = get_job_id(position.get("uid"), track)
                if job_id in seen:
                    continue

                link = position.get("url_comeet_hosted_page", "")
                description = fetch_job_description(link) or title
                location_name = location.get("name") or "N/A"
                job_dict = build_job_dict(title, company_name, location_name, description, link)
                matched.append((job_id, job_dict, track))
    return matched
