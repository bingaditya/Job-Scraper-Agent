# Resume API Setup (Supabase + Groq)

One-time setup for the multi-user resume upload/tailoring feature. This is separate from the
existing scraper pipeline — nothing here affects `main_agent.py` or `dashboard_server.py`.

## 1. Create a Supabase project

1. Sign up / log in at [supabase.com](https://supabase.com) and create a new project (free tier).
2. In the SQL Editor, run the contents of [`migrations/001_resume_versions.sql`](../migrations/001_resume_versions.sql).
   This creates the `resume_versions` table, its RLS policies, and a private `resumes` storage bucket.
3. Go to **Project Settings → API Keys** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **publishable** key (`sb_publishable_...`) → `SUPABASE_PUBLISHABLE_KEY` (safe for frontend use)
   - **secret** key (`sb_secret_...`) → `SUPABASE_SECRET_KEY` (server-side only, never in frontend code)

   Newer projects use these publishable/secret keys instead of the older anon/service_role keys;
   if your project still shows anon/service_role, those work the same way in the same env vars.
4. No JWT secret to copy — this project verifies user session tokens via the project's public
   JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`). This requires your project to
   be on Supabase's newer asymmetric **JWT Signing Keys** system (check **Project Settings → JWT
   Keys** — if it shows "JWT Signing Keys" as the active tab with an ECC/RSA key, you're set). If
   your project is still on the **Legacy JWT Secret** system, this JWKS-based verification will
   not work — migrate to JWT Signing Keys first (Supabase's dashboard has a one-click migration).
5. By default, Supabase requires email confirmation on signup. For local testing you can disable
   this under **Authentication → Providers → Email → Confirm email**, or check your inbox for the
   confirmation link after signing up.

## 2. Get a Groq API key

Already done if you have a `console.groq.com` API key. Note: **Groq** (fast open-source-model
hosting) is not the same as xAI's **Grok** — this project uses Groq.

## 3. Set environment variables (local development)

PowerShell:

```powershell
$env:SUPABASE_URL="https://<your-project>.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY="sb_publishable_..."
$env:SUPABASE_SECRET_KEY="sb_secret_..."
$env:GROQ_API_KEY="<your-groq-key>"
$env:ALLOWED_ORIGINS="http://127.0.0.1:5500,http://127.0.0.1:8001"
```

## 4. Run the API locally

```powershell
uvicorn job_hunter.api.app:app --host 127.0.0.1 --port 8001 --reload
```

## 5. Open the resume page

Serve `dashboard/` with any static file server (or open `dashboard/login.html` directly) and
visit it. If the API isn't at `http://127.0.0.1:8001`, append `?api=http://your-api-host` once —
it's remembered in `localStorage` after that.

## 6. Verify (M1 round trip)

1. Sign up with an email/password, confirm the email if required, log in.
2. Upload a `.docx` resume — it should appear in the version list as `v1 (current)`.
3. Click Download — the file should be byte-identical to what you uploaded.

## Render deployment (when ready)

Add the same environment variables to the Render service running this API, and set
`ALLOWED_ORIGINS` to the actual origin(s) serving `dashboard/login.html` in production
(avoid leaving it as `*` for this authenticated surface).

## 7. Monitoring (Sentry + Better Stack)

Both Render services (`job-scraper-agent-api` and `job-scraper-resume-api`) now report
unhandled exceptions to Sentry if `SENTRY_DSN` is set (no-op otherwise, and every existing test
already runs with it unset). Errors and uptime are two separate free tools — set up both:

### Sentry (error tracking)

1. Sign up free at [sentry.io](https://sentry.io) and create a project — choose **Python** as the
   platform (works for both services; FastAPI is auto-detected for the resume API, the
   `dashboard_server.py` one reports via manual `capture_exception` calls).
2. Copy the **DSN** shown on the project's setup page (looks like
   `https://<key>@<org>.ingest.sentry.io/<project>`).
3. Set `SENTRY_DSN` to that value:
   - Locally: `$env:SENTRY_DSN="https://..."` before running either server.
   - On Render: **Dashboard → each service → Environment → Add Environment Variable** →
     `SENTRY_DSN` (already declared in `render.yaml` with `sync: false`, so Render will prompt
     for the value instead of expecting it committed).
4. Trigger a real error (e.g. hit `/api/tailor-resume` with a bad `job_id` — or temporarily raise
   an exception) and confirm it shows up in the Sentry project's Issues tab.

### Better Stack (uptime monitoring)

1. Sign up free at [betterstack.com](https://betterstack.com) → **Uptime**.
2. Add a monitor for each service's health endpoint (both are under `/api/health` — the resume
   API's router has an `/api` prefix too, not `/health` on its own):
   - `https://job-scraper-agent.onrender.com/api/health` — note the exact hostname has no `-api`
     suffix (see `dashboard/api_config.json`); `job-scraper-agent-api.onrender.com` is NOT a live
     host. Also, this service only implements `GET`, not `HEAD`, on this path — make sure the
     monitor is configured to use GET or it will falsely report down.
   - `https://job-scraper-resume-api.onrender.com/api/health`
3. Set the check interval (free tier supports down to 3 minutes) and add your email/phone under
   **On-call** for alerts.
4. Note: Render free-tier services sleep after inactivity, so expect an occasional false "down"
   alert on cold start (~30-60s) — this is expected, not a real outage (see `PROJECT_CONTEXT.md`
   Section 43's "Known operational notes").
