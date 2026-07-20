#!/usr/bin/env python3
"""One-off exploration script - NOT part of the production pipeline.

Round 2: now that we know /AllCategories lists subprofession categories as
plain <a href="/jobs?subprofid=NNN"> links, and /jobs?subprofid=NNN is a
simple GET-based results page (no VIEWSTATE/POST needed), this:
  1. Dumps the FULL category list (id -> label) from /AllCategories, so we
     can find every relevant Data Analyst/BI and Project Manager/Operations
     category id, not just the ones a narrow keyword search happened to hit.
  2. Fetches /jobs?subprofid=1561 (Data Analyst) directly to inspect the
     real result listing structure (job cards: title/company/location/link)
     and pagination, and to look for a region/location filter parameter.

Safe to delete once the real jobnet.py source module exists.
"""

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def dump_all_categories():
    url = "https://www.jobnet.co.il/AllCategories"
    print(f"\n{'=' * 80}\nFetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={resp.status_code} length={len(resp.text)}")

    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", href=re.compile(r"/jobs\?subprofid=\d+"))
    print(f"  {len(links)} subprofid link(s) found:")
    for a in links:
        subprofid = re.search(r"subprofid=(\d+)", a["href"]).group(1)
        print(f"    subprofid={subprofid}\ttext={a.get_text(strip=True)!r}")

    # also check for a parent "professionid" grouping and any region links
    prof_links = soup.find_all("a", href=re.compile(r"professionid=\d+"))
    print(f"  {len(prof_links)} professionid link(s) found:")
    for a in prof_links[:30]:
        print(f"    href={a['href']!r} text={a.get_text(strip=True)!r}")

    region_links = soup.find_all("a", href=re.compile(r"region", re.IGNORECASE))
    print(f"  {len(region_links)} region-related link(s) found:")
    for a in region_links[:30]:
        print(f"    href={a['href']!r} text={a.get_text(strip=True)!r}")


def inspect_results_page(subprofid, label):
    url = f"https://www.jobnet.co.il/jobs?subprofid={subprofid}"
    print(f"\n{'=' * 80}\nFetching: {url}  ({label})")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={resp.status_code} length={len(resp.text)} final_url={resp.url}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # job posting links tend to follow a pattern like /jobs?positionid=NNN
    job_links = soup.find_all("a", href=re.compile(r"positionid=\d+"))
    print(f"  {len(job_links)} job posting link(s) found (first 15):")
    seen = set()
    for a in job_links:
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)
        if len(seen) > 15:
            break
        print(f"    href={href!r} text={a.get_text(strip=True)[:80]!r}")

    # look for pagination controls
    pagination = soup.find_all("a", href=re.compile(r"[?&]p=\d+"))
    print(f"  {len(pagination)} pagination link(s) found (first 10):")
    for a in pagination[:10]:
        print(f"    href={a['href']!r} text={a.get_text(strip=True)!r}")

    # look for any region/location filter links on this results page
    region_links = soup.find_all("a", href=re.compile(r"region", re.IGNORECASE))
    print(f"  {len(region_links)} region-related link(s) on results page:")
    for a in region_links[:20]:
        print(f"    href={a['href']!r} text={a.get_text(strip=True)!r}")

    # dump a job card's surrounding structure for the first couple results
    print("  --- first 2 job link(s) with surrounding HTML context ---")
    for a in job_links[:2]:
        block = a
        for _ in range(3):
            if block.parent:
                block = block.parent
        print(f"    context html:\n{str(block)[:800]}\n")


def main():
    dump_all_categories()
    inspect_results_page(1561, "Data Analyst")


if __name__ == "__main__":
    main()
