# LinkedIn Intent Signal System (Gojiberry-Style)

Find warm leads using real-time intent signals - monitor keyword engagement, competitor posts, and influencer content to identify prospects showing buying intent.

## Overview

This system implements **3 intent signals** inspired by Gojiberry AI:

| Signal | What It Monitors | Why It Works |
|--------|------------------|--------------|
| **Keyword Engagement** | Posts containing pain point keywords ("struggling with outbound") | People expressing pain = buying intent |
| **Competitor Monitoring** | Posts FROM specific competitor accounts | People engaging with competitors are evaluating solutions |
| **Influencer Engagement** | Posts FROM industry thought leaders | People following influencers are interested in your niche |

**Key Difference from Generic Scraping:**
- ❌ OLD: Generic keyword search for "ceos" = random people
- ✅ NEW: Monitor specific accounts + pain points = warm leads with intent

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   3 INTENT SIGNAL MONITORS                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Keyword Monitor → Pain point keywords                    │
│  2. Competitor Monitor → Specific competitor accounts         │
│  3. Influencer Monitor → Specific thought leader accounts     │
│                                                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │  JSON Output Files    │
           │  (.tmp/ directory)    │
           └──────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   Manual Review        │
          │   (Edit JSON file)     │
          │   Set approved: true   │
          └──────────┬────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  json_to_heyreach.py  │
          │  Upload approved leads │
          └──────────┬────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   HeyReach   │
              │   Campaign   │
              └──────────────┘
```

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

### Python Dependencies

All already in `requirements.txt`:
```bash
pip install apify-client anthropic requests python-dotenv
```

## Signal 1: Keyword Engagement Monitor

**What it does:** Finds posts containing pain point keywords and scrapes who engaged.

### Configuration

Edit `config/keyword_signals.json`:

```json
{
  "keywords": [
    "struggling with LinkedIn outreach",
    "struggling with outbound",
    "tired of cold email",
    "cold email not working",
    "low reply rate",
    "need qualified leads"
  ],
  "min_reactions": 50,
  "days_back": 7,
  "countries": ["United States", "Canada"]
}
```

### Usage

```bash
# Test with single keyword
python execution/keyword_engagement_monitor.py \
  --keywords "struggling with outbound" \
  --dry_run

# Use config file
python execution/keyword_engagement_monitor.py \
  --config config/keyword_signals.json \
  --dry_run

# Upload directly to HeyReach (skip manual review)
python execution/keyword_engagement_monitor.py \
  --config config/keyword_signals.json \
  --list_id 480247
```

### Output

Creates `.tmp/keyword_engagement_{timestamp}.json` with leads containing:

```json
{
  "firstName": "Sarah",
  "lastName": "Johnson",
  "linkedinUrl": "https://linkedin.com/in/sarahjohnson",
  "companyName": "TechCorp",
  "jobTitle": "VP of Sales",
  "personalized_message": "Hey Sarah\n\nTechCorp looks interesting...",
  "trigger_source": "keyword_engagement",
  "trigger_date": "2026-01-21",
  "trigger_url": "https://linkedin.com/posts/abc123",
  "approved": false,
  "heyreach_uploaded_at": null
}
```

## Signal 2: Competitor Monitor

**What it does:** Monitors posts FROM specific competitor accounts and scrapes who engages.

### Configuration

Edit `config/competitors.json`:

```json
{
  "competitors": [
    {
      "name": "HeyReach Founder",
      "linkedin_url": "https://linkedin.com/in/example",
      "company": "HeyReach",
      "notes": "Direct competitor in LinkedIn automation"
    },
    {
      "name": "Instantly CEO",
      "linkedin_url": "https://linkedin.com/in/example2",
      "company": "Instantly",
      "notes": "Cold email platform expanding to LinkedIn"
    }
  ]
}
```

### Usage

**IMPORTANT:** Currently requires manually providing post URLs. Automated profile post scraping not yet implemented.

```bash
# Provide specific post URLs from competitor
python execution/competitor_monitor.py \
  --competitor_name "HeyReach Founder" \
  --post_urls "https://linkedin.com/posts/abc123" "https://linkedin.com/posts/def456" \
  --dry_run

# Use config file (still need to provide posts manually for now)
python execution/competitor_monitor.py \
  --config config/competitors.json \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run
```

**How to get post URLs manually:**
1. Go to competitor's LinkedIn profile
2. Find their recent posts (last 24-48 hours)
3. Click "..." → "Copy link to post"
4. Paste URLs in command

### Output

Creates `.tmp/competitor_monitor_{timestamp}.json` with:

```json
{
  "firstName": "John",
  "trigger_source": "competitor_monitoring",
  "trigger_detail": "Engaged with HeyReach Founder's post",
  "competitor_name": "HeyReach Founder",
  "competitor_url": "https://linkedin.com/in/example",
  "approved": false
}
```

## Signal 3: Influencer Monitor

**What it does:** Monitors posts FROM industry influencers and scrapes who engages.

### Configuration

Edit `config/influencers.json`:

```json
{
  "influencers": [
    {
      "name": "Alex Hormozi",
      "linkedin_url": "https://linkedin.com/in/alexhormozi",
      "niche": "Scaling agencies & businesses"
    },
    {
      "name": "Dan Martell",
      "linkedin_url": "https://linkedin.com/in/danmartell",
      "niche": "SaaS coaching & growth"
    }
  ]
}
```

### Usage

Same as competitor monitor - requires manual post URLs:

```bash
# Monitor specific influencer's posts
python execution/influencer_monitor.py \
  --influencer_name "Alex Hormozi" \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run

# Use config file
python execution/influencer_monitor.py \
  --config config/influencers.json \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run
