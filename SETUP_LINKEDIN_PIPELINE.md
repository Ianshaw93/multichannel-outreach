# LinkedIn Pipeline Setup Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

All required packages are already in `requirements.txt`:
- `anthropic` - For Claude AI (ICP verification, personalization)
- `requests`, `httpx` - For API calls
- `gspread`, `google-auth` - For Google Sheets integration
- `beautifulsoup4` - For web scraping (optional)
- `python-dotenv` - For environment variables

## Step 2: Get API Keys

You need the following API keys and credentials:

### 1. PhantomBuster (for LinkedIn scraping)

**Sign up**: https://phantombuster.com/pricing
- **Recommended plan**: $56/month (for 500-1000 leads/month)
- **Get API key**: Dashboard → Settings → API Key

### 2. LinkedIn Session Cookie (for PhantomBuster)

PhantomBuster needs your LinkedIn session to scrape Sales Navigator.

**How to get it**:
1. Log in to LinkedIn in your browser
2. Open DevTools (F12) → Application tab → Cookies
3. Find `li_at` cookie for `.linkedin.com`
4. Copy the **entire value** (long alphanumeric string)

**Important**: This cookie expires every ~30 days. You'll need to update it periodically.

### 3. Anthropic Claude (for AI verification & personalization)

**Sign up**: https://console.anthropic.com/
- **Get API key**: Account Settings → API Keys → Create Key
- **Cost**: ~$2-5 per 1000 leads (Haiku model)

### 4. AnyMailFinder (for email enrichment)

**Sign up**: https://anymailfinder.com/pricing
- **Recommended plan**: Pay-as-you-go ($0.10-0.15 per email found)
- **Get API key**: Dashboard → API → Create Key

**Alternative**: Apollo.io (better match rates for US leads)
- **Sign up**: https://apollo.io/
- **Get API key**: Settings → Integrations → API

### 5. HeyReach (for LinkedIn outreach)

**Sign up**: https://heyreach.io/pricing
- **Recommended plan**: $79/month per seat
- **Get API key**: Settings → API Access → Generate Key

**Alternative**: Use PhantomBuster's "Send LinkedIn Invitations" phantom (included in your plan)

### 6. Google Sheets API (for storing leads)

**Setup**:
1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable "Google Sheets API" and "Google Drive API"
4. Create OAuth credentials:
   - Create OAuth 2.0 Client ID
   - Application type: "Desktop app"
   - Download JSON and save as `credentials.json` in project root

**Or use Service Account** (for automation):
1. Create Service Account
2. Download JSON and save as `service_account.json`
3. Set `GOOGLE_APPLICATION_CREDENTIALS=service_account.json` in `.env`

## Step 3: Create .env File

Create a file named `.env` in the project root with the following content:

```bash
# PhantomBuster (for LinkedIn scraping)
PHANTOMBUSTER_API_KEY=your_phantombuster_key_here
LINKEDIN_SESSION_COOKIE=your_li_at_cookie_value_here

# Anthropic Claude (for AI verification & personalization)
ANTHROPIC_API_KEY=your_anthropic_key_here

# AnyMailFinder (for email enrichment)
ANYMAILFINDER_API_KEY=your_anymailfinder_key_here

# Apollo.io (alternative email enrichment - optional)
APOLLO_API_KEY=your_apollo_key_here

# HeyReach (for LinkedIn outreach - optional)
HEYREACH_API_KEY=your_heyreach_key_here

# Google Sheets & Drive
GOOGLE_APPLICATION_CREDENTIALS=credentials.json

# OpenAI (alternative to Claude - optional)
OPENAI_API_KEY=your_openai_key_here
```

**Important**: Never commit `.env` to git! It should be in `.gitignore`.

## Step 4: Test Setup

Test each component individually:

### Test Google Sheets Auth

```bash
python3 execution/read_sheet.py "https://docs.google.com/spreadsheets/d/YOUR_TEST_SHEET"
```

If this fails:
- Check `credentials.json` exists
- Run through OAuth flow in browser
- Verify `token.json` was created

### Test PhantomBuster Connection

```bash
python3 -c "
import os
from dotenv import load_dotenv
import requests

load_dotenv()
api_key = os.getenv('PHANTOMBUSTER_API_KEY')
response = requests.get('https://api.phantombuster.com/api/v2/agents/fetch-all', 
                       headers={'X-Phantombuster-Key': api_key})
print('Status:', response.status_code)
print('Response:', response.json() if response.ok else response.text)
"
```

Expected: Status 200 and list of agents (or empty list if none exist)

### Test Anthropic Claude

```bash
python3 -c "
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
response = client.messages.create(
    model='claude-3-haiku-20240307',
    max_tokens=100,
    messages=[{'role': 'user', 'content': 'Say hello'}]
)
print('Claude says:', response.content[0].text)
"
```

Expected: Claude responds with a greeting

### Test AnyMailFinder

