# Competitor Post Pipeline Directive

Find leads by scraping engagers from competitor LinkedIn posts and adding them to HeyReach campaigns.

## Overview

**Flow:**
1. Search Google for LinkedIn posts (e.g., "CEOs", "founders")
2. Filter posts with 50+ reactions
3. Scrape post engagers (who liked/commented)
4. Scrape LinkedIn profiles of engagers (via Apify)
5. Filter for US/Canada prospects
6. ICP qualification (DeepSeek)
7. Generate personalized 5-line LinkedIn DMs (DeepSeek)
8. Upload to HeyReach with personalized messages

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

**Output:** List of profile URLs from reactors.

### Step 4: Scrape LinkedIn Profiles

Scrapes full profile data for each engager using Apify.

**Wait time:** 2 minutes initial, then polls every 30 seconds.

**Output fields:**
- `firstName`, `lastName`, `fullName`
- `jobTitle`, `headline`
- `companyName`, `companyIndustry`
- `addressCountryOnly`, `addressWithCountry`
- `email`, `linkedinUrl`, `about`

### Step 5: Location Filter

Filters profiles to keep only US and Canada prospects.

**Allowed values:**
- `United States`
- `Canada`
- `USA`
- `America`

### Step 6: ICP Qualification (DeepSeek)

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

### Step 7: Personalization (DeepSeek)

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

### Step 8: HeyReach Upload

Uploads qualified leads to HeyReach with personalized messages.

**Custom field:** `personalized_message`

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

## Cost Breakdown (per 100 leads)

| Step | API | Est. Cost |
|------|-----|-----------|
| Google Search | Apify | ~$0.10 |
| Post Engagers | Apify | ~$0.50 |
| Profile Scraper | Apify | ~$2.00 |
| ICP Check | DeepSeek | ~$0.01 |
| Personalization | DeepSeek | ~$0.05 |
| HeyReach Upload | Free | $0 |
| **Total** | | **~$2.66** |

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
