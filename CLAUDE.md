# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_competitor_post_pipeline.py -v

# Run execution scripts (always from repo root, scripts use relative imports)
python execution/competitor_post_pipeline.py --keywords "ceos" --list_id 480247 --dry_run
python execution/gift_leads_list.py --prospect-url "https://linkedin.com/in/johndoe" --dry-run
python execution/buying_signal_outreach.py --csv .tmp/signals.csv --dry-run
python execution/sync_prospects_to_db.py --file .tmp/leads.json --source competitor_post

# Local API server
uvicorn execution.api_server:app --host 0.0.0.0 --port 8000

# Deploy webhooks
modal deploy execution/modal_webhook.py

# Install dependencies
pip install -r requirements.txt
```

## Related Projects

Part of a 3-project prospecting/outreach system:

| Project | Path | Purpose |
|---------|------|---------|
| **speed_to_lead** | `../speed_to_lead` | Prospecting & lead tracking (owns DB schema, Railway deployment) |
| **multichannel-outreach** | (this repo) | Messaging & outreach automation |
| **contentCreator** | `../contentCreator` | Content generation |

Read `.claude/CROSS_REPO.md` for shared context (endpoints, data flows, conventions).

## Railway Deployment

The shared API server is deployed under **speed_to_lead** on Railway:
- **URL:** `https://speedtolead-production.up.railway.app`
- **Source repo:** `speed_to_lead` (NOT this repo)

Any new API endpoints must be added to `speed_to_lead/execution/api_server.py`.

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

## Architecture: 3-Layer System

LLMs are probabilistic; business logic is deterministic. This architecture fixes that mismatch.

**Layer 1: Directive** — SOPs in Markdown (`directives/`). Define goals, inputs, tools, outputs, edge cases.

**Layer 2: Orchestration** — You. Read directives, call execution scripts in order, handle errors, update directives with learnings. Don't do the work yourself—route to scripts.

**Layer 3: Execution** — Deterministic Python scripts (`execution/`). API calls, data processing, file ops, DB interactions.

**Why:** 90% accuracy per step = 59% success over 5 steps. Push complexity into deterministic code.

## Key Execution Pipelines

**Competitor Post Pipeline** (`execution/competitor_post_pipeline.py`): Google search → filter posts by reactions → scrape engagers (Apify) → scrape profiles → location filter → ICP qualify (DeepSeek) → personalize DMs → upload to HeyReach

**Gift Leads List** (`execution/gift_leads_list.py`): Scrape prospect profile → research ICP (DeepSeek) → generate search queries → find posts → scrape engagers → ICP qualify → generate signal notes → export JSON/CSV

**Buying Signal Outreach** (`execution/buying_signal_outreach.py`): Gojiberry CSV → scrape posts (Apify) → personalize 5-line DMs → output JSON

**Personalize & Upload** (`execution/personalize_and_upload.py`): Vayne JSON → ICP check (DeepSeek) → personalize → validate → re-personalize failures → upload to HeyReach

**Sync to DB** (`execution/sync_prospects_to_db.py`): Read prospect JSONs from `.tmp/` → POST to speed_to_lead API

## External Services & APIs

- **HeyReach** — LinkedIn outreach automation (API: `api.heyreach.io`)
- **Apify** — Web scraping (profile scraper: `dev_fusion~Linkedin-Profile-Scraper`)
- **DeepSeek** — LLM for ICP qualification and DM personalization
- **Modal** — Serverless webhook hosting
- **Google Sheets/Slides** — Deliverable outputs via `gspread` + OAuth
- **Gojiberry** — Buying signal source (webhook into speed_to_lead)

## Deprecated Tools

**Vayne.io (`scrape_linkedin_vayne.py`)** — No active subscription. Use Apify `dev_fusion~Linkedin-Profile-Scraper` instead.

## Operating Principles

**0. Be concise**

**1. Check for tools first** — Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Log costs for all paid actions** — API calls, Apify, LLM tokens, etc. must be logged to the speed_to_lead database. See CROSS_REPO.md "Cost Tracking".

**3. Self-anneal when things break** — Read error → fix script → test → update directive with learnings (API limits, timing, edge cases). Don't retry paid actions without user confirmation.

**4. Update directives as you learn** — Directives are living documents. Don't create/overwrite without asking. Improve over time.

**5. Never modify prompts without explicit permission** — `execution/prompts.py` is the single source of truth. All personalization scripts import from it. Never inline duplicate prompts.

**6. Assess health check needs after building** — After completing any feature that creates a new data flow (webhook, pipeline, scheduled task, external integration), assess whether the health check system needs a new check. If the feature has a "liveness signal" (data that should appear regularly if working), add a check. See `directives/health_check_system.md`.

## File Organization

- `.tmp/` — Intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` — Python scripts (deterministic tools). Scripts run from repo root.
- `directives/` — SOPs in Markdown (instruction set)
- `execution/prompts.py` — All AI prompt templates (DO NOT modify without permission)
- `.env` — Environment variables and API keys
- `credentials.json`, `token.json` — Google OAuth credentials (in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.). Everything in `.tmp/` can be deleted and regenerated.

## Script Import Pattern

Execution scripts use `sys.path.insert` and import sibling modules directly. When running from repo root, use `python execution/script.py`. Scripts import prompts via `from prompts import ...` (relative to `execution/` on `sys.path`).

## Cloud Webhooks (Modal)

Each webhook maps to one directive with scoped tool access.

**Adding a webhook:**
1. Read `directives/add_webhook.md`
2. Create directive file in `directives/`
3. Add entry to `execution/webhooks.json`
4. Deploy: `modal deploy execution/modal_webhook.py`
5. Test the endpoint

**Endpoints:**
- `https://nick-90891--claude-orchestrator-list-webhooks.modal.run` — List webhooks
- `https://nick-90891--claude-orchestrator-directive.modal.run?slug={slug}` — Execute directive
- `https://nick-90891--claude-orchestrator-test-email.modal.run` — Test email

**Available tools:** `send_email`, `read_sheet`, `update_sheet`. All activity streams to Slack.

## Cross-Repo Propagation

After completing work, assess whether sibling repos need updates. Propagate when you change:
- Webhook endpoints or Modal functions
- Outreach pipeline changes affecting shared DB
- Message templates or personalization logic
- Conventions that apply across repos

Run `/sync-siblings` to propagate, or manually update `../CROSS_REPO.md` and copy to `.claude/CROSS_REPO.md` in each repo.
