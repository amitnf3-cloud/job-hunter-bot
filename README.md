# Job Hunter Bot

A personal bot that searches for jobs in Tel Aviv (Data Analyst/BI and Project
Manager/Operations tracks), scores them against your resumes using the Claude
API, and emails a daily digest of jobs scoring 6+ - no duplicates.

## Project structure (so far)

```
job-hunter-bot/
├── config/
│   └── config.yaml          # search settings, tracks, scoring, email config
├── resumes/
│   ├── data_analyst_resume.txt      # paste your Data Analyst/BI resume here
│   └── project_manager_resume.txt   # paste your PM/Operations resume here
├── data/
│   └── seen_jobs.json        # record of already-sent jobs (starts empty)
├── .env.example               # template for local secrets
└── .gitignore
```

## Next steps (building incrementally)

1. ~~Folder structure + config~~ (this step)
2. Paste in your two resumes
3. Script to query SerpApi Google Jobs and print raw results
4. Add Claude-based scoring
5. Add duplicate tracking against `data/seen_jobs.json`
6. Add Gmail SMTP digest email
7. Wire it all together into one script
8. Add a GitHub Actions workflow to run it every 24 hours

## Secrets

Copy `.env.example` to `.env` and fill in your API keys/app password for local
testing. In GitHub Actions, the same names will be set as repository secrets
instead (nothing gets committed).
