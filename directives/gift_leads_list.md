# Gift Leads List Pipeline Directive

Generate a "gift leads list" for a prospect — research their ICP, find LinkedIn posts with relevant buying signals, scrape engagers matching that ICP, and output 10+ qualified leads with signal notes.

## Overview

**Value proposition:** Demonstrate competence to a prospect before they become a client by handing them a ready-to-use list of warm leads relevant to their business.

**Flow (12 steps):**
1. Scrape prospect's LinkedIn profile (Apify, cached)
2. Research prospect's business → derive ICP + pain points (DeepSeek)
3. Generate 3-5 Google search queries targeting relevant LinkedIn posts (DeepSeek)
4. Search Google for LinkedIn posts (Apify)
5. Filter posts with 50+ reactions
6. Scrape post engagers (Apify)
7. Pre-filter by headline (language + keyword rejection — cost optimization)
8. Deduplicate + scrape profiles (Apify, cached)
9. Filter: location + profile completeness
10. ICP qualify against prospect's dynamic ICP (DeepSeek)
11. Generate signal notes per lead (DeepSeek)
12. Export JSON + CSV → `.tmp/`

**Key difference from competitor_post_pipeline:** This pipeline uses a *dynamic* ICP derived from the prospect's profile, not a fixed one. The output is a gift deliverable, not a HeyReach upload.

## Setup

### Required API Keys

Same as `competitor_post_pipeline.md`:

```bash
APIFY_API_TOKEN=your_key_here    # Google search + LinkedIn scraping
DEEPSEEK_API_KEY=your_key_here   # Research, queries, ICP, signal notes
```

### Script

```
execution/gift_leads_list.py
```

Imports heavily from `competitor_post_pipeline.py` for shared functions.

## Usage

### Basic Usage

```bash
python execution/gift_leads_list.py \
  --prospect-url "https://linkedin.com/in/johndoe"
```

### Full Options

```bash
python execution/gift_leads_list.py \
  --prospect-url "https://linkedin.com/in/johndoe" \
  --icp "B2B SaaS founders, 10-50 employees" \
  --pain-points "outbound pipeline, lead gen" \
  --days-back 14 \
  --min-reactions 50 \
  --countries "United States" "Canada" \
  --min-leads 10 \
  --max-leads 25 \
  --dry-run
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--prospect-url` | *required* | LinkedIn profile URL of the prospect |
| `--icp` | auto-derived | ICP description override |
| `--pain-points` | auto-derived | Pain points override (comma-separated) |
| `--days-back` | `14` | Days to look back for posts |
| `--min-reactions` | `50` | Minimum reactions threshold |
| `--countries` | `["United States", "Canada"]` | Allowed countries |
| `--min-leads` | `10` | Target minimum leads |
| `--max-leads` | `25` | Maximum leads to return |
| `--dry-run` | `False` | Use cached data only, skip Apify calls |
| `--skip-research` | `False` | Skip research step (requires `--icp`) |

## Pipeline Steps

### Step 1: Scrape Prospect Profile
Uses Apify profile scraper (cached). If prospect is already in `.tmp/profile_cache.json`, skips API call.

### Step 2: Research Prospect's Business
DeepSeek analyzes the prospect's profile and outputs:
- `icp_description` — who their ideal customers are
- `target_titles` — decision-maker titles to look for
- `pain_points` — what problems their customers have
- `buying_signals` — what LinkedIn engagement signals indicate interest
- `search_angles` — different angles for search queries

If `--icp` and/or `--pain-points` are provided, those override the auto-derived values.

### Step 3: Generate Search Queries
DeepSeek generates 3-5 Google search queries in `site:linkedin.com/posts` format, each targeting a different angle (pain points, hiring signals, tool discussions, etc.).

### Steps 4-9: Same as competitor_post_pipeline
Uses shared functions for Google search, reaction filtering, engager scraping, headline pre-filtering, profile scraping, location filtering, and profile completeness checks.

### Step 10: Dynamic ICP Qualification
Uses DeepSeek with the *prospect's dynamic ICP* (not the default agency ICP). Passes `icp_criteria` param to `check_icp_match_deepseek()`.

### Step 11: Signal Notes
DeepSeek generates a 1-line signal note per lead (max 100 chars) explaining:
- What engagement they showed
- Why that makes them relevant to the prospect's ICP

### Step 12: Export
Outputs both JSON and CSV to `.tmp/`:
- `gift_leads_{name}_{timestamp}.json` — full structured output with metadata
- `gift_leads_{name}_{timestamp}.csv` — flat format for sharing

## Output Format

### JSON
```json
{
  "prospect": { "name": "...", "url": "...", "icp": "..." },
  "generated_at": "2026-02-16T12:00:00",
  "lead_count": 14,
  "cost": { "total": 1.45, "breakdown": {...} },
  "leads": [
    {
      "name": "Jane Smith",
      "title": "CEO",
      "company": "GrowthCo",
      "linkedin_url": "https://linkedin.com/in/janesmith",
      "location": "Austin, Texas",
      "signal_note": "Commented on post about scaling SDR teams",
      "source_post_url": "https://linkedin.com/posts/...",
      "engagement_type": "LIKE",
      "icp_confidence": "high",
      "icp_reason": "B2B SaaS founder, 30 employees"
    }
  ]
}
```

### CSV
Same fields, flat format.

## Cost Estimate Per Run

| Step | API | Est. Cost |
|------|-----|-----------|
| Prospect profile | Apify (often cached) | $0.00-0.025 |
| Research + queries | DeepSeek (2 calls) | ~$0.001 |
| Google search | Apify (3-5 queries) | $0.12-0.20 |
| Post reactions | Apify (8-15 posts) | $0.06-0.12 |
| Profile scraping | Apify (40-80 profiles) | $0.50-2.00 |
| ICP checks | DeepSeek (20-50) | $0.006-0.014 |
| Signal notes | DeepSeek (10-25) | $0.001-0.003 |
| **Total** | | **$0.70-$2.40** |

Profile scraping dominates. Cache hits reduce cost significantly on repeat runs.

## Testing

```bash
pytest tests/test_gift_leads_list.py -v
```

Tests cover:
- Prospect profile caching
- Research output parsing
- Search query format validation
- Signal note length (max 100 chars)
- JSON/CSV output structure
- Dynamic ICP passthrough
- CLI argument validation
- Fallback behavior without API keys

## Troubleshooting

### Dry Run Shows No Data
Dry run only uses cached data. Run once without `--dry-run` to populate cache, then subsequent runs can use `--dry-run`.

### Low Lead Count
- Increase `--days-back` (default 14 → try 30)
- Lower `--min-reactions` (default 50 → try 25)
- Broaden ICP with `--icp` override

### DeepSeek API Errors
All DeepSeek calls have fallback behavior — pipeline will continue with basic heuristics.

### Apify Rate Limits
Same as competitor_post_pipeline — increase wait times or stagger queries.
