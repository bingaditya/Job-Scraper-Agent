# PROJECT CONTEXT

> **Purpose:** Persistent source of truth for the AI Agent software project.
>
> **Rule:** Claude Code must read this file before substantial work and update it after every significant decision or implementation milestone.

---

## 1. Project Overview

**Project Name:** AI Job Hunter Agent (repo: `Job-Scraper-Agent`)

**Project Type:** Deterministic scraping/ranking pipeline with an optional local-LLM-assisted resume-tailoring step (not an autonomous multi-step agent — see Section 10 for feasibility framing).

**Project Status:** Existing single-user pipeline being extended into a hosted multi-user service. PII incident resolved (see ISSUE-001). Multi-tenant feature (login + per-user DOCX resume storage + AI tailoring) approved and in active implementation.

**Current SDLC Phase:** Phase 8 — Development (multi-tenant feature, milestone M1 in progress). Security Review (Phase 11) for the original single-user surface is unblocked (ISSUE-001 resolved) but not yet formally closed out.

**Current SDLC Gate:** Gate 8 — Development

**Owner:** Aditya Raj (GitHub: `bingaditya`)

**Last Updated:** 2026-09-11

---

## 2. Product Vision

### Problem Statement

Manually searching multiple job boards, judging fit against one's own skills, and rewriting a resume per application is slow and repetitive.

### Proposed Solution

A scheduled Python job that scrapes/pulls listings from several public job sources, scores each against a single candidate profile using transparent rules, deduplicates against previously-seen jobs, sends a Telegram alert for new qualifying matches, and (optionally) drafts resume-tailoring suggestions — publishing everything to a small dashboard.

### Product Vision

A free-to-run, self-hosted "job radar" a candidate points at their own profile and lets run unattended, with an optional interactive mode for one-click resume tailoring.

### Primary Objective

Surface new, well-matched job postings early and reduce resume-tailoring effort, at near-zero infrastructure cost.

### Expected Business Outcome

Not commercial — personal productivity tool being open-sourced for others to fork and run against their own profile.

---

## 3. Target Users

| Persona | Description | Goals | Permissions |
|---|---|---|---|
| Candidate (primary) | Owns `config/profile.json` and `assets/resume.md`; the only real "user" of any given deployment | Get notified of new matching jobs; get resume-tailoring help | Full — edits own config/resume locally |
| Forker / self-hoster (post public-release) | A stranger who forks the repo to run it against *their* profile | Stand up their own instance without touching anyone else's data | Full over their own fork/deployment only |
| GitHub Actions (scheduler) | Automated identity, not a person | Run the pipeline every 6h, publish artifacts | Repo write (via `GITHUB_TOKEN`), no external system access beyond scraping targets + Telegram |

---

## 4. Requirements

### 4.1 Functional Requirements

| ID | Requirement | Priority | Status | Notes |
|---|---|---|---|---|
| FR-001 | Fetch listings from configurable sources (Arbeitnow, RemoteOK, LinkedIn, Built In, Himalayas; Indeed/Naukri best-effort) | Must Have | Done | `job_hunter/sources/` |
| FR-002 | Deduplicate listings by normalized URL / fingerprint | Must Have | Done | `agent.py:_deduplicate` |
| FR-003 | Score listings 0–100 against candidate profile, filter by `min_score`, cap at `top_n` | Must Have | Done | `ranking.py` |
| FR-004 | Persist "seen" job fingerprints to avoid repeat notifications | Must Have | Done | `storage.py`, `database/state.json` |
| FR-005 | Send Telegram alert per new qualifying match | Should Have | Done, opt-in | `notifications.py` |
| FR-006 | Generate resume-tailoring suggestions (rule-based, or local Ollama) for top-N matches | Should Have | Done | `resume_optimizer.py` |
| FR-007 | Publish run output as JSON to `database/` (system of record) and `dashboard/` (published copy) | Must Have | Done | `storage.py:write_outputs` |
| FR-008 | Static dashboard readable with zero backend (GitHub Pages) | Must Have | Done | `dashboard/` |
| FR-009 | Optional API server for live "Tailor Resume" action | Could Have | Done | `dashboard_server.py` |
| FR-010 | Fail closed: if *all* sources error, do not overwrite last good output | Must Have | Done | `agent.py:run` |
| FR-011 | Public repo: no real candidate PII committed, ever | Must Have | **Open — blocking** | See ISSUE-001 |
| FR-012 | Public repo: forkable by a stranger without touching original owner's config/resume | Must Have | Open | Needs onboarding doc + gitignore fix |

### 4.2 Non-Functional Requirements

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-001 | Cost | $0 to run (GitHub Actions free tier + GitHub Pages); low-cost optional Render tier for interactive mode | Met |
| NFR-002 | Availability | Best-effort; a scheduled batch job, not a live service (except optional Render dashboard) | Met for current scope |
| NFR-003 | Scalability | Single profile, single process, sequential source fetch — not designed for concurrent multi-user load | Met for intended (personal) scope; explicitly out of scope to scale further |
| NFR-004 | Resilience | Partial source failure must not fail the run | Met |
| NFR-005 | Portability | Runs on stdlib + 3 small deps, no external DB/queue | Met |

### 4.3 AI Requirements

| ID | Requirement | Priority | Status |
|---|---|---|---|
| AI-001 | Resume tailoring must never invent experience, employers, dates, or metrics | Must Have | Enforced via prompt instructions only — **no output verification step exists** (see Section 17) |
| AI-002 | System must function fully with **zero** LLM calls (rule-based fallback) | Must Have | Done — Ollama is optional; rule-based path is the default when `ollama_model` unset |
| AI-003 | No cloud LLM cost — local-only Ollama | Must Have | Done |

### 4.4 Security Requirements

| ID | Requirement | Priority | Status |
|---|---|---|---|
| SEC-001 | Authentication on dashboard API | Should Have (Must Have if deployed publicly with write access) | **Open** — no auth today |
| SEC-002 | Authorization / tenant isolation | N/A | Not applicable — single-profile-per-deployment by design |
| SEC-003 | Secrets protection | Must Have | Done — Telegram token/Ollama URL via env vars / GitHub Secrets, never committed |
| SEC-004 | No real candidate PII in version control | Must Have | **Open — Critical, see ISSUE-001** |

