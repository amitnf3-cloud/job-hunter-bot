#!/usr/bin/env python3
"""Filter Telegram messages by track keywords and location, before spending
any Claude API calls on extraction or scoring.

Location filtering is deliberately permissive, but with a specific-city
keyword (Tel Aviv, Ramat Gan, Petah Tikva, ...) always taking priority over
an exclude: a message is excluded only if it mentions a
location_exclude_keywords term (e.g. Jerusalem, USA) and does NOT also
mention a specific target-city keyword. "remote"/"hybrid" are deliberately
NOT treated as override-strength signals here - they say nothing about
which city the role is hybrid/remote *to*, so a "Jerusalem, hybrid" posting
should still be excluded rather than let "hybrid" rescue it. They're
checked last, as a weaker "location is flexible" signal, only once a
specific exclude hasn't already ruled the message out. A message that
doesn't mention location at all is included - this filter's job is to cut
obvious noise (wrong job type, clearly foreign postings) cheaply, not to be
a precise location filter. Claude's scoring step already judges location
fit well on its own.
"""

FLEXIBLE_LOCATION_KEYWORDS = ["remote", "hybrid"]


def _contains_any(text, keywords):
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def matches_location(text, location_keywords, location_exclude_keywords):
    if _contains_any(text, location_keywords):
        return True
    if _contains_any(text, location_exclude_keywords):
        return False
    if _contains_any(text, FLEXIBLE_LOCATION_KEYWORDS):
        return True
    return True  # location unstated either way - don't exclude


def matching_tracks(text, tracks):
    """Return the track dicts (from config['tracks']) whose keywords appear
    in the message text. A message may match zero, one, or multiple tracks."""
    return [track for track in tracks if _contains_any(text, track.get("keywords", []))]


def filter_messages(messages, config):
    """Given an iterable of objects with a `.text` attribute (e.g. Telethon
    messages) and the loaded config, return a list of (message, track)
    pairs for messages passing both the location and track-keyword filters.
    A message matching multiple tracks produces one pair per matched track.
    """
    location_keywords = config["telegram"]["location_keywords"]
    location_exclude_keywords = config["telegram"]["location_exclude_keywords"]
    tracks = config["tracks"]

    matched = []
    for message in messages:
        if not message.text:
            continue
        if not matches_location(message.text, location_keywords, location_exclude_keywords):
            continue
        for track in matching_tracks(message.text, tracks):
            matched.append((message, track))
    return matched
