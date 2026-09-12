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
