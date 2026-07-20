#!/usr/bin/env python3
"""One-off exploration script - NOT part of the production pipeline.

Round 3: quick pagination check (does subprofid=1561 page 2 differ from
page 1? does a bigger category like 683 show more than ~10 results and
any visible "next page" / result-count text?) and a quick glance for a
free-text search parameter. Not spending much time here - just confirming
before writing the real scraper.

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


def job_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=re.compile(r"positionid=\d+"))
    ids = []
    for a in links:
        m = re.search(r"positionid=(\d+)", a["href"])
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids, soup


def check(url, label):
    print(f"\n{'=' * 80}\nFetching: {url}  ({label})")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={resp.status_code} length={len(resp.text)}")
    ids, soup = job_links(resp.text)
    print(f"  {len(ids)} unique positionid(s): {ids}")

    # look for any visible result-count or pagination text/elements
    text = soup.get_text(" ", strip=True)
    for pattern in [r"\d+\s*תוצאות", r"\d+\s*משרות", r"results", r"עמוד \d+"]:
        hits = re.findall(pattern, text)
        if hits:
            print(f"  text matching {pattern!r}: {hits[:5]}")

    pagers = soup.find_all(["a", "li"], class_=re.compile("pag", re.IGNORECASE))
    print(f"  {len(pagers)} element(s) with a 'pag*' class")
    for p in pagers[:10]:
        print(f"    <{p.name} class={p.get('class')}> text={p.get_text(strip=True)!r}")

    return ids


def main():
    ids_p1 = check("https://www.jobnet.co.il/jobs?subprofid=1561", "Data Analyst, page 1")
    ids_p2 = check("https://www.jobnet.co.il/jobs?subprofid=1561&p=2", "Data Analyst, ?p=2")
    print(f"\n  page1 vs page2 identical? {ids_p1 == ids_p2}")

    check("https://www.jobnet.co.il/jobs?subprofid=683", "DWH/BO/BI (bigger category)")

    # quick glance for a free-text param - not spending much time if absent
    check("https://www.jobnet.co.il/jobs?FreeText=Project+Manager", "guess: FreeText param")


if __name__ == "__main__":
    main()
