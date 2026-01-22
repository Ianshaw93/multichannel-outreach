# LinkedIn Sales Navigator → Outreach Pipeline

## Goal
Complete end-to-end pipeline from LinkedIn Sales Navigator search to personalized outreach campaigns. Automates lead filtering, scraping, enrichment, personalization, and sending.

## Overview

This is the master directive that orchestrates all three phases:

**Phase 1: Lead Filtering & Scraping** → [linkedin_sales_nav_scraping.md](linkedin_sales_nav_scraping.md)
- Input: Sales Navigator URL
- Output: Google Sheet with verified LinkedIn leads
- Includes: ICP verification, auto-adjustment of filters

**Phase 2: Contact Enrichment** → [linkedin_contact_enrichment.md](linkedin_contact_enrichment.md)  
- Input: Google Sheet from Phase 1
- Output: Same sheet with enriched emails
- Includes: Bulk API optimization, two-pass enrichment

**Phase 3: Outreach & Personalization** → [linkedin_outreach_personalization.md](linkedin_outreach_personalization.md)
- Input: Google Sheet from Phase 2
- Output: Active campaign with personalized messages
- Includes: AI personalization, smart sending, response tracking

## Quick Start

### Single Command (All Phases)

```bash
python3 execution/linkedin_full_pipeline.py \
  --sales_nav_url "https://www.linkedin.com/sales/search/..." \
  --icp_criteria "Decision-makers in HVAC companies" \
  --total_count 500 \
  --campaign_name "HVAC Owners Q1" \
  --message_template templates/hvac_outreach.txt
```

This will automatically:
1. Test scrape 25 leads
2. Verify ICP match (stop if <80%)
3. Full scrape 500 leads
4. Upload to Google Sheets
5. Enrich with AnyMailFinder bulk API
6. Generate personalized lines with Claude
7. Launch HeyReach campaign

**Total time**: ~20-30 minutes for 500 leads  
**Total cost**: ~$150-250 (mostly PhantomBuster/HeyReach/APIs)

### Step-by-Step (Recommended for First Run)

**Phase 1: Scrape & Verify**
```bash
# Test scrape
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "YOUR_URL" \
  --max_items 25 \
  --output .tmp/test_leads.json

# Verify ICP match
python3 execution/verify_linkedin_leads.py \
  --input .tmp/test_leads.json \
  --icp_criteria "Decision-makers in HVAC" \
  --output .tmp/verified.json

# If >80% match, proceed with full scrape
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "YOUR_URL" \
  --max_items 500 \
  --output .tmp/leads_full.json

# Upload to sheet
python3 execution/update_sheet.py \
  --input .tmp/leads_full.json \
  --sheet_name "LinkedIn Leads - HVAC - Q1 2025"
```

**Phase 2: Enrich Emails**
```bash
# Get sheet URL from Phase 1, then enrich
python3 execution/enrich_emails.py "https://docs.google.com/spreadsheets/d/..."

# Optional: Two-pass enrichment (Apollo for remaining)
python3 execution/enrich_emails_apollo.py "https://docs.google.com/spreadsheets/d/..."
```

**Phase 3: Personalize & Send**
```bash
# Generate personalized lines
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --output_column "personalized_line"

# Launch HeyReach campaign
python3 execution/linkedin_outreach_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --campaign_name "HVAC Q1" \
  --message_template templates/hvac_outreach.txt \
  --daily_limit 50
```

## Decision Tree

```
START: Sales Navigator URL
  ↓
Test Scrape (25 leads)
  ↓
Verify ICP Match?
  ├─ ≥80% → Full Scrape
  ├─ 60-79% → Ask user: Adjust or Proceed?
  └─ <60% → STOP: Refine filters
      ↓
      Agent suggests filter adjustments
      ↓
      User updates URL → Retry Test Scrape
  ↓
Full Scrape (N leads)
  ↓
Upload to Google Sheets
  ↓
Enrich Emails
  ├─ <200 rows → Concurrent API
  └─ ≥200 rows → Bulk API
  ↓
Match rate check?
  ├─ ≥40% → Good data quality
  └─ <40% → Warn: Low match, check data
  ↓
Generate Personalization
  ↓
Quality check (sample 10 lines)?
  ├─ Good → Proceed
  └─ Generic → Adjust prompt, retry
  ↓
Launch Campaign
  ├─ HeyReach (recommended)
  └─ PhantomBuster (fallback)
  ↓
Monitor Daily
  ├─ Acceptance rate <15% → Pause, analyze
  ├─ Reply rate <5% → Adjust messaging
  └─ All good → Continue
  ↓
END: Active campaign running
```

## File Structure

```
directives/
  linkedin_sales_nav_pipeline.md          ← You are here (master orchestrator)
  linkedin_sales_nav_scraping.md          ← Phase 1
  linkedin_contact_enrichment.md          ← Phase 2
  linkedin_outreach_personalization.md    ← Phase 3

execution/
  # Phase 1
  scrape_linkedin_phantombuster.py
  verify_linkedin_leads.py
  
  # Phase 2 (reuses existing)
  enrich_emails.py
  enrich_emails_apollo.py
  
  # Phase 3
  generate_personalization.py
  linkedin_outreach_heyreach.py
  linkedin_outreach_phantombuster.py
  linkedin_campaign_stats.py
  
  # Full pipeline
  linkedin_full_pipeline.py

  # Shared utilities (already exist)
  update_sheet.py
  read_sheet.py

templates/
  hvac_outreach.txt
  default_linkedin_personalization_prompt.txt
```

