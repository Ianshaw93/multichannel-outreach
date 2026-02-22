# Health Check System

## Overview

Production health checks run 2x/day (10am, 3pm UK) via APScheduler in the speed_to_lead service. They query the DB for liveness signals and only alert Slack when something looks wrong.

- **Code:** `speed_to_lead/app/services/health_check.py`
- **Tests:** `speed_to_lead/tests/test_health_check.py`
- **Endpoints:** `POST /admin/health-check` (auth), `GET /admin/health-check/status` (no auth)
- **Slack:** Alerts to metrics channel on WARNING/CRITICAL only

## When to Add a Check

After building any new feature that creates a data flow, assess whether it has a **liveness signal** - data that should appear regularly if the feature is working. Add a check if:

- New webhook endpoint (data should arrive periodically)
- New scheduled task (should produce records on schedule)
- New external service integration (should have recent activity)
- New pipeline that writes to DB (should have recent runs)

## How to Add a Check

1. **Create function** in `speed_to_lead/app/services/health_check.py`:
   ```python
   async def check_<name>(session: AsyncSession) -> CheckResult:
       # Query DB for liveness signal
       # Return CheckResult with OK, WARNING, or CRITICAL
   ```

2. **Add to orchestrator list** in same file:
   ```python
   ALL_CHECKS = [
       ...existing checks...,
       check_<name>,
   ]
   ```

3. **Write tests** in `speed_to_lead/tests/test_health_check.py`:
   - Test OK case (data present)
   - Test WARNING case (data stale)
   - Test CRITICAL case (if applicable)

No scheduler changes needed - the orchestrator auto-runs all checks in `ALL_CHECKS`.

## Threshold Guidelines

| Cadence | WARNING | CRITICAL |
|---------|---------|----------|
| Continuous (messages) | 36-48h silence | 48-72h silence |
| Daily (reports, metrics) | >2 days stale | >4 days stale |
| Weekly (pipelines) | >7 days | - |
| On-demand | Softer thresholds | - |

Weekend awareness: Mondays widen inbound/outbound thresholds to avoid false alarms.

## Rules

- Health checks must **only use DB queries**. Never call paid APIs (Apify, DeepSeek, etc.)
- Each check is independent - one failing check doesn't block others
- Errors in individual checks are caught and reported as WARNING (not crash the whole run)
- OK = silent (logged only). WARNING/CRITICAL = Slack alert

## Current Checks (9)

| # | Check | OK if... |
|---|-------|----------|
| 1 | inbound_messages | Any inbound in last 48h |
| 2 | outbound_messages | Any outbound in last 36h |
| 3 | draft_generation | All inbound convos have drafts |
| 4 | slack_delivery | All drafts have slack_message_ts |
| 5 | stale_pending_drafts | <4 pending >24h old |
| 6 | prospect_freshness | New prospect in last 7d |
| 7 | daily_metrics | Entry within last 2d |
| 8 | pipeline_runs | Recent successful run |
| 9 | connection_tracking | connection_sent_at in last 7d |
