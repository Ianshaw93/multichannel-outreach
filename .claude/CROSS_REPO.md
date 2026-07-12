> **AUTO-GENERATED COPY — do not edit.** Canonical file: `LI_cross_repo/CROSS_REPO.md` (umbrella repo root). Regenerate with `../sync_cross_repo.sh`. Synced: 2026-07-12.

---
# Smiths Cross-Repo Knowledge

Shared knowledge base for the 3 smiths sub-repos. **Canonical file: `LI_cross_repo/CROSS_REPO.md`** (umbrella repo root). Each sub-repo carries an auto-generated copy at `.claude/CROSS_REPO.md` — never edit the copies; edit this file and run `./sync_cross_repo.sh`.

Last verified against code: 2026-07-12. Dated decisions and history live in `DECISIONS.md`.

## Hard Rules

1. **HeyReach is shelved (2026-07-04).** Do not build on, fix, or resurrect any HeyReach integration without asking Ian. LinkedIn outreach runs through Unipile + Slack.
2. **All API endpoints live in speed_to_lead** (`app/main.py`). Other repos call the deployed API; they never host their own endpoints.
3. **Schema changes only via speed_to_lead's Alembic migrations.** (contentCreator's own tables via `create_tables()` are a legacy exception — don't extend the pattern.)
4. **Never cite counts from Obsidian docs** — see "Stale Sources" below. Query the live Postgres instead (`playbooks/query-funnel-state.md`).
5. **Log every paid action** (API calls, Apify runs, LLM tokens) to the speed_to_lead DB. See "Cost Tracking".
6. **Never run the full pytest suite in speed_to_lead** — it can hang indefinitely. Run specific files: `pytest tests/test_x.py -v`.
7. **Run `railway status` before any state-changing Railway command.** The CLI may be linked to the Postgres service — `railway redeploy` there restarts the database.
8. **Never modify `execution/prompts.py`** (multichannel-outreach or contentCreator) without explicit permission.
9. **Don't recommend paid enrichment tools** (Apollo / Clay / AnyMailFinder). Email enrichment = Unipile pull from LinkedIn profiles we already have URLs for.
10. **Don't retry paid actions after an error** without user confirmation.
11. **Correct base path**: `C:\Users\IanShaw\Documents\localProgramming\smiths\LI_cross_repo\`. Any doc citing `C:\Users\IanShaw\localProgramming\...` (no `Documents`) is stale — that path move already cost us the voice-note send CLI.

## Where Do I Look?

Playbooks live in the umbrella repo only (`LI_cross_repo/playbooks/`) — they involve local CLI/DB access. From inside a sub-repo they're at `../playbooks/`.

| Need | Go to |
|---|---|
| Funnel counts / prospect state / queue depth | `playbooks/query-funnel-state.md` |
| Connection sends stopped or slowed | `playbooks/diagnose-stopped-sends.md` |
| Load new prospects into the sender queue | `playbooks/refill-sender-queue.md` — **has a retag gotcha** |
| Add or change an API endpoint | `speed_to_lead/app/main.py` (rule 2) |
| DB models / schema | `speed_to_lead/app/models.py`; migrations in `speed_to_lead/alembic/versions/` |
| Add a health check | `playbooks/add-health-check.md` |
| Deploy speed_to_lead and verify it | `playbooks/deploy-and-verify.md` |
| Location / firm-phone enrichment | `playbooks/run-location-enrichment.md` |
| What runs on a schedule | "Scheduled Jobs" table below |
| Why something was decided / shelved / retired | `DECISIONS.md` |
| Outreach pipeline scripts + SOPs | `multichannel-outreach/execution/` + `multichannel-outreach/directives/` |
| Content generation | `contentCreator/execution/` |
| Strategy, offer, niche narrative | Obsidian vault via the obsidian-notes skill (narrative only — numbers are stale, DB is truth) |

## System Overview

| Project | Path | Purpose | Deployed? |
|---------|------|---------|-----------|
| **speed_to_lead** | `speed_to_lead/` | FastAPI backend, prospect tracking, sales funnel, DB models, all scheduled jobs | Yes (Railway) |
| **multichannel-outreach** | `multichannel-outreach/` | Messaging pipelines, outreach automation, webhook orchestration | Scripts only (Modal webhooks) |
| **contentCreator** | `contentCreator/` | LinkedIn content generation, drafts, hooks, ideas | Scripts only |

(`scalingSmiths/` is an untracked Next.js site in the umbrella dir — not part of this system yet.)

### Database
- **Single PostgreSQL instance** on Railway, shared by all 3 projects.
- Internal URL: `postgres.railway.internal` (Railway-only). Public proxy: `crossover.proxy.rlwy.net:56267`.
- No local `.env` carries `DATABASE_URL` — fetch it via Railway CLI (see `playbooks/query-funnel-state.md` for the exact steps, including the personal-account and PowerShell gotchas).
- **speed_to_lead owns the schema** (Alembic). contentCreator has legacy tables (Draft, Hook, Idea, Insight, Image) via SQLAlchemy `create_tables()`.

### API Server
- **Single deployed API**: `https://speedtolead-production.up.railway.app` (Railway auto-deploys `speed_to_lead` from GitHub pushes).

