# Cross-Repo Sync

You are syncing cross-cutting knowledge across the 3 smiths sub-repos. Run this after creating anything sibling repos should know about (new endpoint, schema change, data flow, convention, scheduled job, decision).

All repos live under the umbrella: `C:\Users\IanShaw\Documents\localProgramming\smiths\LI_cross_repo\` (sub-repos: `speed_to_lead/`, `multichannel-outreach/`, `contentCreator/`).

## Files

- **Canonical knowledge**: `LI_cross_repo/CROSS_REPO.md` (umbrella root). This is the ONLY file you edit.
- **Decision log**: `LI_cross_repo/DECISIONS.md` — dated entries for anything decided/shelved/retired.
- **In-repo copies**: `.claude/CROSS_REPO.md` in each sub-repo are AUTO-GENERATED (for standalone/web access). Never edit them.

## Workflow

1. **Identify what changed** in the current repo that is cross-cutting: endpoints, schema, metrics, conventions, data flows, scheduled jobs, infrastructure.
2. **Edit the canonical file**: `../CROSS_REPO.md` (umbrella root). Keep the structure: Hard Rules → routing table → verified facts. If a decision was made, add a dated entry to `../DECISIONS.md` instead of burying it in prose.
3. **Regenerate copies** from the umbrella root:
   ```bash
   cd .. && bash sync_cross_repo.sh
   ```
4. **Update sibling CLAUDE.md files** only for project-specific knowledge that belongs there (e.g. a new endpoint a specific sibling must call).
5. **Commit**: the umbrella repo (CROSS_REPO.md, DECISIONS.md) and each sub-repo whose `.claude/CROSS_REPO.md` changed. **Do not push sub-repos without checking with Ian if unrelated uncommitted work exists** — a push to speed_to_lead triggers a production deploy.

## What NOT to sync

- Project-internal implementation details, temp/experimental features, credentials, WIP.
