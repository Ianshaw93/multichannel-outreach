# Competitor Post Pipeline Directive

Find leads by scraping engagers from competitor LinkedIn posts and adding them to HeyReach campaigns.

## Overview

**Flow (13 steps):**
1. Search Google for LinkedIn posts (e.g., "CEOs", "founders")
2. Filter posts with 50+ reactions
3. Scrape post engagers (who liked/commented)
4. **Headline pre-filter** - reject non-English + clear non-ICP (saves profile scrape costs)
5. Aggregate profile URLs
6. **Early dedup** - check against `processed_leads.json` tracking file
7. Scrape LinkedIn profiles (via Apify) - only unprocessed URLs
8. Filter for US/Canada prospects
9. Filter incomplete profiles
10. ICP qualification (DeepSeek)
11. Generate personalized 5-line LinkedIn DMs (DeepSeek)
12. **Validate messages** - LLM-as-judge scores accuracy, auto-fixes flagged messages
13. Upload to HeyReach + update tracking file

**Cost optimizations:**
- Steps 4 and 6 run BEFORE expensive profile scraping (~$0.025/profile)
- Language detection rejects non-English headlines (likely non-US/Canada)
- Duplicate tracking prevents re-scraping previously processed leads

**Based on:** n8n workflow "Competitor's post flow -> add connection"

## Setup

### Required API Keys

Add to `.env`:

```bash
# Apify (for Google search + LinkedIn scraping)
APIFY_API_TOKEN=your_key_here

# DeepSeek (for ICP filtering + personalization)
DEEPSEEK_API_KEY=your_key_here

# HeyReach (for campaign upload)
HEYREACH_API_KEY=your_key_here
```

Get keys:
- Apify: https://console.apify.com/account/integrations
- DeepSeek: https://platform.deepseek.com/api_keys
- HeyReach: https://app.heyreach.io/settings/integrations

### Apify Actors Used

| Actor | Purpose | Actor ID |
|-------|---------|----------|
| Google Search Scraper | Find LinkedIn posts | `nFJndFXA5zjCTuudP` |
| LinkedIn Post Reactions | Get post engagers | `J9UfswnR3Kae4O6vm` |
| LinkedIn Profile Scraper | Scrape profiles | `dev_fusion~Linkedin-Profile-Scraper` |

## Usage

### Basic Usage

```bash
python execution/competitor_post_pipeline.py --keywords "ceos" --list_id 480247
```

### Full Options

```bash
python execution/competitor_post_pipeline.py \
  --keywords "founders" \
  --days_back 14 \
  --min_reactions 100 \
  --countries "United States" "Canada" \
  --list_id 480247 \
  --dry_run
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--keywords` | `"ceos"` | Search keywords for LinkedIn posts |
| `--days_back` | `7` | Days to look back for posts |
| `--min_reactions` | `50` | Minimum reactions threshold |
| `--countries` | `["United States", "Canada"]` | Allowed countries |
| `--list_id` | `480247` | HeyReach list ID |
| `--dry_run` | `False` | Skip HeyReach upload |
| `--skip_validation` | `False` | Skip message validation/auto-fix |

## Pipeline Steps

### Step 1: Google Search

Searches Google for LinkedIn posts matching keywords from the last N days.

**Query format:**
```
site:linkedin.com/posts "ceos" after:2026-01-07
```

**Output:** List of post URLs with engagement metrics.

### Step 2: Filter by Reactions

Filters posts to keep only those with 50+ reactions (configurable).

**Regex pattern (from n8n):**
```regex
^([5-9][0-9]|[1-9][0-9]{2,})\+ reactions
```

### Step 3: Scrape Post Engagers

Uses Apify to get all users who reacted to the filtered posts.

**Output:** List of engager data including profile URLs and headlines.

### Step 4: Headline Pre-Filter (Cost Optimization)

Filters engagers by headline BEFORE the expensive profile scrape to reduce Apify costs.

**Two-stage filter:**
1. **Language detection** - rejects non-English headlines (likely non-US/Canada)
2. **Keyword rejection** - rejects clear non-ICP roles

**Language detection:**
- High non-ASCII ratio (>15%) → rejected
- CJK characters (Chinese/Japanese/Korean) → rejected
- Cyrillic characters (Russian) → rejected
- Arabic characters → rejected
- Common non-English words (diretor, gerente, fundador, directeur, geschäftsführer, etc.) → rejected

