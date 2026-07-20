#!/usr/bin/env python3
"""Score a single job posting against a resume using the Claude API.

Given a job's title/company/description and a resume's text, asks Claude to
rate the fit from 1-10 with a short reason. No search, no dedup, no email
yet - just the scoring piece, so it can be tested on its own with a sample
job before it's wired into the real pipeline.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()  # loads .env into the environment for local runs, if present

MODEL = "claude-opus-4-8"

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "Fit score from 1 (poor fit) to 10 (excellent fit)",
        },
        "reason": {
            "type": "string",
            "description": "One or two sentence explanation for the score",
        },
        "location": {
            "type": ["string", "null"],
            "description": (
                "The job's actual work location (city/area, and remote/hybrid "
                "if stated), extracted from the job posting text. Null if the "
                "posting doesn't state a location."
            ),
        },
        "company_name": {
            "type": ["string", "null"],
            "description": (
                "The hiring company's name, extracted from the job posting "
                "text. Null if it isn't stated."
            ),
        },
        "company_description": {
            "type": ["string", "null"],
            "description": (
                "A brief (one or two sentence) summary of the company, but "
                "ONLY if the job posting includes an actual 'About us' / "
                "company-description section. Null if no such section is "
                "present - do not guess or infer a company description from "
                "the company name alone."
            ),
        },
    },
    "required": ["score", "reason", "location", "company_name", "company_description"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = (
    "You score how well a job posting matches a candidate's resume, "
    "and extract a few structured details from the posting. "
    "Score from 1 (poor fit) to 10 (excellent fit), and give a short, "
    "specific reason. Base the score only on the resume and job "
    "description provided - do not assume unstated qualifications. "
    "Also extract: the job's actual work location (city/area, and "
    "remote/hybrid if stated) and the hiring company's name, both "
    "read directly from the job posting text (use null if not "
    "stated - do not guess). Also extract a brief one-or-two "
    "sentence company_description, but ONLY if the posting contains "
    "an actual 'About us' or company-description section - if there "
    "is no such section, return null rather than inferring one from "
    "the company name."
)


def build_job_summary(job: dict) -> str:
    return (
        f"Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company_name', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Description: {job.get('description', 'N/A')}"
    )


def score_job(job: dict, resume_text: str, client: anthropic.Anthropic) -> dict:
    """Return a dict with score/reason plus location, company_name, and
    company_description extracted from the job posting text, for how well
    the job fits the resume."""
    job_summary = build_job_summary(job)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"RESUME:\n{resume_text}\n\nJOB POSTING:\n{job_summary}",
            }
        ],
    )

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable is not set.")

    resume_path = Path(__file__).resolve().parent.parent / "resumes" / "data_analyst_resume.txt"
    resume_text = resume_path.read_text(encoding="utf-8")

    sample_job = {
        "title": "Business Intelligence Analyst",
        "company_name": "Example Corp",
        "location": "Tel Aviv, Israel",
        "description": (
            "We're looking for a BI Analyst to build dashboards in Power BI and "
            "Tableau, write complex SQL queries, and work with cross-functional "
            "teams to turn data into actionable insights. Splunk experience a plus."
        ),
    }

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    result = score_job(sample_job, resume_text, client)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
