# Job Hunter Bot

A personal bot that scans a Telegram job-postings group for Data Analyst/BI
and Project Manager/Operations roles in Israel, scores them against your
resumes using the Claude API, and emails a daily digest of jobs scoring 6+ -
no duplicates.

(Originally used SerpApi's Google Jobs API, but Google Jobs had no usable
coverage for Israel - see git history for that path if curious.)

## Project structure

```
job-hunter-bot/
├── config/
│   └── config.yaml                    # tracks, keywords, scoring, email, Telegram settings
├── resumes/
│   ├── data_analyst_resume.txt        # your Data Analyst/BI resume
│   └── project_manager_resume.txt     # your PM/Operations resume
├── data/
│   └── seen_jobs.json                 # record of already-seen jobs (job_id -> date)
├── scripts/
│   ├── generate_telegram_session.py   # ONE-TIME LOCAL SETUP - generates a Telethon session string
│   ├── fetch_telegram_messages.py     # connects via Telethon, fetches recent messages
│   ├── filter_messages.py             # track/location keyword filtering
│   ├── fetch_job_description.py       # fetches the real career-page URL + extracts text (Workday-aware)
│   ├── score_job.py                   # Claude API scoring (1-10 + reason)
│   ├── seen_jobs.py                   # duplicate tracking, 60-day pruning
│   ├── send_email.py                  # HTML digest builder + Gmail SMTP sender
│   ├── run_daily_pipeline.py          # the full daily pipeline (entry point)
│   └── test_filter_on_real_messages.py, test_fetch_job_description.py
│                                       # read-only diagnostics for tuning filters/fetch against real data
├── .github/workflows/
│   └── daily-job-search.yml           # runs the pipeline every 24 hours
├── .env.example                       # template for local secrets
└── .gitignore
```

## How it works

1. `run_daily_pipeline.py` connects to Telegram (via Telethon, logged in as
   your account - see `generate_telegram_session.py`) and fetches messages
   from the configured group within the last `telegram.hours_lookback` hours.
2. Each message is filtered by track keywords and location (`filter_messages.py`).
3. For each match, the real career-page link is extracted and fetched for
   the full job description, with a Workday-specific path and a fallback to
   the raw Telegram text if the fetch fails or returns too little content
   (`fetch_job_description.py`).
4. Each job is scored 1-10 against the matching resume via Claude
   (`score_job.py`), skipping anything already in `data/seen_jobs.json`.
5. An HTML digest of jobs scoring 6+ is emailed via Gmail SMTP
   (`send_email.py`), and `data/seen_jobs.json` is updated and committed
   back by the GitHub Actions workflow.

## Secrets

Copy `.env.example` to `.env` and fill in your API keys/app password/Telegram
credentials for local testing. In GitHub Actions, the same names are set as
repository secrets instead (nothing gets committed).
