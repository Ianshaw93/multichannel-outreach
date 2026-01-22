# LinkedIn Sales Navigator Lead Scraping & Verification

## Goal
Scrape LinkedIn profiles from a Sales Navigator search URL using PhantomBuster, verify they match your ICP criteria (e.g., "80% must be decision-makers in HVAC industry"), and auto-adjust filters if match rate is too low. Save verified leads to Google Sheets for enrichment.

## Inputs
- **Sales Navigator URL**: The LinkedIn Sales Navigator search URL containing your target filters
- **ICP Criteria**: Description of your Ideal Customer Profile (e.g., "Decision-makers in HVAC companies with 10-50 employees")
- **Match Threshold**: Minimum % of leads that must match ICP (default: 80%)
- **Total Count**: Number of leads desired (default: 100)

## Tools/Scripts
- Script: `execution/scrape_linkedin_phantombuster.py` (PhantomBuster API integration)
- Script: `execution/verify_linkedin_leads.py` (LLM-based ICP verification)
- Script: `execution/update_sheet.py` (save to Google Sheets)
- Dependencies: PhantomBuster API key, Anthropic API key, Google credentials

## Process

### 1. Test Scrape (25 leads)
```bash
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "https://www.linkedin.com/sales/search/..." \
  --max_items 25 \
  --output .tmp/test_linkedin_leads.json
```

**What it does:**
- Uses PhantomBuster's "Sales Navigator Search Export" phantom
- Extracts: name, title, company, location, profile URL, current position, experience
- Saves to `.tmp/test_linkedin_leads.json`

### 2. ICP Verification
```bash
python3 execution/verify_linkedin_leads.py \
  --input .tmp/test_linkedin_leads.json \
  --icp_criteria "Decision-makers (CEO, Owner, VP) in HVAC companies" \
  --output .tmp/verified_leads.json
```

**What it does:**
- Uses Claude to analyze each lead's title, company, and experience
- Classifies as: `match`, `maybe`, or `no_match`
- Calculates match rate (match + maybe / total)
- Outputs verification report with stats

**Decision Logic:**
- **Match Rate ≥ 80%**: ✅ Proceed to full scrape
- **Match Rate 60-79%**: ⚠️ Ask user if they want to adjust filters or proceed
- **Match Rate < 60%**: ❌ Stop and refine Sales Navigator search filters

### 3. Auto-Adjustment (if match rate < 80%)
If verification fails, the agent (you) should:
1. Analyze the mismatches (wrong titles, wrong industries, wrong company sizes)
2. Suggest specific Sales Navigator filter adjustments:
   - Adjust "Job Titles" field
   - Adjust "Industry" filters
   - Adjust "Company Size" range
   - Adjust "Seniority Level"
3. Ask user to update the Sales Navigator URL with new filters
4. Re-run test scrape with updated URL

### 4. Full Scrape (if verified)
```bash
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "https://www.linkedin.com/sales/search/..." \
  --max_items 500 \
  --output .tmp/linkedin_leads_full.json
```

**Cost**: ~$0.01-0.02 per lead with PhantomBuster

### 5. Upload to Google Sheets (DELIVERABLE)
```bash
python3 execution/update_sheet.py \
  --input .tmp/linkedin_leads_full.json \
  --sheet_name "LinkedIn Leads - [Industry] - [Date]"
```

**Output**: Google Sheet URL with columns:
- `full_name`, `first_name`, `last_name`
- `title`, `company_name`, `company_domain`
- `linkedin_url`, `location`
- `email` (empty, to be enriched in Phase 2)
- `icp_match` (match/maybe/no_match)
- `icp_reason` (why they match/don't match)

## Outputs (Deliverables)
- **Intermediate**: `.tmp/test_linkedin_leads.json`, `.tmp/verified_leads.json` (for verification)
- **Final Deliverable**: Google Sheet URL with verified LinkedIn leads

## Edge Cases
- **PhantomBuster rate limits**: Phantom might take 10-30 mins for large scrapes (500+ leads)
- **LinkedIn connection required**: PhantomBuster requires a LinkedIn account with Sales Navigator access
- **Expired session**: PhantomBuster needs valid LinkedIn session cookies (must re-authenticate periodically)
- **Low match rate**: If <60%, agent must guide user to refine filters before proceeding

## Dependencies in .env
```
PHANTOMBUSTER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

## Learnings
- Sales Navigator URLs contain all filter state - no need to manually specify filters
- PhantomBuster's "Sales Navigator Search Export" phantom is the most reliable for this
- LLM verification (Claude Haiku) costs ~$0.002 per lead, very cheap for quality filtering
- Common mismatch reasons: wrong seniority level, adjacent industries, generic job titles
- Always test with 25 leads first - saves money if filters are wrong
- Session cookies expire after ~30 days, need periodic re-authentication with PhantomBuster