## Scheduled Jobs (verified against `speed_to_lead/app/main.py`, 2026-07-12)

All scheduling lives in speed_to_lead's APScheduler, registered in `app/main.py` lifespan. Times are Europe/London.

| Job | Schedule | Code |
|---|---|---|
| Safety engineering briefing → Obsidian | daily 7:00 | `app/services/safety_briefing.py` |
| Unipile acceptance sweep (stamps `connection_accepted_at`, pulls emails) | daily 7:45 | `app/services/acceptance_sweep.py` |
| Accepted-connections Slack digest | daily 8:00 | `app/services/scheduler.py` |
| Comment engagement poll (own comments → prospect match → Slack) | every 2 days 8:30 | `app/services/comment_engagement_poll.py` |
| Voice note poll (Unipile → Whisper → DB → Slack) | daily 9:17 | `app/services/voice_note_poll.py` |
| Unipile connection burst (probabilistic fire) | every 30 min, 9–18 | `app/services/unipile_sender.py` |
| Unipile Sunday catch-up to weekly cap | Sun 11:00 | `app/services/unipile_sender.py` |
| Health checks (Slack alert on failure) | daily 10:00 + 15:00 | `app/services/health_check.py` `run_health_check_task` |

(The health-check cron was accidentally removed 2026-03-07 and silently absent for four months — restored 2026-07-12. See DECISIONS.md.)

## Sales Funnel

```
Connection Req Sent → Accepted → Initial Msg → Positive Reply → Pitched → Calendar Shown → Booked
```

Timestamps on `Prospect`: `connection_sent_at`, `connection_accepted_at`, `positive_reply_at`, `pitched_at`, `calendar_sent_at`, `booked_at`. Stage enum: `FunnelStage` (POSITIVE_REPLY, PITCHED, CALENDAR_SENT, BOOKED) on `Conversation.funnel_stage`. Connection requests are sent by the Unipile burst sender; acceptance is detected only by the daily acceptance sweep.

## Available API Endpoints (speed_to_lead)

### Admin/Metrics
- `GET /admin/prospects/funnel` — Prospects at pitched+ stage
- `GET /admin/draft/{draft_id}` — View draft content
- `POST /admin/run-migrations` — Run DB migrations (needs `Authorization: Bearer SECRET_KEY`)
- `POST /admin/health-check` (auth) / `GET /admin/health-check/status` (no auth)
- `GET /admin/poll-comment-engagement` — Manual comment-poll trigger
- `GET /health` — Liveness check

### Webhooks
- `POST /webhook/buying-signal` — Buying signal from Gojiberry
- `POST /webhook/heyreach*` — inert (HeyReach shelved), kept for history

### Clients (Ex-Client Info Store)
- `POST /api/clients` — Add a client (name required)
- `GET /api/clients` — List (optional `?status=active|paused|churned|ex_client`)
- `GET /api/clients/{client_id}` / `PATCH /api/clients/{client_id}`
- Model: `Client` in `app/models.py` — `name`, `email`, `linkedin_url`, `company`, `status`, `case_study_data` (JSON), `notes`, optional `prospect_id` FK, `started_at`, `ended_at`.

### Costs
- `POST /api/costs` — Batch-log cost entries
- `GET /api/costs` — List (filterable by project, provider)
- `GET /api/costs/summary` — Aggregated summary

## Cross-Repo Data Flows

1. **multichannel-outreach** discovers prospects → creates them in shared DB → **speed_to_lead** tracks funnel.
2. **speed_to_lead** detects positive replies → pitched message flow.
3. **contentCreator** generates content → drafts in DB → usable for outreach messaging.
4. **Buying signals** (Gojiberry webhook) → stored on prospects → inform personalization.

## Unipile LinkedIn Pipeline (operational facts)