```bash
python3 -c "
import os
from dotenv import load_dotenv
import requests

load_dotenv()
api_key = os.getenv('ANYMAILFINDER_API_KEY')
response = requests.get('https://api.anymailfinder.com/v5.1/account', 
                       headers={'Authorization': api_key})
print('Status:', response.status_code)
print('Credits:', response.json().get('credits') if response.ok else response.text)
"
```

Expected: Status 200 and your account credit balance

## Step 5: Create Test Sales Navigator Search

Before running the pipeline, create a test search in LinkedIn Sales Navigator:

1. Go to https://www.linkedin.com/sales/search/people
2. Set filters:
   - **Location**: Your target location (e.g., "United States", "Austin, TX")
   - **Industry**: Your target industry (e.g., "HVAC", "SaaS")
   - **Job Titles**: Decision-maker titles (e.g., "CEO", "Owner", "Founder", "VP")
   - **Company Size**: Your target size (e.g., "11-50 employees")
3. Review results - do they look like your ICP?
4. Copy the **full URL** from the address bar

The URL should look like:
```
https://www.linkedin.com/sales/search/people?query=(filters:List((type:INDUSTRY,values:List((id:...)))))...
```

**Important**: This URL contains all your filter state. Don't modify it manually.

## Step 6: Run Test Scrape

Now run a small test scrape (25 leads) to verify everything works:

```bash
python3 execution/scrape_linkedin_phantombuster.py \
  --sales_nav_url "YOUR_SALES_NAV_URL" \
  --max_items 25 \
  --output .tmp/test_leads.json
```

**Expected output**:
- "Agent launched!" message
- Progress updates every 30 seconds
- "Scrape completed successfully!" 
- JSON file saved to `.tmp/test_leads.json`

**Common issues**:
- **"LinkedIn session expired"**: Update `LINKEDIN_SESSION_COOKIE` in `.env`
- **"Phantom failed"**: Check PhantomBuster dashboard for error details
- **"Rate limited"**: Wait 5-10 minutes and try again

## Step 7: Verify ICP Match

```bash
python3 execution/verify_linkedin_leads.py \
  --input .tmp/test_leads.json \
  --icp_criteria "Decision-makers (CEO, Owner, VP) in HVAC companies with 10-50 employees" \
  --output .tmp/verified.json
```

**Expected output**:
- Per-lead verification results (✅ match, ❓ maybe, ❌ no match)
- Match rate percentage
- Decision: PASS (≥80%), WARNING (60-79%), or FAIL (<60%)

**If match rate is <80%**:
- Adjust Sales Navigator filters
- Be more specific with job titles
- Narrow industry selection
- Run test scrape again

## Step 8: You're Ready!

If all tests pass, you're ready to run the full pipeline. See `README_LINKEDIN_PIPELINE.md` for complete usage instructions.

## Troubleshooting

### "ModuleNotFoundError: No module named 'X'"

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### "ANTHROPIC_API_KEY not found in .env"

**Solution**: Check your `.env` file
- Make sure it's named `.env` exactly (not `.env.txt`)
- Verify API keys have no extra spaces or quotes
- Reload: `python-dotenv` loads `.env` automatically

### "Error opening sheet: Permission denied"

**Solution**: Share the Google Sheet with your service account email
- Open Google Sheet
- Click "Share"
- Add the email from `service_account.json` (the `client_email` field)
- Give "Editor" access

### PhantomBuster scrape takes too long

**Expected**: 5-30 minutes for large scrapes (500+ leads)
- PhantomBuster must visit each profile page
- LinkedIn rate limits slow this down
- For faster results, reduce `--max_items`

### AnyMailFinder not finding emails

**Causes**:
- Wrong company names
- Missing company domains
- Profiles are outdated

**Solutions**:
- Try Apollo.io (better for US leads)
- Verify company names in LinkedIn
- Consider manual verification for high-value leads

## Cost Summary (Monthly)

For running **2000 leads/month** (typical mid-size campaign):

| Service | Plan | Cost |
|---------|------|------|
| PhantomBuster | Standard | $56/mo |
| Anthropic Claude | Pay-as-you-go | $8-15/mo |
| AnyMailFinder | Pay-as-you-go | $200-300 (per email) |
| HeyReach | Professional | $79-99/mo |
| LinkedIn Sales Nav | Core | $79/mo |
| Google Sheets | Free | $0 |
| **Total** | | **~$422-549/mo** |

**Cost per lead**: ~$0.21-0.27 (all-in)

## Next Steps

- Read `README_LINKEDIN_PIPELINE.md` for full pipeline usage
- Check `directives/` folder for detailed SOPs
- Run your first small campaign (100 leads)
- Monitor and optimize based on results

## Support

- **Issues with setup?** Check troubleshooting section above
- **Issues with a specific tool?** See that tool's directive in `directives/`
- **Need to adjust the workflow?** Update the relevant directive and execution script

---

**Remember**: This is a self-annealing system. When you encounter issues, fix the scripts and update the directives with learnings.



We'd need to use the rest of their profile as well. 