---

## 5. User Stories

### US-001

**As a:** candidate running my own instance

**I want:** to be notified only about new jobs I haven't seen, scored against my real skills

**So that:** I don't waste time re-reviewing the same listings

**Acceptance Criteria:**

- [x] Re-running the agent with no new jobs sends zero Telegram messages
- [x] `min_score` and `top_n` are configurable

### US-002

**As a:** person who forks this repo

**I want:** to plug in my own profile/resume without exposing the original owner's data or my own

**So that:** the tool is safe to fork publicly

**Acceptance Criteria:**

- [ ] `config/profile.json` and `assets/resume.md` are gitignored, only `.example` templates are tracked
- [ ] README documents the copy-and-edit onboarding flow explicitly

---

## 6. Business Rules

- One candidate profile per deployment (no multi-tenancy).
- A run must never publish output if every source failed (protects last-known-good data).
- Resume rewriting must only add content backed by the candidate's own profile/skills — never fabricate.

---

## 7. Assumptions

- ~~The user's primary goal for "public release" is open-sourcing the code only.~~ **Superseded 2026-09-11**: user confirmed the goal is a **hosted multi-tenant service** — other people log in and use their own data. See Section 41 for the approved architecture.
- "Public" scraping of LinkedIn/Indeed/Naukri carries ToS risk the user accepts for personal use; this is not re-litigated here, just flagged (RISK-002).
- "Tailor based on job role" (Section 41) accepts a typed/pasted job title + description in v1; it does not require deep integration with the existing scraper/ranking pipeline yet (kept as a clean future integration point via an optional `job_id` column).

---

## 8. Constraints

### Budget

Preference: **Free / Open Source / Self-hosted / Free Tier wherever practical** — matches current implementation (GitHub Actions + Pages + optional Render free/low tier + local Ollama).

### Technical Constraints

- Python 3.11, stdlib `http.server` for the API (no framework) — keep as-is; introducing a framework (FastAPI/Flask) is optional polish, not required for correctness.
- Flat JSON file storage — sufficient at current scale (single profile); do not introduce a database unless multi-user hosting becomes the actual goal.

### Business Constraints

- None (personal/open-source project).

### Time Constraints

- None specified.

---

# 9. MVP Definition

*(MVP is already built and running; this section reframes it as "public-release MVP" — the minimum to safely open the repo to the world.)*

## Must Have (blocking public release)

- Remove real PII (`config/profile.json`, `assets/resume.md`) from git tracking and history (ISSUE-001).
- Add a `LICENSE` file.
- README onboarding flow: copy `.example` files, never commit the real ones.

## Should Have

- Basic auth/shared-secret on the dashboard API before recommending others deploy it publicly on Render.
- CONTRIBUTING.md for external contributors.

## Could Have

- Structured logging instead of `print`.
- Retry/backoff on scrapers.
- Docker packaging for easier self-hosting.

## Future

- Multi-profile / multi-user support (would require real auth + a database — a different project shape, see Section 10).

---

# 10. AI Agent Architecture

## Agent Objective

Score and shortlist job listings against a fixed candidate profile; optionally draft (never fabricate) resume-tailoring text for the top matches.

## Agent Type

**AI + rules engine — a deterministic pipeline with one optional, isolated LLM step**, not an autonomous planning/tool-choosing agent.

> **Feasibility note (Phase 3):** This system does *not* need multi-step planning, tool selection, reflection, or a conversational loop — the "AI agent" framing in this master prompt template doesn't fully fit. The pipeline is: fetch → dedupe → score (pure rules) → optionally call an LLM once per job for text generation → notify → publish. Keeping it this way is correct — do **not** retrofit LangChain/LangGraph, a planning loop, or multi-agent orchestration onto this; it would add complexity and cost with no functional benefit. If a future requirement genuinely needs multi-step reasoning (e.g., an agent that reads a job page and decides *whether* to apply autonomously), re-open this section then.

## Agent Workflow (actual, as implemented)

```text
Scheduler (GitHub Actions, every 6h) or manual run
  ↓
Load config/profile.json
  ↓
For each enabled source: fetch_jobs() [isolated try/except per source]
  ↓
Deduplicate (by URL / fingerprint)
  ↓
Filter by location match (optional strict mode)
  ↓
Score 0–100 (skills, title, keywords, location/remote, experience fit) — pure rules, no LLM
  ↓
Filter by min_score, sort, truncate to top_n
  ↓
For top N (max_tailored_jobs): optional single LLM call (Ollama) → ResumeSuggestion
  (falls back to deterministic rule-based suggestion on any LLM failure)
  ↓
Diff against previously-seen job fingerprints → notify only new matches (Telegram)
  ↓
Write jobs.json / summary.json / resume_suggestions.json / state.json to database/ + dashboard/
```

---

## 11. Agent Tools

| Tool | Purpose | Inputs | Outputs | Permission Level | Status |
|---|---|---|---|---|---|
| `JobSource.fetch_jobs()` (7 adapters) | Pull listings from a public job source | queries, keywords, locations | `list[JobListing]` | Outbound HTTP only, no write access | Done (Indeed/Naukri guarded/best-effort) |
| `TelegramNotifier.notify()` | Send alert for new matches | `list[RankedJob]` | count sent | Outbound HTTP to Telegram API only | Done, opt-in |
| `ResumeOptimizer.tailor()` / `apply_tailoring()` | Draft or apply resume tailoring | job, matched_skills, resume text | `ResumeSuggestion` / rewritten resume text | Local Ollama call (optional) + local file write (dashboard flow only) | Done |
| `DashboardService.tailor_resume()` | HTTP-triggered resume rewrite | `job_id` from client | writes `assets/resume.md`, backup, application state | **Unauthenticated** local file write via HTTP | Done, needs SEC-001 before public hosting |

### Tool Safety Rules