**Keyword rejection:** intern, student, trainee, cashier, driver, technician, nurse, teacher, professor, doctor, retired, unemployed, "looking for", "seeking", "open to work"

**Estimated savings:** ~$0.025 per rejected engager (profile scrape cost avoided)

### Step 5: Aggregate Profile URLs

Collects and deduplicates profile URLs from engagers.

### Step 6: Early Duplicate Check (Cost Optimization)

Checks profile URLs against `processed_leads.json` tracking file BEFORE expensive profile scraping.

**How it works:**
- Loads tracking file with all previously uploaded leads
- Filters out URLs that have already been processed
- Logs removed duplicates and estimated savings

**Tracking file:** `.tmp/processed_leads.json`
- Updated automatically after each successful HeyReach upload
- Contains normalized LinkedIn URLs mapped to metadata (name, date, source, list_id)

**Estimated savings:** ~$0.025 per duplicate removed

### Step 7: Scrape LinkedIn Profiles

Scrapes full profile data for each engager using Apify.

**Wait time:** 2 minutes initial, then polls every 30 seconds.

**Output fields:**
- `firstName`, `lastName`, `fullName`
- `jobTitle`, `headline`
- `companyName`, `companyIndustry`
- `addressCountryOnly`, `addressWithCountry`
- `email`, `linkedinUrl`, `about`

### Step 8: Location Filter

Filters profiles to keep only US and Canada prospects.

**Allowed values:**
- `United States`
- `Canada`
- `USA`
- `America`

### Step 9: Incomplete Profile Filter

Filters out profiles that are too sparse to evaluate.

**Required fields:**
- Headline OR (jobTitle AND companyName)
- At least one experience entry

Profiles missing these fields are rejected to avoid wasting ICP/personalization API calls.

### Step 10: ICP Qualification (DeepSeek)

Uses DeepSeek AI to qualify leads based on ICP criteria.

**Authority (Strict):**
- Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, C-Suite
- Reject: Interns, Students, Junior staff, Administrative assistants

**Industry (Lenient):**
- Qualify: Agencies, SaaS, Consulting, Coaching, Tech
- Benefit of Doubt: When unsure, qualify

**Hard Rejections:**
- Traditional banking (Santander, Getnet, etc.)
- Physical labor/retail roles

### Step 11: Personalization (DeepSeek)

Generates 5-line personalized LinkedIn DMs using DeepSeek.

**Template format:**
```
Hey [FirstName]

[CompanyName] looks interesting

You guys do [service] right? Do that w [method]? Or what

[Industry insight line 1]
[Industry insight line 2]

See you're in [city]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland
```

### Step 12: Validation (LLM-as-Judge)

Uses DeepSeek to validate that personalized messages accurately reflect the prospect's actual service/industry.

**Scoring (1-5 scale):**
- **Service accuracy** - Does "[service]" match what they actually do?
- **Method accuracy** - Is "[method]" realistic for that service?
- **Authority relevance** - Does the authority statement apply to their industry?

**Flags:**
- PASS: avg_score >= 4.0 (uploaded)
- REVIEW: avg_score >= 2.5 < 4.0 (auto-regenerated with correction feedback)
- FAIL: avg_score < 2.5 (auto-regenerated with correction feedback)

Flagged messages are regenerated with correction feedback:
```
You said they do: "{inferred_service}"
They ACTUALLY do: "{actual_service}"
Problem: {reason}
```

### Step 13: HeyReach Upload + Tracking Update

Uploads qualified leads to HeyReach with personalized messages and updates the tracking file.

**Custom field:** `personalized_message`

**After upload:**
- Updates `.tmp/processed_leads.json` with all uploaded leads
- Future runs will skip these leads in Step 6 (early dedup)

## Output

### Console Output