- **Burst sender** (`app/services/unipile_sender.py`): targets prospects with `source_keyword = 'safety engineering'` AND `connection_sent_at IS NULL`. Caps via Railway env `UNIPILE_MAX_PER_DAY` / `UNIPILE_MAX_PER_WEEK` (10/50 since 2026-07-04 ramp; see DECISIONS.md).
- **Refill**: `scripts/load_ehs_firms.py` tags prospects `safety engineering` by default since 2026-07-12 — loading IS queueing (`--source-keyword` stages a batch unsent instead). Procedure + verification: `playbooks/refill-sender-queue.md`. Batches loaded under other tags still need a retag.
- **Acceptance sweep** is the ONLY acceptance detection for Unipile-sent invites. Also pulls contact email into `Prospect.email` (1st-degree only).
- **Comment poll** Unipile quirk: share-URL ids (`urn:li:share:X`) resolve to a post whose real `social_id` is a different `urn:li:activity:` — always query comments against the resolved `social_id`.
- **Voice notes**: poll/transcribe side works (`app/services/voice_note_poll.py`, `voice_notes` table). The interactive SEND CLI is lost (pre-`Documents` path move, never committed). Sending is manual via the LinkedIn app until rebuilt.
- **Location + firm-phone enrichment**: `scripts/enrich_locations.py`, standalone, throttled with per-run caps — see `playbooks/run-location-enrichment.md`.

## Email Enrichment

Unipile pulls emails from LinkedIn profiles we already have URLs for — NOT Apollo / AnyMailFinder / Clay (rule 9). Prospect LI URLs are curated in Obsidian (`Smiths/Safety Engineering niche/`). Reasoning: Obsidian `Smiths/Cold Email - Infrastructure & Strategy.md` §5a.

## Cost Tracking

All actions that incur a cost MUST be logged to the speed_to_lead database.

- `PipelineRun` in `app/models.py` tracks prospecting pipeline costs.
- Non-pipeline costs: log via the `/api/costs` endpoints.
- Required fields: source repo, action name, service (apify/openai/anthropic/etc.), cost amount, timestamp.

## Health Check System

- **Code**: `speed_to_lead/app/services/health_check.py` — active checks in `ALL_CHECKS` (5), HeyReach-era checks parked in `SHELVED_HEYREACH_CHECKS` (6).
- **Schedule**: 2x/day (10:00 + 15:00 UK) via APScheduler, registered in `app/main.py` lifespan. Manual trigger: `POST /admin/health-check` (auth) / `GET /admin/health-check/status` (no auth).
- **Adding a check**: `playbooks/add-health-check.md` (also `multichannel-outreach/directives/health_check_system.md`).
- **After building any feature with a new data flow** (webhook, scheduled task, pipeline writing to DB): assess whether it needs a liveness check.

## Shared Conventions

- **Railway CLI**: works in PowerShell directly; in Git Bash requires `cmd.exe /c "railway ..."` (and even that wrapper is unreliable for some commands — prefer PowerShell).
- **PostgreSQL enums**: `DO $$ BEGIN CREATE TYPE ... EXCEPTION WHEN duplicate_object THEN NULL; END $$` for idempotent creation.
- **Environment**: `.env` files locally, Railway env vars in production.

## Related Projects (Outside This Repo)

- **L&S Cold Email** (`G:\My Drive\Scaling Smiths\L&S\Cold Email\`) — Smartlead-based cold email targeting the safety engineers list. Prior Claude transcripts: `~/.claude/projects/G--My-Drive-Scaling-Smiths-L-S-Cold-Email/`. Check there before starting new cold-email work.

## Stale Sources — Do Not Cite

Read for narrative context only; never cite their counts. The live DB is the source of truth for prospect counts, ICP breakdowns, and funnel state.

- `Obsidian Vault/Smiths/Offer Context - Safety Engineering.md` — "Market Size" section
- `Obsidian Vault/Smiths/Safety Engineering niche/Prospecting Status - March 2026.md` — frozen 2026-03-23
- `Obsidian Vault/Smiths/Cold Email - Infrastructure & Strategy.md` §4 — TAM table
- `speed_to_lead/.claude/strategy.md` — strategy narrative, funnel numbers frozen ~2026-02/03

## How to Update This File

When you create something cross-cutting (new endpoint, shared convention, data flow change, scheduled job):

1. Edit **this file** (umbrella root) — never the `.claude/CROSS_REPO.md` copies.
2. Run `./sync_cross_repo.sh` from the umbrella root to regenerate the copies.
3. If a decision was made (something shelved, a cadence chosen, a tool retired), add a dated entry to `DECISIONS.md`.
4. Commit the umbrella repo and each sub-repo whose copy changed.

Or run `/sync-siblings` in any sub-repo to follow the full workflow.
