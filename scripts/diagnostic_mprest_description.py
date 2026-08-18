#!/usr/bin/env python3
"""One-off diagnostic: compare what the generic Telegram-path extractor
(fetch_job_description.py, no Comeet special-case) actually returns for the
mPrest "Junior Project Manager" posting versus the fixed Comeet-specific
extractor (fetch_comeet_jobs.py). Prints both raw texts in full so we can see
exactly what was sent to Claude for scoring."""

from fetch_job_description import fetch_job_description
from fetch_comeet_jobs import fetch_position_description

URL = "https://www.comeet.com/jobs/mprest/38.005/junior-project-manager/16.07F"

print("=" * 80)
print("GENERIC extractor (fetch_job_description.py) - this is the Telegram code path")
print("=" * 80)
generic_text = fetch_job_description(URL)
if generic_text is None:
    print("-> Returned None (fetch failed or below min length)")
else:
    print(f"-> Length: {len(generic_text)} chars")
    print(generic_text)

print()
print("=" * 80)
print("FIXED Comeet-specific extractor (fetch_comeet_jobs.py) - this is the Comeet-native code path")
print("=" * 80)
fixed_text = fetch_position_description(URL)
if fixed_text is None:
    print("-> Returned None")
else:
    print(f"-> Length: {len(fixed_text)} chars")
    print(fixed_text)