```
============================================================
COMPETITOR POST PIPELINE
============================================================
Keywords: ceos
Days back: 7
Min reactions: 50
Target countries: United States, Canada
HeyReach list ID: 480247
Dry run: False
============================================================

[1/7] Searching Google for LinkedIn posts...
Found 15 search results

[2/7] Filtering posts by reactions...
Filtered to 8 posts with 50+ reactions

[3/7] Scraping post engagers...
Found 245 total engagers

[4/7] Aggregating profile URLs...
Found 198 unique profile URLs

[5/7] Scraping LinkedIn profiles...
Retrieved 198 profiles

[6/7] Filtering by location...
Location filter: 198 -> 142 profiles

[7/7] Qualifying leads (ICP)...
  [OK] #1: Mike Johnson
  [ICP-REJECT] #2: Carlos Garcia - Rejected title: student
  [OK] #3: Sarah Williams
  ...

ICP qualification: 142 -> 89 leads

[8/8] Generating personalized messages...

[9/9] Uploading to HeyReach...
  Uploaded 89/89...

============================================================
PIPELINE SUMMARY
============================================================
  posts_found: 15
  posts_filtered: 8
  engagers_found: 245
  profiles_scraped: 198
  location_filtered: 142
  icp_qualified: 89
  personalized: 89
  uploaded: 89
============================================================
```

### Output File

Saved to `.tmp/competitor_post_leads_{timestamp}.json`:

```json
[
  {
    "firstName": "Mike",
    "lastName": "Johnson",
    "fullName": "Mike Johnson",
    "jobTitle": "CEO",
    "companyName": "TechStartup Inc",
    "companyIndustry": "Software",
    "addressCountryOnly": "United States",
    "linkedinUrl": "https://linkedin.com/in/mikej",
    "email": "mike@techstartup.com",
    "icp_match": true,
    "icp_confidence": "high",
    "icp_reason": "CEO at tech company - clear decision maker",
    "personalized_message": "Hey Mike\n\nTechStartup looks interesting\n\n..."
  }
]
```

## Cost Breakdown (per 100 qualified leads)

| Step | API | Est. Cost | Notes |
|------|-----|-----------|-------|
| Google Search | Apify | ~$0.10 | |
| Post Engagers | Apify | ~$0.50 | |
| **Headline Pre-Filter** | None | **-$X.XX** | Saves ~$0.025 per rejected engager |
| Profile Scraper | Apify | ~$2.00 | Only scrapes pre-filtered leads |
| ICP Check | DeepSeek | ~$0.01 | |
| Personalization | DeepSeek | ~$0.05 | |
| HeyReach Upload | Free | $0 | |
| **Total** | | **~$2.66** | Lower with headline pre-filter |

**Cost optimization:** The headline pre-filter (Step 4) reduces profile scraping costs by rejecting clear non-ICP engagers before the expensive Apify profile scrape. Savings depend on engager quality but typically 20-40% reduction in profile scrape costs.

## Testing

Run tests:
```bash
pytest tests/test_competitor_post_pipeline.py -v
```

All 26 tests should pass:
- Google search query building
- Reaction filtering
- Profile URL aggregation
- Location filtering
- ICP authority checks
- ICP industry checks
- Personalization format
- HeyReach lead formatting
- Pipeline integration

## Troubleshooting

### Apify Rate Limits

If you hit Apify rate limits, wait or increase wait times:

```python
# In competitor_post_pipeline.py
config["scrape_wait_seconds"] = 180  # Increase from 120
config["poll_interval_seconds"] = 45  # Increase from 30
```

### DeepSeek API Errors

If DeepSeek fails, the pipeline falls back to local ICP rules (still functional).

### No Posts Found

Try broader keywords or increase `days_back`:

```bash
python execution/competitor_post_pipeline.py \
  --keywords "startup founders" \
  --days_back 30
```

### Low ICP Match Rate

If too many leads are rejected, the ICP uses "benefit of doubt" by default. You can skip ICP check for manual review:

```bash
# Save profiles without ICP filtering
# Then manually review before upload
```

## Best Practices

1. **Test with dry run first** - Use `--dry_run` to verify results before uploading
2. **Start with narrow keywords** - More specific = higher quality leads
3. **Review ICP rejections** - Check output file for `icp_match: false` leads
4. **Monitor Apify costs** - Profile scraping is the most expensive step
5. **Batch processing** - Run during off-peak hours for better API performance

## Integration with HeyReach Campaign

1. Create campaign in HeyReach UI
2. Use `{personalized_message}` variable in connection request
3. Upload leads via this pipeline
4. Start campaign

Example message template:
```
{personalized_message}

Quick question - would you be open to a chat?
```