## Google Sheet Schema

The sheet created/updated throughout the pipeline has these columns:

**From Phase 1 (Scraping):**
- `full_name`, `first_name`, `last_name`
- `title`, `company_name`, `company_domain`
- `linkedin_url`, `location`
- `headline` (LinkedIn headline)
- `icp_match` (match/maybe/no_match)
- `icp_reason` (why they match)

**Added in Phase 2 (Enrichment):**
- `email` (enriched)
- `email_status` (valid/risky/not_found)
- `phone` (if available from Apollo)

**Added in Phase 3 (Personalization):**
- `personalized_line` (AI-generated opener)
- `outreach_status` (queued/sent/accepted/replied)
- `sent_at` (timestamp)
- `campaign_id` (HeyReach or PhantomBuster)

## Performance Benchmarks

| Metric | Target | Notes |
|--------|--------|-------|
| ICP match rate | ≥80% | Test scrape verification |
| Email enrichment rate | 40-70% | Depends on data quality |
| Connection acceptance rate | 20-40% | With personalization |
| Reply rate | 5-15% | Interested prospects |
| Pipeline time (500 leads) | 20-30 min | All phases |
| Cost per lead (full pipeline) | $1.50-2.50 | Excluding tool subscriptions |

## Agent Role (You)

Your job as orchestrator:

1. **Verification**: Check ICP match rates, make go/no-go decisions
2. **Adjustment**: Suggest filter changes if verification fails
3. **Quality Control**: Sample personalized lines before sending to all
4. **Error Handling**: Retry failed API calls, fall back to alternatives
5. **Reporting**: Provide clear status updates at each phase
6. **Learning**: Update directives when discovering new edge cases

## Error Handling

### Phase 1 Errors
- **PhantomBuster timeout**: Retry with smaller batch
- **LinkedIn session expired**: Prompt user to re-authenticate
- **Low ICP match**: Don't proceed, refine filters

### Phase 2 Errors
- **AnyMailFinder API error**: Fall back to Apollo
- **Rate limit hit**: Implement exponential backoff
- **Low enrichment rate**: Warn user, check data quality

### Phase 3 Errors
- **Generic personalization**: Improve prompt, regenerate
- **HeyReach API error**: Fall back to PhantomBuster
- **Low acceptance rate**: Pause campaign, analyze issues

## Edge Cases

### No Sales Navigator Access
- **Problem**: User doesn't have Sales Navigator
- **Solution**: Use regular LinkedIn search + PhantomBuster, but expect lower quality
- **Alternative**: Use Apollo's intent data to build lead lists

### Duplicate Leads Across Campaigns
- **Problem**: Same lead appears in multiple scrapes
- **Solution**: Use `linkedin_url` as unique key, deduplicate before enrichment
- **Script**: `execution/deduplicate_leads.py`

### Multi-Region Campaigns
- **Problem**: Want to target multiple countries/regions
- **Solution**: Create separate Sales Navigator searches per region, then combine
- **Benefit**: Better personalization per region

### Follow-up Sequences
- **Problem**: Want multi-touch campaigns (connection → message → email)
- **Solution**: Use HeyReach's sequence builder or see `directives/multichannel_outreach_campaign.md`

## Dependencies

### API Keys Required
- `PHANTOMBUSTER_API_KEY` (Phase 1)
- `ANTHROPIC_API_KEY` (Phases 1 & 3)
- `ANYMAILFINDER_API_KEY` or `APOLLO_API_KEY` (Phase 2)
- `HEYREACH_API_KEY` or `PHANTOMBUSTER_API_KEY` (Phase 3)
- `GOOGLE_APPLICATION_CREDENTIALS` (all phases)

### Tool Subscriptions
- **LinkedIn Sales Navigator**: $79-99/month
- **PhantomBuster**: $30-100/month (depends on usage)
- **HeyReach**: $79-99/month per seat
- **AnyMailFinder or Apollo**: Pay-per-email or monthly

### Python Packages
All already in `requirements.txt`:
- `apify-client`, `anthropic`, `gspread`, `requests`, `httpx`

## Learnings

- Always start with 25-lead test scrape - saves money if filters are wrong
- ICP verification catches bad data early (worth the $0.50 in API costs)
- Bulk email enrichment is 10x faster than individual calls for 200+ leads
- Personalization is THE differentiator - acceptance rates 2-3x higher
- HeyReach is worth the cost vs PhantomBuster for serious campaigns
- LinkedIn soft-limits are real (50-100/day) - don't exceed or account gets flagged
- Best to run pipeline during business hours (better response rates)
- A/B test messages on small batch (50) before scaling to 500+
- Track metrics daily - early signals predict campaign success
- Update this directive with learnings from each campaign











