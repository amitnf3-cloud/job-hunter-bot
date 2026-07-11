#!/usr/bin/env python3
"""Fetch a job's real career-page URL and extract its visible text as the
job description, with a fallback to the Telegram message text when the
fetch fails, times out, or returns suspiciously little content (e.g. a
JS-rendered page with nothing meaningful in the raw HTML).
"""

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT_SECONDS = 10
MIN_DESCRIPTION_LENGTH = 200
USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"

# Workday career pages (*.myworkdayjobs.com) are JS-rendered SPAs - a plain
# GET returns an empty shell, with the real content loaded client-side from
# a JSON API. This is a best-effort, UNVERIFIED-AGAINST-A-LIVE-ENDPOINT
# rewrite based on Workday's documented CXS URL shape; if it's wrong or the
# API responds unexpectedly, it fails closed and falls through to the
# normal fetch (and ultimately the Telegram-text fallback) rather than
# raising.
WORKDAY_JOB_PATH_WITH_LOCALE_RE = re.compile(r"^/([a-z0-9\-]{2,10})/([^/]+)/job/(.+)$", re.IGNORECASE)
WORKDAY_JOB_PATH_RE = re.compile(r"^/([^/]+)/job/(.+)$", re.IGNORECASE)

# Telethon's `message.text` renders MessageEntityTextUrl entities as
# markdown link syntax "[visible text](url)" - regex-matching this is more
# robust than manually walking message.entities offsets, which are UTF-16
# code units and easy to get wrong once emoji or other non-BMP characters
# appear earlier in the message.
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\s\)]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s\)\]]+")

# Some ATS platforms (e.g. Comeet) leak unrendered template placeholders
# like "{{position.name}}" into the page's raw HTML text.
TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")


def get_message_url(message_text):
    """Extract the first real hyperlink from a message's rendered text, or
    None if there isn't one."""
    if not message_text:
        return None

    match = MARKDOWN_LINK_RE.search(message_text)
    if match:
        return match.group(1)

    match = BARE_URL_RE.search(message_text)
    if match:
        return match.group(0)

    return None


def extract_visible_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = TEMPLATE_PLACEHOLDER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def is_workday_url(url):
    return urlparse(url).netloc.lower().endswith("myworkdayjobs.com")


def workday_api_url(url):
    """Rewrite a Workday career-page URL into its underlying CXS JSON API
    URL, or return None if the path doesn't match the expected shape."""
    parsed = urlparse(url)

    match = WORKDAY_JOB_PATH_WITH_LOCALE_RE.match(parsed.path)
    if match:
        _locale, site, job_path = match.groups()
    else:
        match = WORKDAY_JOB_PATH_RE.match(parsed.path)
        if not match:
            return None
        site, job_path = match.groups()

    tenant = parsed.netloc.split(".")[0]
    return f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/job/{job_path}"


def fetch_workday_description(url, timeout):
    """Best-effort: fetch a Workday job's real description via its CXS
    JSON API instead of the JS-rendered HTML shell. Returns None (never
    raises) if the URL doesn't match, the request fails, or the response
    isn't the expected JSON shape - the caller falls through to the normal
    HTML fetch and ultimately the Telegram-text fallback."""
    api_url = workday_api_url(url)
    if not api_url:
        return None

    try:
        response = requests.get(
            api_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    job_posting_info = data.get("jobPostingInfo") or {}
    html_description = job_posting_info.get("jobDescription")
    if not html_description:
        return None

    return extract_visible_text(html_description)


def fetch_job_description(url, timeout=REQUEST_TIMEOUT_SECONDS, min_length=MIN_DESCRIPTION_LENGTH):
    """Fetch `url` and return its extracted visible text, or None if the
    fetch fails, times out, or the extracted text is too short to be a
    real job description."""
    if is_workday_url(url):
        workday_text = fetch_workday_description(url, timeout)
        if workday_text and len(workday_text) >= min_length:
            return workday_text
        # Fall through to the generic fetch below as a last resort.

    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return None

    text = extract_visible_text(response.text)
    if len(text) < min_length:
        return None
    return text


def get_job_description(message_text, timeout=REQUEST_TIMEOUT_SECONDS, min_length=MIN_DESCRIPTION_LENGTH):
    """Return the best available job description for a message: the
    fetched career-page text if a link exists and the fetch succeeds with
    enough content, otherwise the raw Telegram message text as a fallback.
    """
    url = get_message_url(message_text)
    if url:
        description = fetch_job_description(url, timeout=timeout, min_length=min_length)
        if description:
            return description, url

    return message_text, url
