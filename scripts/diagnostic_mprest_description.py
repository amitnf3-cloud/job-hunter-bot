#!/usr/bin/env python3
"""One-off diagnostic: confirm fetch_job_description.py's new Comeet
special-case (mirroring the existing Workday special-case) now returns the
real posting text for the mPrest "Junior Project Manager" job - the same
job that previously scored 5/10 against boilerplate when sourced via a
Telegram-shared link - and that scoring that real text against the resume
produces a substantive score/reason instead of the boilerplate-based one."""

import os
from pathlib import Path

import anthropic

from fetch_job_description import fetch_job_description, is_comeet_url
from fetch_comeet_jobs import fetch_position_description
from score_job import score_job

URL = "https://www.comeet.com/jobs/mprest/38.005/junior-project-manager/16.07F"

print(f"is_comeet_url(URL) = {is_comeet_url(URL)}")
print()

print("=" * 80)
print("fetch_job_description() - the Telegram code path, AFTER the Comeet fix")
print("=" * 80)
telegram_path_text = fetch_job_description(URL)
if telegram_path_text is None:
    print("-> Returned None (fetch failed or below min length)")
else:
    print(f"-> Length: {len(telegram_path_text)} chars")
    print(telegram_path_text)

print()
print("=" * 80)
print("fetch_position_description() - the Comeet-native code path (unchanged, for comparison)")
print("=" * 80)
native_path_text = fetch_position_description(URL)
if native_path_text is None:
    print("-> Returned None")
else:
    print(f"-> Length: {len(native_path_text)} chars")
    print(native_path_text)

print()
if telegram_path_text and "Spark Hire" not in telegram_path_text and "no open positions" not in telegram_path_text:
    print("PASS: Telegram-path text looks like the real posting, not boilerplate.")
else:
    print("FAIL: Telegram-path text is missing or still looks like boilerplate.")

print()
print("=" * 80)
print("Scoring the Telegram-path text against the project_manager resume")
print("=" * 80)
if telegram_path_text:
    resume_path = Path(__file__).resolve().parent.parent / "resumes" / "project_manager_resume.local.txt"
    resume_text = resume_path.read_text(encoding="utf-8")
    job = {
        "title": "Junior Project Manager",
        "company_name": "mPrest",
        "location": "Petah Tikva, Israel",
        "description": telegram_path_text,
    }
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    result = score_job(job, resume_text, client)
    print(f"Score: {result['score']}/10")
    print(f"Reason: {result['reason']}")
else:
    print("-> Skipped: no Telegram-path text to score.")
