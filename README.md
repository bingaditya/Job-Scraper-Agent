# AI Job Hunter Agent

A Python-based AI job search agent that:

- pulls jobs from public sources,
- supports search portals such as LinkedIn, Built In, and Himalayas,
- ranks them against your profile,
- generates resume-tailoring suggestions,
- sends Telegram alerts for new matches,
- publishes JSON output for a static dashboard.

## What is included

- `main_agent.py`: CLI entrypoint.
- `job_hunter/`: source integrations, ranking, resume optimization, storage, notifications.
- `config/profile.json`: editable candidate profile and search preferences.
- `database/`: generated run artifacts.
- `dashboard/`: static dashboard that reads generated JSON.
- `.github/workflows/ai-agent.yml`: scheduled automation.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Edit `config/profile.json` with your skills, titles, locations, and resume path.
4. Optional: set Telegram and Ollama variables.

```powershell
$env:TELEGRAM_BOT_TOKEN="your-token"
$env:TELEGRAM_CHAT_ID="your-chat-id"
$env:OLLAMA_MODEL="llama3.1"
```

5. Run the agent:

```powershell
python main_agent.py
```

6. Start the interactive dashboard server:

```powershell
python dashboard_server.py
```

Open `http://127.0.0.1:8000`.

The run writes:

- `database/jobs.json`
- `database/summary.json`
- `database/resume_suggestions.json`
- `database/state.json`
- `database/resume_application_state.json`
- `dashboard/jobs.json`
- `dashboard/summary.json`
- `dashboard/resume_suggestions.json`
- `dashboard/resume_application_state.json`

## Configuration

`config/profile.json` controls:

- candidate skills and experience,
- preferred titles and locations,
- search queries used on portal-based sources,
- keyword filtering used for ranking and final shortlist,
- optional strict location filtering when you want only specific regions,
- enabled sources,
- minimum score and result limit,
- Telegram notifications,
- optional local Ollama resume tailoring.

## Notes

- The agent now includes `LinkedIn`, `Built In`, and `Himalayas` scrapers in addition to `Arbeitnow` and `RemoteOK`.
- `Indeed` and `Naukri` are included as guarded sources. They currently return explicit errors when the site presents bot protection or client-side-only job data to this environment.
- The dashboard `Tailor Resume` button requires `python dashboard_server.py`; a plain static file server cannot write `assets/resume.md`.
- Resume tailoring updates `assets/resume.md`, creates a backup under `assets/resume.backups/`, and stores a separate `resume_fit_score`. The original job match score stays unchanged.
- If every source fails during a run, the agent exits without overwriting existing results.
