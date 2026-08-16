#!/usr/bin/env python3
"""One-off diagnostic - NOT part of the production pipeline.

Tests the updated SYSTEM_PROMPT's experience-gap weighting by scoring two
synthetic postings against the real resume:
  1. A recreation of the קבוצת יעל (Yael Group) BI Analyst case that
     triggered this change: requires 6+ years, resume shows ~1 year (6x
     gap) - should now score 5 or below.
  2. A hypothetical posting requiring 2-3 years - resume shows ~1 year
     (2x-3x gap) - should NOT be significantly capped, since the
     candidate considers this a realistic, competitive application.

Safe to delete once the scoring behavior is confirmed.
"""

import json
import os
import sys
from pathlib import Path

import anthropic

from score_job import score_job

RESUME_PATH = Path(__file__).resolve().parent.parent / "resumes" / "data_analyst_resume.local.txt"

LARGE_GAP_JOB = {
    "title": "BI Analyst",
    "company_name": "קבוצת יעל",
    "location": "Jerusalem, Israel",
    "description": (
        "We are looking for a BI Analyst with 6+ years of experience to "
        "join our data team. Responsibilities include building dashboards "
        "in Power BI and Tableau, writing complex SQL queries, and "
        "presenting insights to senior stakeholders. Requirements: 6+ "
        "years of experience in BI/data analysis, strong SQL skills, "
        "experience with Power BI and/or Tableau, excellent communication "
        "skills."
    ),
}

SMALL_GAP_JOB = {
    "title": "Data Analyst",
    "company_name": "Example Analytics Co",
    "location": "Tel Aviv, Israel",
    "description": (
        "We are looking for a Data Analyst with 2-3 years of experience "
        "to join our growing analytics team. Responsibilities include "
        "building dashboards in Power BI, writing SQL queries against our "
        "data warehouse, and collaborating with cross-functional teams to "
        "turn data into actionable insights. Requirements: 2-3 years of "
        "experience in data analysis, strong SQL skills, experience with "
        "Power BI or similar BI tools."
    ),
}


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable is not set.")

    resume_text = RESUME_PATH.read_text(encoding="utf-8")
    client = anthropic.Anthropic()

    print("=== Case 1: Large gap (6+ years required vs ~1 year actual, ~6x) ===")
    print("Expect: score capped at 5 or below, gap mentioned prominently.\n")
    result = score_job(LARGE_GAP_JOB, resume_text, client)
    print(json.dumps(result, indent=2))

    print("\n=== Case 2: Small gap (2-3 years required vs ~1 year actual, ~2-3x) ===")
    print("Expect: NOT significantly capped, judged mainly on skills fit.\n")
    result = score_job(SMALL_GAP_JOB, resume_text, client)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