- Minimize agent permissions. — Met: no tool has destructive scope beyond the candidate's own resume file.
- Validate tool inputs. — **Partial**: `job_id` is looked up but not otherwise validated/sanitized; acceptable for trusted single-user use, a gap for public multi-user hosting.
- Validate tool outputs. — **Gap**: LLM-generated resume text is not checked against the "no fabrication" instruction beyond prompting (see AI-001, Section 17).
- Use human approval for high-impact actions. — Met by design: resume file write is always human-initiated (button click), never autonomous.
- Apply timeouts and retry limits. — Met for HTTP calls (`timeout=` on all `requests` calls); no retry logic exists (single attempt, fail-open to rule-based fallback for the LLM path).
- Never expose secrets to the model unnecessarily. — Met: Telegram token/Ollama URL never enter any prompt.

---

# 12. AI / LLM Strategy

## Primary Model

None required — rule-based scoring and rule-based resume suggestions are the default, always-available path.

## Backup Model

N/A (rule-based *is* the fallback, not the other way around).

## Optional Model

Local Ollama model (e.g. `llama3.1`), used only if `OLLAMA_MODEL` / `ai.ollama_model` is configured.

## Model Provider

Local (self-hosted via Ollama, `http://127.0.0.1:11434` by default) — no cloud LLM provider is used or required.

## Model Selection Reason

Zero cost, zero external data exposure (resume/job text never leaves the local machine when Ollama is used), and the system degrades gracefully without it.

## Model Abstraction

Not implemented as a formal provider interface — there are exactly two paths (`_tailor_with_ollama` / `_rule_based_tailoring`), hardcoded as try-then-fallback in `resume_optimizer.py`. **This is appropriate at current scope** — introducing a full provider abstraction layer for a single optional local model would be over-engineering (violates Section 30 "avoid unnecessary frameworks"). Revisit only if a second LLM backend is actually needed.

## AI Cost Strategy

Already optimal: $0. Local model only, no token metering needed since there's no paid API in the loop.

---

# 13. Prompt Strategy

## System Prompt / Agent Instructions

Two prompts exist in `resume_optimizer.py`:
1. Suggestion generation (`_tailor_with_ollama`) — requests strict JSON with 4 fixed keys.
2. Resume rewriting (`_rewrite_resume_with_ollama`) — explicit "do not invent experience/companies/dates/certifications/outcomes" constraint, markdown-only output.

## Tool Instructions

N/A — the LLM is not given tool-calling capability; it only transforms text in a single request/response call.

## Prompt Version

v1 (as shipped; no versioning scheme currently tracked in code).

## Prompt Change Policy

Not yet formalized. **Recommendation**: before changing either prompt, manually spot-check 3–5 outputs for fabricated content, since there is no automated eval (see Section 25, AI Evaluation).

---

# 14. Agent Memory

## Short-Term / Working Memory

None needed — each run is stateless in-memory; no conversation, no multi-turn context.

## Long-Term Memory

`database/state.json` → `seen_job_ids` (a set of fingerprints). Purpose: dedup notifications across runs only — not a knowledge store.

## Episodic Memory

N/A — not applicable to this pipeline shape.

## Memory Storage

Flat JSON file on disk (or in the GitHub-committed repo state for the Actions run).

## Memory Retention

