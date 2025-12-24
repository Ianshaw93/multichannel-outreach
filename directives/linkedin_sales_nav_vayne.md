# LinkedIn Sales Navigator Scraping with Vayne.io

## Goal
Extract LinkedIn profile data from Sales Navigator search URLs using Vayne.io API. Input a Sales Navigator URL and get a list of enriched profile information ready for downstream processing.

## Inputs
- **Sales Navigator URL**: The LinkedIn Sales Navigator search URL containing target filters
- **Max Results**: Number of profiles to extract (default: 20, max: 10,000 per request)
- **Export Format**: Simple or Advanced (default: Advanced for maximum data)

## Tools/Scripts
- Script: `execution/scrape_linkedin_vayne.py` (Vayne.io API integration)
- Dependencies: Vayne.io API key (Bearer token)

## Process

### 1. Single API Call Scraping
```bash
python3 execution/scrape_linkedin_vayne.py \
  --sales_nav_url "https://www.linkedin.com/sales/search/..." \
  --max_results 20 \
  --output .tmp/vayne_profiles.json
```

**What it does:**
- Creates scraping order via Vayne.io API
- Polls order status until completion
- Downloads enriched profile data
- Saves structured JSON output

### 2. Output Processing
The script outputs a list of LinkedIn profiles with:
- Full name, first name, last name
- Current job title and company
- LinkedIn profile URL
- Location and other profile data
- Company information (size, industry, etc.)

## Outputs
- **Intermediate**: `.tmp/vayne_profiles.json` - Raw profile data from Vayne.io
- **Deliverable**: Structured list of profiles ready for enrichment/outreach

## API Integration Details

**Authentication:**
- Bearer token authentication
- Token generated in Vayne.io dashboard "API Settings"

**Endpoints:**
- POST /orders - Create scraping order
- GET /orders/{id} - Check order status
- GET /orders/{id}/download - Download results

**Rate Limits:**
- Up to 10,000 profiles per single request
- Up to 100,000 profiles per month (plan dependent)
- Automatic segmentation for large orders

## Advantages over PhantomBuster
- No LinkedIn session management required
- Higher volume limits (10k vs 2.5k per day)
- More reliable (built-in anti-detection)
- Real-time scraping vs database lookups
- Simpler API integration

## Edge Cases
- **Large orders**: Automatically segmented by Vayne.io for LinkedIn safety
- **API credits**: Each successful order consumes credits from plan
- **Order failures**: API returns specific error messages for debugging
- **Webhook notifications**: Optional webhook for order completion (async processing)

## Dependencies in .env
```
VAYNE_API_KEY=your_bearer_token_here
```

## Cost Structure
- Credit-based pricing model
- Free tier: 200 lead exports per month
- Paid plans: Higher volume limits
- No per-request charges beyond credit consumption

## Learnings
- Vayne.io handles LinkedIn's anti-scraping automatically
- No need for session cookie management
- Real-time scraping ensures fresh data
- API is more reliable than browser automation
- Supports much larger volumes than traditional scrapers