```

### Output

Creates `.tmp/influencer_monitor_{timestamp}.json` with:

```json
{
  "firstName": "Mike",
  "trigger_source": "influencer_engagement",
  "trigger_detail": "Engaged with Alex Hormozi's post",
  "influencer_name": "Alex Hormozi",
  "approved": false
}
```

## Manual Review Workflow

After running any signal monitor:

### Step 1: Review Output JSON

```bash
# Open JSON file in your editor
code .tmp/keyword_engagement_20260121_120000.json

# Or view in terminal
cat .tmp/keyword_engagement_20260121_120000.json | jq '.[] | {name: .fullName, company: .companyName, trigger: .trigger_source}'
```

### Step 2: Approve Leads

Edit the JSON file and set `"approved": true` for leads you want to upload:

```json
{
  "firstName": "Sarah",
  "lastName": "Johnson",
  "approved": true,  // ← Set to true to approve
  "notes": "Great fit - VP at SaaS company"  // ← Optional notes
}
```

### Step 3: Upload to HeyReach

```bash
# Dry run first - preview what will be uploaded
python execution/json_to_heyreach.py \
  --input .tmp/keyword_engagement_20260121_120000.json \
  --dry_run

# Actually upload approved leads
python execution/json_to_heyreach.py \
  --input .tmp/keyword_engagement_20260121_120000.json \
  --list_id 480247

# Upload from multiple files at once
python execution/json_to_heyreach.py \
  --input ".tmp/*_monitor_*.json" \
  --list_id 480247
```

The script will:
- ✅ Only upload leads where `approved: true`
- ✅ Skip leads already uploaded (`heyreach_uploaded_at` is set)
- ✅ Update JSON with upload timestamp
- ✅ Include `personalized_message` as custom field in HeyReach

## Testing Workflow

### Test 1: Keyword Engagement

```bash
# 1. Run with dry_run flag
python execution/keyword_engagement_monitor.py \
  --keywords "struggling with outbound" \
  --days_back 3 \
  --dry_run

# 2. Check output file
ls -la .tmp/keyword_engagement_*.json

# 3. Review leads
cat .tmp/keyword_engagement_*.json | jq '.[0]'

# 4. Approve some leads (edit JSON)

# 5. Upload with dry_run first
python execution/json_to_heyreach.py \
  --input .tmp/keyword_engagement_*.json \
  --dry_run

# 6. Actually upload
python execution/json_to_heyreach.py \
  --input .tmp/keyword_engagement_*.json \
  --list_id 480247
```

### Test 2: Competitor Monitoring

```bash
# 1. Get post URLs from competitor profile manually

# 2. Run monitor
python execution/competitor_monitor.py \
  --competitor_name "Competitor CEO" \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run

# 3. Review, approve, upload (same as above)
```

### Test 3: Influencer Monitoring

```bash
# 1. Get post URLs from influencer profile manually

# 2. Run monitor
python execution/influencer_monitor.py \
  --influencer_name "Alex Hormozi" \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run

# 3. Review, approve, upload (same as above)
```

## Cost Estimates (Per Run)

| Service | Usage | Cost/Run |
|---------|-------|----------|
| Apify (Google Search) | 1 search | ~$0.10 |
| Apify (Post Engagers) | 5 posts | ~$0.25 |
| Apify (Profile Scraper) | 50 profiles | ~$1.00 |
| DeepSeek (ICP Check) | 50 calls | ~$0.01 |
| DeepSeek (Personalization) | 50 calls | ~$0.05 |
| **Total per 50 leads** | | **~$1.41** |

## Troubleshooting

### No engagers found

**Problem:** "Found 0 engagers from post"

**Solution:**
- Check post URL is correct (should be `linkedin.com/posts/...`)
- Verify post has public reactions/comments
- Try a more recent post (last 24-48 hours)

### ICP rejection rate too high

**Problem:** Most leads rejected by ICP filter

**Solution:**
- Review ICP criteria in DeepSeek (modify `keyword_engagement_monitor.py` line ~597)
- Use `--skip_icp` flag to bypass filtering
- Manually review rejected leads in JSON output

### No leads after location filter

**Problem:** All leads filtered out by country

**Solution:**
- Expand countries: `--countries "United States" "Canada" "United Kingdom"`
- Check post engagement is from target regions

### Upload errors

**Problem:** HeyReach upload fails

**Solution:**
- Verify `HEYREACH_API_KEY` in `.env`
- Check list ID exists: https://app.heyreach.io/lists
- Test with `--dry_run` first

## Next Steps

### If Manual Testing Works Well

1. **Build Autopilot Orchestrator** (optional)
   - Runs all 3 signals automatically
   - Daily scheduled runs
   - Accumulates leads for batch review

2. **Set up Scheduling** (optional)
   - Windows Task Scheduler or Modal cron
   - Run daily at 6 AM
   - Review accumulated leads weekly

### Future Enhancements

- [ ] Automated profile post scraping (competitor/influencer monitors)
- [ ] Deduplication across signals (`.tmp/trigger_history.json`)
- [ ] AI lead scoring based on multiple signals
- [ ] Integration with other outreach channels (email, SMS)

## Summary

**You now have 3 manual intent signal monitors:**
1. ✅ Keyword Engagement - Pain point keywords
2. ✅ Competitor Monitoring - Specific competitor accounts
3. ✅ Influencer Monitoring - Thought leader accounts

**Workflow:**
1. Run signal monitor → Outputs JSON
2. Review JSON → Set `approved: true`
3. Upload approved → HeyReach campaign

**Key advantage over generic scraping:**
- Monitoring SPECIFIC accounts + pain points
- Real intent signals vs random prospects
- Gojiberry-style warm lead generation
