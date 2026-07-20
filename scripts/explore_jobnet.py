#!/usr/bin/env python3
"""One-off exploration script - NOT part of the production pipeline.

Fetches JobNet's robots.txt and search page(s) to figure out the real
form/URL structure (parameter names, category checkbox values, region
codes) before writing any real scraping code. Prints raw findings for
manual review. Safe to delete once the real jobnet.py source module
exists and the structure is understood.
"""

import sys

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

CANDIDATE_SEARCH_URLS = [
    "https://www.jobnet.co.il/robots.txt",
    "https://www.jobnet.co.il/PositionResults.aspx",
    "https://www.jobnet.co.il/SearchIndex.aspx",
    "https://www.jobnet.co.il/%D7%97%D7%99%D7%A4%D7%95%D7%A9_%D7%A2%D7%91%D7%95%D7%93%D7%94_%D7%9E%D7%93%D7%A8%D7%99%D7%9A",
    "https://m.jobnet.co.il/Search/SearchResults?Region=7",
]


def describe_forms(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    print(f"  {len(forms)} <form> tag(s) found")
    for form in forms:
        print(f"    method={form.get('method')} action={form.get('action')}")

    inputs = soup.find_all("input")
    print(f"  {len(inputs)} <input> element(s) found - checkbox/text/hidden with name+value:")
    for inp in inputs:
        name = inp.get("name")
        if not name:
            continue
        print(f"    type={inp.get('type')!r} name={name!r} value={inp.get('value')!r}")

    selects = soup.find_all("select")
    print(f"  {len(selects)} <select> element(s) found:")
    for sel in selects:
        name = sel.get("name")
        options = [(opt.get("value"), opt.get_text(strip=True)) for opt in sel.find_all("option")]
        print(f"    name={name!r} options={options[:20]}")

    # look for anything mentioning known category labels, to find their checkbox/value
    for label_text in ["Data Analyst", "DWH", "BI", "Back End", "Project Manager", "פרויקטים"]:
        hits = soup.find_all(string=lambda s: s and label_text.lower() in s.lower())
        if hits:
            print(f"  Found label text matching {label_text!r}: {len(hits)} occurrence(s)")
            for h in hits[:3]:
                parent = h.parent
                print(f"    context: <{parent.name}> attrs={parent.attrs} text={h.strip()[:80]!r}")


def main():
    for url in CANDIDATE_SEARCH_URLS:
        print(f"\n{'=' * 80}\nFetching: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"  ERROR: {e}")
            continue

        print(f"  status={resp.status_code} length={len(resp.text)} final_url={resp.url}")

        if url.endswith("robots.txt"):
            print("  --- robots.txt content ---")
            print(resp.text)
            continue

        if resp.status_code != 200:
            print(f"  --- first 500 chars of response body ---\n{resp.text[:500]}")
            continue

        describe_forms(resp.text, url)

        # dump a chunk of raw HTML too, in case structure isn't in <form>/<input>
        # (e.g. client-side JS building the search, or data in a script tag/JSON blob)
        print("  --- first 2000 chars of raw HTML ---")
        print(resp.text[:2000])


if __name__ == "__main__":
    main()