Unbounded — `seen_job_ids` only grows. **Open question**: no pruning strategy exists; over years this file will grow without bound (low practical impact — it's a set of SHA-1 hashes, ~40 bytes each).

## Memory Deletion

None implemented. Not currently a problem since no third-party PII is stored in it (job fingerprints only).

## Privacy Rules

- Store only information required for the product. — Met.
- Do not unnecessarily persist sensitive information. — **Violated today** at the repo level (see ISSUE-001) — not by `state.json`, but by `config/profile.json` and `assets/resume.md` being tracked.
- Enforce access controls. — N/A (single local user); becomes relevant only if hosted for others.
- Provide deletion mechanisms. — N/A at current scope.

---

# 15. RAG / Knowledge Base

## Is RAG Required?

**No.** There is no corpus to retrieve from — job descriptions arrive directly as scraped text and are used inline. Do not add a vector database; it would solve a problem this project doesn't have.

*(Remaining RAG subsections intentionally omitted — not applicable.)*

---

# 16. AI Guardrails

| Guardrail | Status |
|---|---|
| Prompt injection (via scraped job descriptions fed into the tailoring prompt) | **Not evaluated** — a malicious job posting could contain text attempting to redirect the LLM's output. Low impact today (output is just resume text a human reviews before use), but worth a smoke test before wider release. |
| Jailbreaking | N/A — no chat surface exposed to untrusted users. |
| Data leakage | Local-only LLM calls — no third-party data exposure by default. If a user configures a cloud model in `ollama_base_url`, their resume text would be sent externally — not currently warned about in docs. |
| Unauthorized tool use | N/A — no tool-selection loop exists. |
| Excessive autonomy / infinite loops | N/A — single-pass pipeline, no iteration loop. |
| Excessive token/API cost | N/A — local model only. |

## Guardrail Strategy

Sufficient for the current single-pass, local-only design. **Recommendation before public release**: add one line to the README warning that pointing `ollama_base_url` at a remote/cloud endpoint sends resume + job text there.

## Maximum Agent Iterations / Maximum Tool Calls / Token Budget

N/A — not a looping agent (see Section 10 feasibility note).

## Human Approval Requirements

Every resume file write is human-triggered (dashboard button click) — no autonomous writes occur.

---

# 17. Hallucination Control

- Prefer verified data over model assumptions. — Scoring is 100% rule-based (no LLM in the ranking path) — correct choice, keeps the trustworthy part trustworthy.
- Validate structured outputs. — **Gap**: the Ollama JSON response is `json.loads`'d and used directly; malformed/missing keys are handled (falls back cleanly), but *content* correctness (e.g., "did it actually avoid inventing experience?") is never verified — it relies entirely on the prompt instruction.
- Verify critical actions before execution. — Partial: a human reviews the tailored resume in the UI before using it, which is the real safety net today.

**Recommendation**: not blocking for public release (impact is limited to the user's own resume, which they review before use), but worth a documented known-limitation note.

---

# 18. Technology Stack

## Frontend

**Technology:** Vanilla HTML/CSS/JS (`dashboard/index.html`, `app.js`, `styles.css`)

**Reason:** Zero build step, deployable as-is to GitHub Pages; matches the project's zero-infrastructure goal.

## Backend

**Technology:** Python 3.11, stdlib `http.server.ThreadingHTTPServer`

**Reason:** No framework dependency for a 4-endpoint API; keeps the deployable surface tiny.

## AI / Agent Framework

**Technology:** None (direct `requests` calls to Ollama's REST API)

**Reason:** A single optional LLM call does not justify LangChain/LangGraph/Semantic Kernel — would add dependency weight and complexity with no functional gain (see Section 10).

## Database

**Technology:** Flat JSON files (`database/`, `dashboard/`)

**Reason:** Single-profile scale, no concurrent multi-user writes today — a real database (PostgreSQL/SQLite) is unnecessary unless the project pivots to multi-user hosting (see Section 9, Future).

## Vector Database

**Technology:** N/A — no RAG (Section 15).

## Cache

**Technology:** None.

**Reason:** Runs are 6-hourly batch jobs; nothing hot enough to cache.

## Authentication

**Technology:** None currently.

**Reason / Gap:** Fine for local/personal use; a real gap if the Render-hosted API is exposed publicly (SEC-001).

## Messaging

**Technology:** Telegram Bot API (outbound only).

## Infrastructure

**Technology:** GitHub Actions (compute) + GitHub Pages (static hosting) + optional Render (persistent API host).

**Reason:** All free or near-free; matches budget constraint.

## CI/CD

**Technology:** GitHub Actions (`.github/workflows/ai-agent.yml`, `static.yml`). No lint/test/security-scan stage currently — see Section 25/28 gaps.

## Monitoring / Logging

**Technology:** None (stdout `print` + `summary.json` per run).

**Reason / Gap:** Adequate for a solo batch job; a real gap if this becomes a hosted service others depend on.

---

# 19. Technology Decision Matrix

| Area | Selected Technology | Alternatives | Why Selected | Cost | Lock-in Risk |
|---|---|---|---|---|---|
| Frontend | Vanilla HTML/JS | React/Vue | No build step, GH Pages-native | Free | None |
| Backend | Python stdlib `http.server` | FastAPI/Flask | 4 endpoints don't need a framework | Free | None |
| LLM | Local Ollama (optional) | Cloud APIs (OpenAI/Anthropic) | Free, private, and fully optional | Free | None |
| Storage | Flat JSON | SQLite/Postgres | Single-profile scale; simplest thing that works | Free | Low (easy migration path if needed) |
| Hosting | GitHub Pages + Render free/low tier | Vercel, Netlify, self-VPS | Already free/near-free, already wired up | Free–low | Low |

---

# 20. System Architecture

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full component diagram, sequence diagrams, data model, and deployment topology (already produced and current as of this update). Not duplicated here to avoid drift between two copies of the same diagrams.

## Architecture Principles

- Prefer simplicity. — Met (no framework, no DB, no queue).
- Avoid unnecessary microservices. — Met (2 processes: batch agent, optional dashboard server).
- Keep AI providers replaceable where practical. — Partially met; acceptable given single optional provider (Section 12).
- Design for security. — **Gap**, see Section 23.

---

# 21. Database Design

**Database:** None — flat JSON files serve as the persistence layer.

| "Entity" (file) | Purpose | Status |
|---|---|---|
| `database/jobs.json` | Ranked jobs from the latest run | Done |
| `database/summary.json` | Run metadata/stats | Done |
| `database/state.json` | Seen-job fingerprints (dedup) | Done |
| `database/resume_suggestions.json` | Per-job resume suggestions | Done |
| `database/resume_application_state.json` | Tailoring history per job | Done |

## Migration / Backup Strategy

N/A for a JSON-file store; the files themselves are the backup (committed to git each run, so full history is in git log).

---

# 22. API Design

## API Style

Minimal REST-ish, JSON over HTTP (no OpenAPI spec today).

## Authentication

**None.** Required before recommending public multi-user hosting (SEC-001).

## Key Endpoints

| Method | Endpoint | Purpose | Auth | Status |
|---|---|---|---|---|
| GET | `/api/health` | Liveness/API-detection for the frontend | None | Done |
| GET | `/api/resume` | Resume metadata | None | Done |
| GET | `/api/resume/download` | Download resume as `.docx` | None | Done |
| POST | `/api/tailor-resume` | Rewrite resume for a given `job_id` | **None** | Done, needs SEC-001 |

---

# 23. Security Architecture

## Authentication / Authorization / RBAC

Not implemented. Acceptable for local/single-user use; **required** before advertising the Render deployment as something others should expose publicly.

## Secrets Management

Env vars / GitHub Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `DASHBOARD_API_URL`) — never committed. **Done correctly.**

## Data Protection

**Critical gap (ISSUE-001):** `config/profile.json` (real candidate profile) and `assets/resume.md` (real name, personal email, phone number) are currently tracked in git and already pushed to the public repo `github.com/bingaditya/Job-Scraper-Agent`, across multiple historical commits.

## API Security

CORS wide open (`Access-Control-Allow-Origin: *`); no rate limiting; `job_id` trusted from client without deeper validation. Acceptable for solo local use only.

## AI Security

See Section 16 (prompt injection via scraped job text — not yet evaluated, low current impact).

## Audit Logging

None — only `summary.json` per run, not append-only/tamper-evident. Not a practical concern at current scale.

---

# 24. Project Structure

Actual structure (already matches the template reasonably well):

```text
Job-Scraper-Agent/
├── job_hunter/            (⇔ src/)
│   ├── sources/
│   ├── agent.py, config.py, models.py, ranking.py,
│   │   resume_optimizer.py, resume_converter.py,
│   │   notifications.py, storage.py, dashboard_service.py
├── tests/
├── docs/
│   ├── HLD.md
│   └── ARCHITECTURE.md      (docs/adr/ not yet created — see Section 30)
├── dashboard/               (static frontend + published JSON)
├── database/                (system-of-record JSON)
├── config/profile.example.json  (tracked) / profile.json (should NOT be tracked)
├── assets/resume.md         (should NOT be tracked)
├── .github/workflows/
├── main_agent.py, dashboard_server.py
├── PROJECT_CONTEXT.md
└── README.md
```

**Gap:** no `CHANGELOG.md`, no `LICENSE`.

---

# 25. Testing Strategy

## Existing

`tests/test_storage.py`, `test_ranking.py`, `test_resume_optimizer.py`, `test_dashboard_service.py` — unit-level coverage of the deterministic/testable core.

## Gaps

- No tests for `job_hunter/sources/*` (fragile HTML-selector scrapers — most likely thing to silently break).
- No integration test for the full `JobHunterAgent.run()` pipeline end-to-end.
- No API tests for `dashboard_server.py` endpoints.
- No AI evaluation (Section not applicable in the traditional sense given the narrow, optional LLM usage — but a handful of "does the LLM path still avoid fabrication" spot checks would be worthwhile before public release, see Section 17).

---

# 26. Performance

Not a target-driven system — batch job every 6 hours, single profile. No performance requirements currently defined or needed.

---

# 27. Observability

**Current:** `print()` statements + `summary.json` per run (source-level success/failure, counts). Sufficient for a solo batch job; would need real structured logging/monitoring only if this becomes a hosted service for others.

---

# 28. DevOps

## CI/CD

`ai-agent.yml` runs the agent + deploys Pages; **no lint, no test execution, no security scan stage**. Gap for a public repo accepting external contributions.

## Docker

None. Not required for the GitHub Actions / Render paths as configured, but would lower the barrier for other self-hosters (Could Have, Section 9).

## Deployment Targets

- GitHub Pages (static, free) — primary, already working.
- Render (optional, persistent API) — already configured via `render.yaml`.

---

# 29. Cost Model

| Component | Option | Monthly Cost Estimate | Free Tier | Notes |
|---|---|---:|---|---|
| Compute (scrape/rank) | GitHub Actions | $0 | Yes (public repo = unlimited minutes) | |
| Static hosting | GitHub Pages | $0 | Yes | |
| Interactive API (optional) | Render free/low tier | $0–7 | Yes (with cold starts) | |
| LLM | Local Ollama | $0 | N/A (self-hosted) | |
| Notifications | Telegram Bot API | $0 | Yes | |

Already at the target cost profile — no optimization needed here.

---

# 30. Architecture Decision Records

`docs/adr/` does not exist yet. **Recommended first ADRs**, once created:

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Use flat JSON files instead of a database | Proposed (retroactive) |
| ADR-002 | Keep LLM usage optional/local-only, no provider abstraction layer | Proposed (retroactive) |
| ADR-003 | Untrack real profile/resume; require history purge for public release | Proposed |

---

# 31. Risks

| ID | Risk | Probability | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| RISK-001 | Real PII (name/email/phone) already public in git history | Certain (already occurred) | Critical | Untrack files now; rewrite/purge git history (`git filter-repo`); consider rotating exposed contact info | **Resolved 2026-09-10** (history purged; rotation of phone/email still the user's own call) |
| RISK-002 | LinkedIn/Indeed/Naukri scraping violates target sites' ToS | Medium | Medium (IP ban / takedown request) | README disclaimer; keep LinkedIn opt-in; add basic rate limiting | Open |
| RISK-003 | If Render API URL becomes known, anyone can trigger resume overwrites (no auth) | Low today (URL not advertised), rises if publicized | Medium–High | Add shared-secret/basic auth before promoting the Render deployment publicly | Open |
| RISK-004 | Scrapers depend on exact HTML structure of third-party sites and can silently degrade | Medium | Low–Medium (fewer/no jobs from a source, not a crash) | Add per-source zero-result alerting; scraper tests with saved fixtures | Open |

---

# 32. Dependencies

| Dependency | Purpose | Version | Risk | Status |
|---|---|---|---|---|
| `requests` | HTTP client for all scrapers + Telegram + Ollama | `>=2.31,<3` | Low, widely maintained | Active |
| `beautifulsoup4` | HTML parsing for scrapers | `>=4.12,<5` | Low | Active |
| `python-docx` | Resume `.docx` export | `>=1.1,<2` | Low | Active |

No dependency scanning (e.g. `pip-audit`, Dependabot) currently configured — worth adding to CI for a public repo.

---

# 33. Open Questions

- Is the actual public-release goal "open-source the code for others to fork" (current assumption, Section 7) or "host this as a service other people log into"? The answers to Sections 4.4/18/23 differ substantially depending on which.
- Should the exposed personal phone/email (already public) be treated as compromised (i.e., proactively changed), or is the user comfortable leaving it as-is since it's already out?
- Is a git history rewrite (destructive: breaks any existing forks/clones, rewrites all commit hashes) acceptable, or should the fix be forward-only (untrack now, leave history as-is, accept the historical exposure)?

---

# 34. Known Issues

| ID | Issue | Severity | Status | Workaround |
|---|---|---|---|---|
| ISSUE-001 | Real candidate PII (name, email, phone) committed and pushed to public repo via `config/profile.json` and `assets/resume.md` | **Critical** | **Resolved 2026-09-10** | History rewritten with `git-filter-repo` (89→88 commits), force-pushed to origin/main, both files gitignored going forward. Caveat: cannot guarantee removal from any pre-existing forks/clones or GitHub caches. |
| ISSUE-002 | No `LICENSE` file | Medium | Open | Add one (e.g. MIT) before advertising the repo as open source |
| ISSUE-003 | Dashboard API has no authentication and open CORS | High (if publicly hosted) | Open | Keep Render deployment private/undocumented until SEC-001 addressed |
| ISSUE-004 | Indeed/Naukri sources fail due to bot protection | Low | Open, by design | Already documented in README as best-effort |
| ISSUE-005 | No rate limiting/backoff on scraper requests | Medium | Open | Add delay/backoff, especially for LinkedIn |

---

# 35. Change Log Summary

| Date | Change | Reason | Impact |
|---|---|---|---|
| 2026-09-06 | Created `docs/HLD.md` and `docs/ARCHITECTURE.md` from full codebase analysis | Requested documentation of existing system | Establishes architecture baseline |
| 2026-09-06 | Identified real PII committed to public repo during public-release readiness review | User asked what's needed for public release | Surfaced ISSUE-001 / RISK-001 |
| 2026-09-10 | Retrofitted `PROJECT_CONTEXT.md` against existing implementation per user-provided SDLC framework | User adopted this governance template | Established current SDLC phase/gate and full gap list |

---

# 36. Current Implementation Status

## Completed

- [x] Project initialized (pre-existing)
- [x] Requirements gathered (reconstructed from code, this document)
- [x] Requirements analyzed (Section 4)
- [x] AI feasibility completed (Section 10 — concluded: rules engine + optional LLM, not an autonomous agent)
- [x] MVP defined (original MVP shipped; public-release MVP defined in Section 9)
- [x] Technology selected (Section 18)
- [x] Architecture approved (see `docs/ARCHITECTURE.md`)
- [x] Database designed (flat-file, Section 21)
- [x] APIs designed (Section 22)
- [ ] Security designed — **gap, Section 23**
- [x] Agent architecture designed (Section 10–11)
- [x] Memory designed (Section 14 — minimal, by design)
- [x] RAG designed (Section 15 — concluded not needed)
- [x] Implementation started (already substantially complete)
- [ ] Tests implemented — partial (Section 25)
- [ ] AI evaluation implemented — not started (low priority given narrow LLM usage)
- [ ] Security testing completed — **not started, blocking public release**
- [ ] CI/CD implemented — partial (no lint/test/security-scan stage)
- [x] Deployment completed (GitHub Pages + Render both working)
- [ ] Production readiness completed — **not started**

## Current Blockers

- **ISSUE-001**: real PII in git history/tracked files. Blocks safely making the repo public.

## Next Action

**Decide and execute the ISSUE-001 fix** (untrack files; decide on history rewrite — see Open Questions), then proceed to Gate 11 — Security Review (auth on the dashboard API) before Gate 13 — Production Readiness.

---

# 37. SDLC Status

| Phase | Status |
|---|---|
| 1. Requirement Gathering | 🟢 Complete (retroactive) |
| 2. Requirement Analysis | 🟢 Complete (retroactive) |
| 3. AI Feasibility | 🟢 Complete — concluded rules-engine + optional local LLM is correct, no agent framework needed |
| 4. MVP Definition | 🟢 Complete |
| 5. Technology Selection | 🟢 Complete (retroactive) |
| 6. Architecture | 🟢 Complete — see `docs/ARCHITECTURE.md` |
| 7. Detailed Design | 🟢 Complete (retroactive) |
| 8. Development | 🟢 Complete for current scope |
| 9. Testing | 🟡 In Progress — core logic covered, scrapers/API untested |
| 10. AI Evaluation | ⚪ Not Started — low priority given narrow, optional LLM usage |
| 11. Security Review | 🔴 Blocked — ISSUE-001 must be resolved first |
| 12. Deployment | 🟡 In Progress — infra works, hardening pending |
| 13. Production Readiness | ⚪ Not Started |
| 14. Maintenance | ⚪ Not Started |

Legend:

- 🟢 Complete
- 🟡 In Progress
- 🔴 Blocked
- ⚪ Not Started

---

# 38. Rules for Claude Code

Claude Code MUST:

1. Read this file before substantial work.
2. Inspect the existing repository before changing architecture.
3. Keep this file synchronized with the actual project.
4. Never silently change major architectural decisions.
5. Document major decisions in ADRs.
6. Update the current SDLC phase.
7. Track blockers and open questions.
8. Prefer free/open-source solutions where practical.
9. Consider AI cost on every architecture decision.
10. Consider security on every feature.
11. Test every significant feature.
12. Evaluate AI behavior, not only traditional software correctness.
13. Never hard-code secrets.
14. Avoid unnecessary complexity.
15. Do not declare the project production-ready until the production-readiness checklist has been completed.

---

# 39. Change Protocol

For every significant change:

```text
READ PROJECT_CONTEXT.md
        ↓
UNDERSTAND CURRENT SYSTEM
        ↓
ANALYZE CHANGE
        ↓
IDENTIFY IMPACT
        ↓
PLAN
        ↓
IMPLEMENT
        ↓
TEST
        ↓
REVIEW
        ↓
UPDATE DOCUMENTATION
        ↓
UPDATE PROJECT_CONTEXT.md
        ↓
UPDATE ADR IF REQUIRED
```

---

# 40. Source of Truth

This file is the **persistent project context**.

If the conversation history and this file appear to conflict:

1. Identify the conflict.
2. Determine which decision is newer.
3. Ask for clarification if the difference is material.
4. Update this file after the decision.

Do not silently discard architectural history.

---

# 41. Multi-Tenant Hosting Pivot (Approved, In Progress)

## Decision Summary (2026-09-11)

Approved architecture for the hosted multi-user resume feature — full detail lives in the approved plan file: **`C:\Users\shamb\.claude\plans\floofy-greeting-spindle.md`** (read this file first in any continuation session; it is the single source of truth for this feature's design).

- **Upload format**: DOCX only for v1 (PDF explicitly out of scope — no reliable in-place text-editing model exists for PDF while preserving design).
- **Backend/Auth/DB/Storage**: **Supabase** — hosted Postgres + built-in Auth (email/password) + Storage buckets, free tier. User provisions the project manually (Claude cannot create third-party accounts).
- **LLM provider**: **Groq** (console.groq.com — NOT xAI's paid "Grok" API, a naming mix-up caught and corrected this session). OpenAI-compatible chat-completions API, genuinely free rate-limited "Developer Plan" tier. User already has an API key.
- **New backend**: a separate FastAPI service (existing `dashboard_server.py`/stdlib `http.server` stays untouched — it's fine for the existing wide-open static dashboard; the new authenticated file-upload surface genuinely needs multipart + JWT handling that stdlib doesn't reasonably provide).
- **Versioning model**: `resume_versions` table, one row per version (upload or AI-tailored), `is_current` flag, `parent_version_id` chain — a full history, not a rigid "one backup" slot.
- **DOCX design preservation**: paragraph-level text extraction/replacement via `python-docx` (replace `runs[0].text`, clear other runs in that paragraph) — never touches document theme/styles/section-properties/tables, so layout survives. Documented limitation: intra-paragraph mixed-run formatting and floating text boxes/graphic-heavy designer resumes won't round-trip perfectly; typical corporate-style resumes will.
- This is **additive** — the existing scraper → score → Telegram → static-dashboard pipeline (GitHub Actions + GitHub Pages) is untouched and keeps running exactly as today.

## Correction (2026-09-12): Supabase API key system

The original plan assumed legacy Supabase auth: `anon`/`service_role` keys (JWTs) + a shared HS256
`SUPABASE_JWT_SECRET`. The user's actual project uses Supabase's **newer** system:
- API keys are `sb_publishable_...` / `sb_secret_...` — opaque strings, not JWTs. `StorageConfig`
  fields are `supabase_publishable_key`/`supabase_secret_key` (env: `SUPABASE_PUBLISHABLE_KEY`/
  `SUPABASE_SECRET_KEY`), not `supabase_anon_key`/`supabase_service_role_key`.
- User session JWTs are signed with an **asymmetric** key (this project: ECC P-256 / ES256) under
  Supabase's "JWT Signing Keys" system, verified via the project's public JWKS endpoint
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) rather than a shared secret. There is no
  `SUPABASE_JWT_SECRET` — `job_hunter/auth.py` uses `jwt.PyJWKClient` to fetch/cache the public
  signing key by `kid` and verifies with `ES256`/`RS256`. **This only works for projects on the
  new JWT Signing Keys system** — a project still on the Legacy JWT Secret system would need a
  different (HS256, shared-secret) verification path, not implemented here since it doesn't apply
  to this project.
- `requirements.txt`: `pyjwt` → `pyjwt[crypto]` (the `cryptography` backend is required for
  ES256/RS256 verification).
- `tests/test_auth.py` rewritten to generate a real EC keypair and mock `PyJWKClient.get_signing_key_from_jwt`, rather than testing HS256 shared-secret verification.

## Implementation Status (as of 2026-09-12)

**M0 — DONE.** Supabase project created (`xuphcxftqpltucikgwob.supabase.co`), migration run
(`resume_versions` table confirmed present and queryable). Project is on the new JWT Signing Keys
system (confirmed via dashboard screenshot + live JWKS fetch).

**Live end-to-end verification — PASSED** (real signup via admin-confirmed test user, real JWT
verified against the live JWKS endpoint, real Supabase Storage + Postgres, all through the actual
FastAPI app via TestClient): upload → 201, list → 1 row, download → byte-identical, tailor
(no `GROQ_API_KEY` set, so rule-based fallback) → 200, new version created as current, prior
version correctly archived (`is_current=False`), tailored `.docx` confirmed to have the skills
paragraph correctly extended ("Python, SQL, Git, Docker, CI/CD") with every other paragraph
untouched. Test user, rows, and storage objects were cleaned up afterward. **The Groq AI path
itself (as opposed to its rule-based fallback) has not yet been live-tested** — needs the user's
actual `GROQ_API_KEY` value to verify.

**M1 — plumbing, no AI: code complete, tested without live Supabase.**
- [x] `migrations/001_resume_versions.sql`
- [x] `requirements.txt` (`fastapi`, `uvicorn`, `python-multipart`, `pyjwt`, `supabase` — installed locally and confirmed working, e.g. FastAPI resolved to 0.141.1)
- [x] `job_hunter/config.py` — `StorageConfig`, `GroqConfig` + env-var wiring
- [x] `config/profile.example.json` — placeholder `storage`/`groq` blocks
- [x] `job_hunter/auth.py` — Supabase JWT verification (HS256, `aud=authenticated`); unit-tested in `tests/test_auth.py` (accepts valid token, rejects wrong-secret/expired/missing-token/missing-server-secret — 5 tests, all passing)
- [x] `job_hunter/resume_store.py` — Supabase Postgres+Storage service class (untestable without a live project; interface exercised via a fake in tests/test_api_routes.py)
- [x] `job_hunter/api/{app,routes_resume,schemas}.py` — FastAPI app; health/config/upload/list/download endpoints confirmed working via `TestClient` and via `tests/test_api_routes.py` (byte-identical download verified)
- [x] `dashboard/login.html` — signup/login (Supabase JS v2 CDN client) + upload/list/download UI
- [x] Live M1 verification against the real Supabase project — **passed** (see above)

**M2 — AI tailoring + versioning: code complete, tested without live Groq/Supabase.**
- [x] `job_hunter/keyword_utils.py` — extracted from `resume_optimizer.py` (behavior-preserving; existing resume_optimizer tests still pass)
- [x] `job_hunter/groq_client.py` — `chat_json()`, treats HTTP 429 as expected/fallback-triggering, not exceptional
- [x] `job_hunter/docx_tailor.py` — paragraph-level extract/replace (`runs[0].text`, clear other runs), Groq path + rule-based fallback (finds a skills-list paragraph, appends missing skills); tested in `tests/test_docx_tailor.py` (3 tests: Groq path preserves bold formatting, falls back correctly when Groq unavailable, makes no edit when nothing to add)
- [x] `POST /api/resumes/tailor` wired up; tested in `tests/test_api_routes.py` (tailoring creates a new current version, previous version retained and flagged non-current — the core "keep a backup" requirement, verified)
- [x] `dashboard/login.html` — added a tailor form (job title/description/skills → calls the endpoint, shows the result)
- [x] Live M2 verification of the rule-based fallback path — **passed** (see above)
- [x] Live verification of the actual Groq AI path — **passed** (see below), after fixing two real issues found during testing

**Design gap resolved during implementation**: the approved plan deferred a per-user `profiles` table (v1 has none). This left no source for "skills to emphasize" during tailoring — using the old single-owner `config/profile.json` skills would have leaked one user's profile into every other user's tailoring, a real multi-tenant correctness bug. Fixed by adding an optional `skills: list[str]` field directly to the tailor request instead (per-request, not persisted) — forward-compatible with adding a real profiles table later without an API break.

**Test suite**: 19 tests total, all passing (`python -m unittest discover -s tests`) — 7 pre-existing + 5 auth + 3 docx_tailor + 4 API integration tests.

**M3 — polish**: not started (version-history UI polish, `job_id` picker from `database/jobs.json`, 429 loading/error UX).

## Live Groq verification (2026-09-12) — two real issues found and fixed

1. **Stale default model.** `llama-3.3-70b-versatile` no longer exists on Groq (confirmed via a
   raw 404 from the API, then `GET /models` to list what's actually hosted now — Groq's lineup
   has shifted heavily toward `openai/gpt-oss-120b`/`openai/gpt-oss-20b`, Qwen, and Groq's own
   `compound` models; no Llama chat models remain as of this session). Default model in
   `GroqConfig`/`load_config()`/`config/profile.example.json` updated to `openai/gpt-oss-120b`,
   confirmed working with `response_format: json_object`. **If Groq calls ever start 404ing
   again, re-run `GET {base_url}/models` with the configured key rather than guessing a new
   model name — Groq's hosted lineup rotates.**
2. **Prompt was overly conservative.** The original `_SYSTEM_PROMPT` in `docx_tailor.py` said
   "do not invent experience... if a paragraph needs no change, return it unchanged" — the model
   (a reasoning model) interpreted this as license to echo every paragraph back unchanged,
   including the skills list, which is explicitly supposed to gain new relevant skills. Fixed by
   splitting the instruction into two explicit cases: skills/technology list paragraphs (adding a
   given "skill to emphasize" is expected, not fabrication) vs. narrative paragraphs (rephrase
   freely, never invent employers/dates/degrees/metrics). Verified consistent across 3 repeated
   live calls after the fix. **If this regresses again, dump the model's `reasoning` field from
   the raw API response (not just `content`) to see its actual chain of thought — that's what
   revealed the true cause here, a plain content-diff would not have.**

Full live verification (real Supabase test user, real Groq call, real `.docx` round-trip) now
confirms: `changed=True`, `mode=groq`, the skills paragraph correctly extended
("Python, SQL, Git, REST APIs, Docker, Kubernetes, AWS, CI/CD"), bold formatting on an untouched
paragraph preserved, and no fabricated career facts added to the narrative paragraph. Test data
cleaned up afterward.

## Next Action (resume here)

1. Set env vars permanently for local dev (currently only exported ad hoc per test command) and
   in the Render deployment when ready to deploy this service. Consider adding `GROQ_MODEL` and
   Supabase creds to the user's actual `config/profile.json` (already gitignored) rather than
   re-exporting env vars every session.
2. Proceed to M3 polish (version-history UI, `job_id` picker from `database/jobs.json`, 429/loading UX), or address anything else the user raises first.

---

# 42. Resume-Based Personalized Job Matching + Apply-to-Tailor (2026-09-12, DONE)

## What this adds

Full plan: `C:\Users\shamb\.claude\plans\floofy-greeting-spindle.md` (Connect Job
Scraping/Ranking to Resume-Based Personalized Matching + One-Click Apply). Extends the resume
feature (Section 41) so that: (1) uploading/tailoring a resume extracts a candidate profile
(skills, preferred titles, experience years) via Groq, stored per-user; (2) the shared scraped
job pool (already produced by the existing `job_hunter/agent.py` pipeline) is now also exported
unfiltered as `database/raw_jobs.json`; (3) each logged-in user gets `GET /api/jobs`, their own
personalized ranking of that shared pool computed with the **existing, unmodified**
`job_hunter/ranking.py::score_job()`; (4) `dashboard/login.html` shows this list with one-click
**Apply**, which calls the existing tailor endpoint pre-filled from that specific job — no manual
paste required.

**Stated trade-off (still true)**: job *fetching* stays shared/scheduled (one crawl, same search
queries as before); only *scoring* is personalized per user. A user whose skills are very
different from the pool's search terms will see fewer matches — documented, not silently hidden.

## New/changed files

- New: `migrations/002_candidate_profiles.sql` (per-user extracted profile, RLS same pattern as
  `resume_versions`), `job_hunter/resume_profile.py` (Groq-then-rules extraction, mirrors
  `docx_tailor.py`'s pattern), `job_hunter/api/routes_jobs.py` (`GET /api/jobs`)
- Changed: `job_hunter/keyword_utils.py` (shared `find_skills_line_index` extracted out of
  `docx_tailor.py` so both modules reuse it), `job_hunter/resume_store.py`
  (`get_candidate_profile`/`upsert_candidate_profile`), `job_hunter/api/routes_resume.py` (calls
  extraction after every upload/tailor; tailor now falls back to the stored profile's skills when
  the request doesn't pass any explicit `skills`), `job_hunter/api/schemas.py` (`JobMatchOut`
  includes the real job `description`, not a synthesized one — needed for genuine Groq context on
  Apply), `job_hunter/agent.py` + `job_hunter/storage.py` (emit `database/raw_jobs.json`, the
  deduped-but-unscored pool, **not** duplicated to `dashboard/`), `dashboard/login.html` (Job
  Matches section with Apply, manual tailor form kept as secondary option)

## Live verification — PASSED (full chain, real Supabase + real Groq)

Upload a resume with real skills (Python, Docker, Kubernetes, CI/CD, PostgreSQL) → confirmed
`candidate_profiles` row extracted correctly → `GET /api/jobs` against a 3-job fixture pool
correctly ranked the Docker/Kubernetes job highest (score 78), a partially-matching Python job
lower (score 42), and correctly excluded the unrelated React job entirely → clicked "Apply"
(called the tailor endpoint with that job's real `job_id`/description) → new version created
(`ai_tailored`, `mode=groq`, `fit_score=100`), prior versions correctly archived → downloaded
result showed the AI naturally wove Docker/Kubernetes/CI-CD into the professional summary
(genuinely already-listed skills, not fabricated) while correctly leaving the already-complete
skills line untouched. All test data cleaned up afterward.

## Operational note found this session — stale background process

Restarting the local dev `uvicorn` process via `pkill -f "uvicorn job_hunter.api.app"` **did not
actually kill it** in this Windows/Git-Bash environment — the old process kept holding port 8001,
silently serving stale code while a new (correctly-coded) process failed to bind and exited. This
produced confusing false negatives (404 on a route that existed in the code, a missing DB row
that had never actually been requested). **Fix**: verify a restart actually worked by checking
`netstat -ano | grep ":<port>" | grep LISTENING` for the PID, and force-kill with Windows-native
`taskkill //F //PID <pid>` if it's still there — don't trust `pkill` alone on this platform, and
don't trust a `/health` 200 response as proof the *new* code is running (an old process answers
health checks identically).

---

# END OF PROJECT CONTEXT
