# LinkedIn Sales Navigator → Outreach Pipeline

Complete automation system for scraping LinkedIn Sales Navigator leads, enriching contact data, and launching personalized outreach campaigns.

## Overview

This pipeline automates the entire lead generation and outreach process:

1. **Phase 1**: Scrape & verify LinkedIn profiles from Sales Navigator
2. **Phase 2**: Enrich with verified work emails  
3. **Phase 3**: Generate AI personalization and launch campaigns

## Quick Start

### Prerequisites

1. **API Keys Required** (add to `.env`):
   ```bash
   PHANTOMBUSTER_API_KEY=your_key
   ANTHROPIC_API_KEY=your_key
   ANYMAILFINDER_API_KEY=your_key
   HEYREACH_API_KEY=your_key
   GOOGLE_APPLICATION_CREDENTIALS=credentials.json
   LINKEDIN_SESSION_COOKIE=your_li_at_cookie
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Get LinkedIn Session Cookie**:
   - Log in to LinkedIn in your browser
   - Open DevTools (F12) → Application → Cookies
   - Copy the value of the `li_at` cookie
   - Add to `.env`: `LINKEDIN_SESSION_COOKIE=YOUR_COOKIE_VALUE`

### Run the Pipeline

**Step 1: Scrape & Verify Leads**

```bash
# Test scrape (25 leads to verify ICP match)
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "https://www.linkedin.com/sales/search/..." \
  --max_items 25 \
  --output .tmp/test_leads.json

# Verify ICP match
python3 execution/verify_linkedin_leads.py \
  --input .tmp/test_leads.json \
  --icp_criteria "Decision-makers (CEO, Owner, VP) in HVAC companies" \
  --output .tmp/verified.json

# If >80% match, do full scrape
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "YOUR_URL" \
  --max_items 500 \
  --output .tmp/leads_full.json

# Upload to Google Sheets
python3 execution/update_sheet.py \
  --input .tmp/leads_full.json \
  --sheet_name "LinkedIn Leads - HVAC - Q1 2025"
```

**Step 2: Enrich Emails**

```bash
# Enrich with AnyMailFinder (bulk API for 200+ rows)
python3 execution/enrich_emails.py "https://docs.google.com/spreadsheets/d/..."

# Optional: Two-pass enrichment with Apollo for remaining emails
python3 execution/enrich_emails_apollo.py "https://docs.google.com/spreadsheets/d/..."
```

**Step 3: Personalize & Launch Campaign**

```bash
# Generate personalized opening lines
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --output_column "personalized_line" \
  --prompt_template default_linkedin

# Launch HeyReach campaign
python3 execution/linkedin_outreach_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --campaign_name "HVAC Q1 2025" \
  --message_template templates/hvac_outreach.txt \
  --type connection_request \
  --daily_limit 50
```

## Architecture

This follows the **3-layer architecture**:

### Layer 1: Directives (SOPs)
- `directives/linkedin_sales_nav_pipeline.md` - Master orchestrator
- `directives/linkedin_sales_nav_scraping.md` - Phase 1
- `directives/linkedin_contact_enrichment.md` - Phase 2
- `directives/linkedin_outreach_personalization.md` - Phase 3

### Layer 2: Orchestration (You, the Agent)
- Read directives
- Make go/no-go decisions (ICP verification, quality checks)
- Handle errors and fallbacks
- Update directives with learnings

### Layer 3: Execution (Python Scripts)
- `execution/scrape_linkedin_phantombuster.py` - PhantomBuster scraping
- `execution/verify_linkedin_leads.py` - LLM-based ICP verification
- `execution/enrich_emails.py` - AnyMailFinder enrichment (existing)
- `execution/enrich_emails_apollo.py` - Apollo.io enrichment
- `execution/generate_personalization.py` - AI personalization
- `execution/linkedin_outreach_heyreach.py` - HeyReach campaign launch
- `execution/update_sheet.py` - Google Sheets updates (existing)

## Decision Tree

```
START: Sales Navigator URL
  ↓
Test Scrape (25 leads)
  ↓
ICP Match ≥80%?
  ├─ YES → Full Scrape → Continue
  └─ NO → Refine filters → Retry
  ↓
