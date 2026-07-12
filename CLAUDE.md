# CLAUDE.md

**Read `.claude/CROSS_REPO.md` first** — shared hard rules, routing table, and system facts for the 3-repo system. It is an auto-generated copy; the canonical file is `../CROSS_REPO.md` in the umbrella repo (which also has `DECISIONS.md` and step-by-step `playbooks/`).

> `AGENTS.md` and `GEMINI.md` in this repo are pointers to this file — this is the single source of instructions.

## Related Projects

Part of a 3-project system under `C:\Users\IanShaw\Documents\localProgramming\smiths\LI_cross_repo\`:

| Project | Path | Purpose |
|---------|------|---------|
| **speed_to_lead** | `../speed_to_lead` | Prospecting & lead tracking (owns DB schema, Railway deployment, ALL API endpoints) |
| **multichannel-outreach** | (this repo) | Messaging & outreach automation |
| **contentCreator** | `../contentCreator` | Content generation |

The shared API is deployed from **speed_to_lead** at `https://speedtolead-production.up.railway.app`. Any new API endpoint goes in `speed_to_lead/app/main.py`, never in this repo.

## ⚠️ HeyReach Is Shelved (2026-07-04)

LinkedIn outreach runs through **Unipile** (in speed_to_lead) + Slack. Every HeyReach script in `execution/` (`add_leads_to_heyreach.py`, `json_to_heyreach.py`, `linkedin_outreach_heyreach.py`, `personalize_and_upload.py`'s upload step, `heyreach_webhook.py`, …) is **inert — do not run, fix, or build on them** without asking Ian. Pipeline docs below that end in "upload to HeyReach" are useful up to that final step only. See `../DECISIONS.md` for what was shelved and the known gaps.

## Common Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_competitor_post_pipeline.py -v

# Run execution scripts (always from repo root; scripts use sys.path imports)
python execution/competitor_post_pipeline.py --keywords "ceos" --list_id 480247 --dry_run
python execution/gift_leads_list.py --prospect-url "https://linkedin.com/in/johndoe" --dry-run
python execution/buying_signal_outreach.py --csv .tmp/signals.csv --dry-run
python execution/sync_prospects_to_db.py --file .tmp/leads.json --source competitor_post

# Local API server (dev only — production endpoints live in speed_to_lead)
uvicorn execution.api_server:app --host 0.0.0.0 --port 8000

# Deploy webhooks
modal deploy execution/modal_webhook.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture: 3-Layer System

LLMs are probabilistic; business logic is deterministic. This architecture fixes that mismatch.

**Layer 1: Directive** — SOPs in Markdown (`directives/`). Goals, inputs, tools, outputs, edge cases.

**Layer 2: Orchestration** — You. Read directives, call execution scripts in order, handle errors, update directives with learnings. Don't do the work yourself — route to scripts.

**Layer 3: Execution** — Deterministic Python scripts (`execution/`). API calls, data processing, file ops, DB interactions.

**Why:** 90% accuracy per step = 59% success over 5 steps. Push complexity into deterministic code.

## Key Execution Pipelines

**Competitor Post Pipeline** (`execution/competitor_post_pipeline.py`): Google search → filter posts by reactions → scrape engagers (Apify) → scrape profiles → location filter → ICP qualify (DeepSeek) → personalize DMs. (Final HeyReach upload step: shelved.)

**Gift Leads List** (`execution/gift_leads_list.py`): Scrape prospect profile → research ICP (DeepSeek) → generate search queries → find posts → scrape engagers → ICP qualify → signal notes → export JSON/CSV.

**Buying Signal Outreach** (`execution/buying_signal_outreach.py`): Gojiberry CSV → scrape posts (Apify) → personalize 5-line DMs → output JSON.

**Sync to DB** (`execution/sync_prospects_to_db.py`): Read prospect JSONs from `.tmp/` → POST to speed_to_lead API.

## External Services & APIs

- **Unipile** — LinkedIn messaging/connections (integration lives in speed_to_lead, not here)
- **Apify** — Web scraping (profile scraper: `dev_fusion~Linkedin-Profile-Scraper`)
- **DeepSeek** — LLM for ICP qualification and DM personalization
- **Modal** — Serverless webhook hosting
- **Google Sheets/Slides** — Deliverable outputs via `gspread` + OAuth
- **Gojiberry** — Buying signal source (webhook into speed_to_lead)
- **HeyReach** — SHELVED (see above)
- **Vayne.io** — DEPRECATED (no subscription); use the Apify profile scraper

## Operating Principles

0. **Be concise.**
1. **Check for tools first** — check `execution/` per your directive before writing a new script.
2. **Log costs for all paid actions** to the speed_to_lead DB (see CROSS_REPO.md "Cost Tracking").
3. **Self-anneal** — read error → fix script → test → update directive with learnings. Don't retry paid actions without user confirmation.
4. **Update directives as you learn.** Don't create/overwrite directives without asking.
5. **Never modify `execution/prompts.py` without explicit permission** — single source of truth for all personalization prompts; never inline duplicates.
6. **Assess health check needs after building** — any feature with a liveness signal needs a check in speed_to_lead: `../playbooks/add-health-check.md`. (Note: `directives/health_check_system.md` claims a 2x/day schedule — that schedule was removed 2026-03-07; checks are manual-trigger, see CROSS_REPO.md KNOWN GAP.)

## File Organization

- `.tmp/` — Intermediate files. Never commit, always regenerable. Deliverables live in cloud services (Sheets, Slides), not local files.
- `execution/` — Python scripts (run from repo root; they `sys.path.insert` and import siblings directly, e.g. `from prompts import ...`)
- `directives/` — SOPs in Markdown
- `.env` — API keys; `credentials.json` / `token.json` — Google OAuth (gitignored)

## Cloud Webhooks (Modal)

Each webhook maps to one directive with scoped tool access.

**Adding a webhook:** read `directives/add_webhook.md` → create directive → add entry to `execution/webhooks.json` → `modal deploy execution/modal_webhook.py` → test.

**Endpoints:**
- `https://nick-90891--claude-orchestrator-list-webhooks.modal.run` — List webhooks
- `https://nick-90891--claude-orchestrator-directive.modal.run?slug={slug}` — Execute directive
- `https://nick-90891--claude-orchestrator-test-email.modal.run` — Test email

**Available tools:** `send_email`, `read_sheet`, `update_sheet`. All activity streams to Slack.

## Cross-Repo Propagation

After completing work, assess whether siblings need to know (webhook/Modal changes, pipeline changes affecting the shared DB, template/personalization logic, conventions). Run `/sync-siblings`: edit the canonical `../CROSS_REPO.md`, log decisions in `../DECISIONS.md`, regenerate copies with `../sync_cross_repo.sh`. Never hand-edit `.claude/CROSS_REPO.md`.
