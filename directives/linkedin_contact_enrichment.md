# LinkedIn Lead Contact Enrichment

## Goal
Take verified LinkedIn leads from Phase 1 and enrich them with verified work email addresses using AnyMailFinder or Apollo.io APIs.

## Inputs
- **Google Sheet URL**: Sheet created in Phase 1 (contains LinkedIn profiles without emails)
- **Enrichment Provider**: `anymailfinder` (default, bulk API available) or `apollo` (alternative)

## Tools/Scripts
- Script: `execution/enrich_emails.py` (existing script, already supports bulk API)
- Alternative: `execution/enrich_emails_apollo.py` (if using Apollo.io)
- Dependencies: AnyMailFinder or Apollo API key, Google credentials

## Process

### Using AnyMailFinder (Recommended)

AnyMailFinder has excellent LinkedIn → email enrichment and supports bulk API for large datasets.

```bash
python3 execution/enrich_emails.py "https://docs.google.com/spreadsheets/d/..."
```

**What it does:**
1. Reads all rows from Google Sheet
2. Finds rows with missing emails
3. **Auto-detects strategy:**
   - **200+ rows**: Uses bulk API (creates job, polls until complete, downloads results)
   - **<200 rows**: Uses concurrent API (20 parallel requests)
4. Updates Google Sheet with found emails in-place

**Performance:**
- **Bulk API**: ~1000 emails in 5 minutes (fastest)
- **Concurrent API**: ~100 emails in 2 minutes
- **Cost**: ~$0.10-0.15 per email found

**Match Rate:** Typically 40-70% for LinkedIn profiles (depends on profile completeness)

### Using Apollo.io (Alternative)

Apollo has a LinkedIn URL → email enrichment endpoint and might have higher match rates for US-based leads.

```bash
python3 execution/enrich_emails_apollo.py "https://docs.google.com/spreadsheets/d/..."
```

**What it does:**
1. Reads sheet, extracts `linkedin_url` field
2. Calls Apollo's `people/match` endpoint with LinkedIn URL
3. Updates sheet with found emails + additional data (phone, company info)

**Performance:**
- ~60-80% match rate for US B2B leads
- ~100 requests per minute (API limit)
- **Cost**: ~$0.05-0.10 per email found (cheaper than AnyMailFinder)

## Required Sheet Columns

The script expects these columns from Phase 1:
- `full_name` or (`first_name` + `last_name`)
- `company_name` (required)
- `company_domain` (optional but improves match rate)
- `linkedin_url` (required for Apollo, optional for AnyMailFinder)
- `email` (empty, will be filled)

## Outputs (Deliverables)
- **Updated Google Sheet URL** (same sheet, now with emails filled in)
- **Enrichment Stats** (printed to console):
  - Total rows processed
  - Emails found
  - Not found (%)
  - Cost estimate

## Process Flow

1. **Read Sheet**: Load all rows with missing emails
2. **Choose Strategy**:
   - AnyMailFinder: Auto-selects bulk vs concurrent based on row count
   - Apollo: Always uses concurrent (no bulk API available)
3. **Enrich**: Call API for each row
4. **Batch Update**: Update all found emails in one batch operation (fast)
5. **Report**: Show stats and updated sheet URL

## Edge Cases
- **No company domain**: AnyMailFinder can work with just company name, but match rate drops ~20%
- **Generic emails**: Some leads have generic emails (info@, contact@) - these are returned but may not be decision-maker emails
- **API rate limits**: Both APIs have rate limits (handled with backoff/retry in scripts)
- **LinkedIn URL required**: Apollo requires valid LinkedIn profile URL, AnyMailFinder doesn't
- **Low match rate**: If <40% match rate, data quality may be poor (wrong company names, outdated profiles)

## Cost Optimization

**Recommendation**: Start with AnyMailFinder bulk API (cheapest per email), then fall back to Apollo for unmatchable leads.

**Two-pass enrichment**:
```bash
# Pass 1: AnyMailFinder (bulk, fast, cheap)
python3 execution/enrich_emails.py "https://docs.google.com/spreadsheets/d/..."

# Pass 2: Apollo for remaining missing emails (higher match rate)
python3 execution/enrich_emails_apollo.py "https://docs.google.com/spreadsheets/d/..."
```

This approach maximizes match rate while minimizing cost.

## Dependencies in .env
```
ANYMAILFINDER_API_KEY=your_key_here
APOLLO_API_KEY=your_key_here (if using Apollo)
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

## Learnings
- AnyMailFinder bulk API is 5-10x faster than individual calls for large datasets
- Apollo has better match rates for US B2B but more expensive
- Company domain is the most important field for email enrichment (always try to extract from LinkedIn)
- Some LinkedIn profiles have emails visible on the profile page - consider scraping these first before using APIs
- Generic emails (info@, contact@) are often returned but not useful for direct outreach
- Enrichment should always run in foreground (don't background it) - user needs to see completion before Phase 3