Upload to Google Sheets
  ↓
Enrich Emails (bulk API if 200+ rows)
  ↓
Generate Personalization
  ↓
Quality Check (sample 10 lines)
  ├─ Good → Launch Campaign
  └─ Generic → Adjust prompt → Retry
  ↓
Monitor Daily (acceptance rate, reply rate)
```

## Cost Breakdown (per 500 leads)

| Component | Cost |
|-----------|------|
| PhantomBuster scraping | $5-10 |
| ICP verification (Claude) | $1-2 |
| Email enrichment (AnyMailFinder) | $50-75 |
| Personalization (Claude) | $5-10 |
| HeyReach subscription | $79-99/mo |
| **Total** | **~$140-196** |

## Performance Benchmarks

| Metric | Target | Notes |
|--------|--------|-------|
| ICP match rate | ≥80% | Test scrape verification |
| Email enrichment rate | 40-70% | Depends on data quality |
| Connection acceptance | 20-40% | With personalization |
| Reply rate | 5-15% | Interested prospects |
| Pipeline time (500 leads) | 20-30 min | All phases |

## Message Templates

See `templates/` for examples:
- `default_connection_request.txt` - Generic B2B
- `hvac_outreach.txt` - For service businesses
- `saas_founder_outreach.txt` - For SaaS founders

Template variables:
- `{{first_name}}` - Lead's first name
- `{{company_name}}` - Lead's company
- `{{personalized_line}}` - AI-generated opener

## Troubleshooting

### PhantomBuster Issues

**Error: "LinkedIn session expired"**
- Solution: Get new `li_at` cookie and update `.env`

**Error: "Phantom timed out"**
- Solution: Reduce `--max_items` or split into smaller batches

### Low ICP Match Rate (<80%)

**Problem**: Test scrape returns wrong leads
- Solution: Refine Sales Navigator filters:
  - Adjust "Job Titles" (be more specific)
  - Narrow "Industry" (exclude adjacent industries)
  - Adjust "Company Size" range
  - Add "Seniority Level" filters

### Low Email Enrichment Rate (<40%)

**Problem**: Most emails not found
- Causes:
  - Wrong company names
  - Missing company domains
  - Incomplete LinkedIn profiles
- Solutions:
  - Try Apollo.io (better for US leads)
  - Manually verify company names are correct
  - Extract company domains from LinkedIn company pages

### Generic Personalization

**Problem**: AI generates lines like "I came across your profile..."
- Solution: Adjust prompt template in `generate_personalization.py`
- Add more specific instructions about what to look for
- Sample and review 10-20 before sending to all

### Low Acceptance Rate (<15%)

**Problem**: LinkedIn connections not accepting
- Causes:
  - Generic message
  - Sending too fast (looks like spam)
  - Wrong ICP (not relevant)
- Solutions:
  - Pause campaign
  - Review and improve personalization
  - Reduce daily limit to 30-40
  - Check ICP match (might need to re-verify)

## Best Practices

1. **Always test with 25 leads first** - Don't waste money on bad filters
2. **Verify ICP match ≥80%** before full scrape
3. **Sample personalization** (10-20 lines) before sending to all
4. **Start with 30-50 daily limit** - Scale up if acceptance rate is good
5. **Monitor daily** - Early signals predict campaign success
6. **Two-pass enrichment** - AnyMailFinder first, then Apollo for remaining
7. **A/B test messages** - Try 2-3 variations on small batches
8. **Stay under LinkedIn limits** - 50-100 requests/day max
9. **Update directives** - Document learnings after each campaign

## Support

- See directives for detailed SOPs: `directives/linkedin_sales_nav_pipeline.md`
- Issues? Check troubleshooting section above
- Update `.env` with all required API keys before starting

## Next Steps

After running your first campaign:

1. Monitor metrics daily (acceptance rate, reply rate)
2. Adjust messaging based on feedback
3. Scale to larger volumes (1000+) if results are good
4. Consider multi-channel campaigns (LinkedIn + Email)
5. Update directives with learnings

---

**Built with the 3-layer architecture**: Directives (what) → Orchestration (decisions) → Execution (deterministic scripts)


