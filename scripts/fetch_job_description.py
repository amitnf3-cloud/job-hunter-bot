#!/usr/bin/env python3
"""Fetch a job's real career-page URL and extract its visible text as the
job description, with a fallback to the Telegram message text when the
fetch fails, times out, or returns suspiciously little content (e.g. a
JS-rendered page with nothing meaningful in the raw HTML).
"""

import re

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT_SECONDS = 10
MIN_DESCRIPTION_LENGTH = 200
USER_AGENT = "Mozilla/5.0 (compatible; JobHunterBot/1.0)"

# Telethon's `message.text` renders MessageEntityTextUrl entities as
# markdown link syntax "[visible text](url)" - regex-matching this is more
# robust than manually walking message.entities offsets, which are UTF-16
# code units and easy to get wrong once emoji or other non-BMP characters
# appear earlier in the message.
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\s\)]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s\)\]]+")


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
    return soup.get_text(separator=" ", strip=True)


def fetch_job_description(url, timeout=REQUEST_TIMEOUT_SECONDS, min_length=MIN_DESCRIPTION_LENGTH):
    """Fetch `url` and return its extracted visible text, or None if the
    fetch fails, times out, or the extracted text is too short to be a
    real job description."""
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
