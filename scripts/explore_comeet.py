#!/usr/bin/env python3
"""One-off exploration - NOT part of the production pipeline.

Comeet's public Careers API (https://www.comeet.co/careers-api/2.0) needs
a per-company `uid` + `token`. The uid is visible in each company's public
careers page URL (comeet.com/jobs/{slug}/{uid}/...), but the token is not
- per Comeet's own docs, it's bootstrapped from a `COMPANY_DATA` JS
variable embedded in that page's HTML. This script fetches each
candidate company's careers page, extracts COMPANY_DATA, pulls the token,
and tries the real positions API - to confirm the real shape of both
before writing the production module.

Safe to delete once the Comeet integration approach is confirmed.
"""

import json
import re

import requests

USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"
REQUEST_TIMEOUT_SECONDS = 10

# (display name, careers-page slug, uid found in that page's URL)
CANDIDATES = [
    ("Lasso Security", "lassosecurity", "F9.008"),
    ("mPrest", "mprest", "38.005"),
    ("Natural Intelligence", "naturalint", "71.001"),
    ("mend.io", "mend", "83.000"),
    ("Elementor", "Elementor", "A3.00F"),
    ("Landa", "landacorp", "A4.000"),
    ("Skai", "kenshoo", "22.00A"),
    ("BioCatch", "biocatch", "03.00E"),
    ("CodeValue", "codevalue", "81.009"),
    ("Pentera", "pentera", "C5.00D"),
    ("HiBob", "hibob", "12.00A"),
    ("Abra", "abra", "12.003"),
]

COMPANY_DATA_RE = re.compile(r"COMPANY_DATA\s*=\s*(\{.*?\});", re.DOTALL)


def fetch_careers_page(slug, uid):
    url = f"https://www.comeet.com/jobs/{slug}/{uid}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as e:
        return None, str(e)
    return response.text, None


def extract_company_data(html):
    match = COMPANY_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def try_positions_api(uid, token):
    url = f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions"
    try:
        response = requests.get(url, params={"token": token}, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as e:
        return None, str(e)
    return response, None


JS_STATE_VAR_NAMES = [
    "POSITION_DATA",
    "JOB_DATA",
    "__INITIAL_STATE__",
    "__NEXT_DATA__",
    "__NUXT__",
    "__APOLLO_STATE__",
    "PRELOADED_STATE",
    "initialState",
]


def inspect_position_page_for_description(url):
    """The Careers API has no description field anywhere, and the
    hosted position page's VISIBLE text turned out to be just site
    chrome/an error shell (confirmed live via diagnostic_comeet_check.py
    - Abra's fetched "description" was identical boilerplate across all
    9 matched jobs). Check whether the real description text is embedded
    server-side as JSON inside a <script> tag instead - our generic
    extractor strips <script> tags, so it would have missed this even if
    present. Prints any embedded JS state variable found, and searches
    raw HTML for the word "description" for a broader net."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"    FAILED to fetch position page: {e}")
        return
    html = response.text
    print(f"    Position page length: {len(html)}")

    for var_name in JS_STATE_VAR_NAMES:
        idx = html.find(var_name)
        if idx != -1:
            print(f"    Found JS state var '{var_name}' at offset {idx}")
            print(f"    Context: ...{html[idx:idx+400]}...")

    # Broader net: every occurrence of "description" (case-insensitive),
    # in case the real content is under some other variable name entirely.
    lowered = html.lower()
    found_at = []
    start = 0
    while True:
        idx = lowered.find("description", start)
        if idx == -1 or len(found_at) >= 5:
            break
        found_at.append(idx)
        start = idx + 1
    print(f"    'description' appears {len(found_at)}+ time(s) in raw HTML, first few contexts:")
    for idx in found_at:
        print(f"      ...{html[max(0, idx-80):idx+200]}...")


def try_single_position_api(uid, token, position_uid):
    """The positions LIST endpoint has no description field - check
    whether a per-position detail endpoint returns the actual job
    description text, which score_job() needs for real signal (a bare
    title produces the same weak/generic scoring we already saw on
    thin JobNet postings)."""
    url = f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions/{position_uid}"
    try:
        response = requests.get(url, params={"token": token}, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as e:
        return None, str(e)
    return response, None


def main():
    for name, slug, uid in CANDIDATES:
        print(f"\n=== {name} (slug={slug}, uid={uid}) ===")
        html, err = fetch_careers_page(slug, uid)
        if err:
            print(f"  FAILED to fetch careers page: {err}")
            continue

        company_data = extract_company_data(html)
        if not company_data:
            print(f"  COMPANY_DATA not found in HTML (page length={len(html)})")
            # show a snippet to help debug the actual embedding format
            idx = html.find("COMPANY_DATA")
            if idx != -1:
                print(f"  Context: ...{html[max(0, idx-50):idx+300]}...")
            continue

        print(f"  COMPANY_DATA keys: {list(company_data.keys())}")
        token = company_data.get("token") or company_data.get("company_token") or company_data.get("Token")
        real_uid = company_data.get("uid") or company_data.get("company_uid") or uid
        print(f"  Extracted token={token!r}  uid={real_uid!r}")

        if not token:
            print("  No token found in COMPANY_DATA - dumping full object for inspection:")
            print(f"  {json.dumps(company_data)[:1000]}")
            continue

        response, err = try_positions_api(real_uid, token)
        if err:
            print(f"  Positions API request FAILED: {err}")
            continue
        print(f"  Positions API -> HTTP {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                positions = data if isinstance(data, list) else data.get("positions", data)
                count = len(positions) if isinstance(positions, list) else "unknown shape"
                print(f"  Position count: {count}")
                if isinstance(positions, list) and positions:
                    print(f"  Sample position keys: {list(positions[0].keys())}")
                    print(f"  Sample position: {json.dumps(positions[0])[:500]}")

                    hosted_page_url = positions[0].get("url_comeet_hosted_page")
                    if hosted_page_url:
                        print(f"  Inspecting hosted position page for embedded description data: {hosted_page_url}")
                        inspect_position_page_for_description(hosted_page_url)

                    position_uid = positions[0].get("uid")
                    if position_uid:
                        detail_response, detail_err = try_single_position_api(real_uid, token, position_uid)
                        if detail_err:
                            print(f"  Single-position detail API FAILED: {detail_err}")
                        else:
                            print(f"  Single-position detail API -> HTTP {detail_response.status_code}")
                            if detail_response.status_code == 200:
                                try:
                                    detail_data = detail_response.json()
                                    print(f"  Detail keys: {list(detail_data.keys())}")
                                    has_desc = "description" in detail_data
                                    print(f"  Has 'description' field: {has_desc}")
                                    if has_desc:
                                        print(f"  Description preview: {str(detail_data['description'])[:300]}")
                                except (ValueError, AttributeError) as e:
                                    print(f"  Could not parse detail response: {e}")
                                    print(f"  Raw snippet: {detail_response.text[:300]}")
                            else:
                                print(f"  Detail response snippet: {detail_response.text[:300]}")
            except (ValueError, AttributeError) as e:
                print(f"  Could not parse response as JSON: {e}")
                print(f"  Raw response snippet: {response.text[:300]}")
        else:
            print(f"  Response snippet: {response.text[:300]}")


if __name__ == "__main__":
    main()
