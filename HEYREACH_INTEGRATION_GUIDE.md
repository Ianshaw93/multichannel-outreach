# HeyReach Integration Guide

## Overview

This guide explains how to integrate HeyReach with your multi-channel outreach system to send **custom, AI-generated messages** to LinkedIn prospects while **tracking all engagement (replies, connections, etc.) on your side** via webhooks.

## Architecture Decision: Hybrid Approach (RECOMMENDED)

**What HeyReach Does:**
- Handles LinkedIn automation safely (rate limits, timing, account safety)
- Sends connection requests and messages with your custom content
- Manages sequences (connection request → follow-up after acceptance → etc.)

**What You Control:**
- ICP filtering and prospect selection
- AI-powered message generation (using Claude API)
- Engagement tracking via webhooks (replies, connections, status changes)
- Multi-channel orchestration (LinkedIn + email + phone)

**Why This Works:**
- You don't reinvent LinkedIn automation (safety, compliance)
- You keep full control over message quality and personalization
- You track everything in your own system (Google Sheets, database, etc.)
- HeyReach is just the execution layer, not the brains

---

## Setup

### 1. Prerequisites

Install required Python packages:
```bash
pip install -r requirements.txt
```

Required packages:
- `anthropic` - For Claude API (message generation)
- `requests` - For HeyReach API calls
- `gspread` - For Google Sheets integration
- `python-dotenv` - For environment variables

### 2. Get API Keys

**HeyReach API Key:**
1. Go to https://app.heyreach.io/settings/integrations
2. Find "API" section
3. Click "Get API Key"
4. Copy and add to `.env`:
   ```
   HEYREACH_API_KEY=your_key_here
   ```

**Anthropic API Key (for AI personalization):**
1. Go to https://console.anthropic.com/
2. Create API key
3. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

### 3. Create Campaign in HeyReach UI

**IMPORTANT:** Create campaigns in the HeyReach UI (not via API) for better control.

1. Go to HeyReach → Campaigns → Create New Campaign
2. Set up your message templates with variables:
   ```
   Hi {firstName},

   {personalized_line}

   I help companies like {companyName} book more qualified meetings through multi-channel outreach.

   Would you be open to a quick chat?

   Best,
   [Your Name]
   ```

3. **Variable Naming Rules:**
   - Use curly braces: `{variable_name}`
   - No spaces (use `_` or `-`)
   - Must EXACTLY match what you send via API
   - Examples: `{personalized_line}`, `{custom_message}`, `{icebreaker}`

4. Set up sequence steps:
   - Step 1: Connection request with note
   - Step 2: Follow-up message (3 days after connection accepted)
   - Step 3: Second follow-up (7 days if no reply)

5. Configure settings:
   - Daily limit: 50-100 (LinkedIn safe limits)
   - Working hours: 9am-5pm in prospect's timezone
   - Random delays: Enabled

6. **Save as DRAFT** (don't activate yet)

7. Note the **List ID** (you'll need this for the API)

---

## Workflow

### Step 1: Pull LinkedIn Profiles

Use your existing scripts to scrape LinkedIn profiles (Sales Navigator, Vayne, etc.)

### Step 2: Filter by ICP

Check prospects against your Ideal Customer Profile criteria.

### Step 3: Generate Custom Messages

Use Claude API to generate personalized messages for each prospect:

```bash
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID" \
  --output_column "personalized_line" \
  --prompt_template "default_linkedin"
```

**What this does:**
- Reads prospects from Google Sheet
- For each prospect, generates a custom opening line using Claude API
- Writes `personalized_line` column back to sheet
- Cost: ~$0.01-0.02 per prospect (using Claude Haiku)

**Available prompt templates:**
- `default_linkedin` - Generic B2B personalization
- `service_business` - For contractors, agencies, local services
- `saas_founder` - For SaaS/tech founders

**Example outputs:**
- "Saw you're scaling the HVAC team at TechCorp - hiring in this market is tough!"
- "Congrats on the Series B - noticed you're expanding into enterprise"
- "Fellow Austin business owner here - love seeing local companies thrive"

### Step 4: Add Leads to HeyReach Campaign

```bash
python3 execution/add_leads_to_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID" \
  --list_id 12345 \
  --custom_fields "personalized_line,custom_message" \
  --update_sheet
```

**Arguments:**
- `--sheet_url`: Your Google Sheet with prospects
- `--list_id`: HeyReach list ID (from Step 3 of setup)
- `--custom_fields`: Comma-separated custom field names from your sheet
- `--update_sheet`: Update sheet with "added_to_heyreach" status

**What this does:**
1. Reads leads from Google Sheet
2. Formats them with `customUserFields` matching your campaign variables
3. Uploads to HeyReach list via API (batch upload, 100 per chunk)
4. Updates Google Sheet with status

**Required sheet columns:**
- `first_name` (or `firstName`)
- `linkedin_url` (or `profileUrl`)

**Optional but recommended:**
- `last_name`, `company_name`, `title`, `email`, `location`
- Any custom fields you want to use in messages

### Step 5: Activate Campaign in HeyReach

1. Go to HeyReach → Campaigns
2. Find your campaign
3. Verify leads were added
4. Click "Activate"

HeyReach will now send messages according to your sequence and daily limits.

---

## Tracking Engagement (Webhooks)

To track replies, connections, and engagement on your side:

### Available Webhook Events

- `connection_request_sent` - When connection request is sent
- `connection_request_accepted` - When prospect accepts
- `message_sent` - When message is sent
- `message_reply_received` - When prospect replies (first reply)
- `every_message_reply_received` - All subsequent replies
- `status_tag_updated` - When lead status changes

### Setup Webhooks

1. **Create webhook endpoint** (using Modal, Zapier, Make, or custom server)
2. **Configure in HeyReach:**
   - Go to Settings → Integrations → Webhooks
   - Click "Create Webhook"
   - Add your webhook URL
   - Select events to track

3. **Handle webhook payload:**

Example payload for `connection_request_accepted`:
```json
{
  "event": "connection_request_accepted",
  "lead": {
    "firstName": "John",
    "lastName": "Doe",
    "profileUrl": "https://linkedin.com/in/johndoe",
    "customUserFields": [
      {"name": "personalized_line", "value": "Saw you're scaling..."}
    ]
  },
  "campaign": {
    "id": 12345,
    "name": "Q1 Outreach"
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

4. **Update your Google Sheet** or database with engagement data

---

## API Details

### Authentication

```python
headers = {
    "X-API-KEY": HEYREACH_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}
```

### Rate Limits

- 300 requests/minute
- Plan batching accordingly (script uploads in chunks of 100)

### Add Leads Endpoint

```
POST https://api.heyreach.io/api/v1/lists/{list_id}/leads
```

**Payload:**
```json
{
  "leads": [
    {
      "firstName": "John",
      "lastName": "Doe",
      "profileUrl": "https://www.linkedin.com/in/johndoe",
      "companyName": "TechCorp",
      "position": "VP of Sales",
      "emailAddress": "john@techcorp.com",
      "location": "Austin, TX",
      "customUserFields": [
        {
          "name": "personalized_line",
          "value": "Saw you're scaling the HVAC team at TechCorp..."
        },
        {
          "name": "custom_message",
          "value": "I help companies like yours book 40% more meetings..."
        }
      ]
    }
  ],
  "listId": 12345
}
```

### Important Requirements

1. **Variable names must EXACTLY match:**
   - API: `customUserFields.name = "personalized_line"`
   - Campaign template: `{personalized_line}`
   - NO spaces allowed (use `_` or `-`)

2. **Campaign must be ACTIVE:**
   - Drafts cannot receive leads via API
   - Activate in HeyReach UI first

3. **LinkedIn URL is required:**
   - `profileUrl` field must be valid LinkedIn profile URL

---

## Example: Full End-to-End Flow

```bash
# 1. Generate personalized messages
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/ABC123" \
  --output_column "personalized_line" \
  --prompt_template "saas_founder"

# 2. Add leads to HeyReach campaign
python3 execution/add_leads_to_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/ABC123" \
  --list_id 12345 \
  --custom_fields "personalized_line" \
  --update_sheet

# 3. Activate campaign in HeyReach UI

# 4. Track engagement via webhooks (set up in HeyReach)
```

---

## Files Reference

**Scripts:**
- `execution/generate_personalization.py` - Generate custom messages with Claude API
- `execution/add_leads_to_heyreach.py` - Add leads to HeyReach list (RECOMMENDED)
- `execution/linkedin_outreach_heyreach.py` - Legacy script (creates campaigns via API)

**Templates:**
- `templates/heyreach_connection_request_example.txt` - Example connection request
- `templates/heyreach_follow_up_example.txt` - Example follow-up message

**Directives:**
- `directives/linkedin_outreach_personalization.md` - Full SOP

---

## Troubleshooting

### "API key invalid"
- Check `.env` has correct `HEYREACH_API_KEY`
- Verify key is active in HeyReach → Settings → Integrations

### "Campaign not found" or "List not found"
- Make sure campaign is ACTIVE (not draft)
- Verify list ID is correct (find in HeyReach UI)

### Variables not populating in messages
- Check variable names EXACTLY match between API and campaign template
- No spaces allowed (use `_` or `-`)
- Variables are case-sensitive: `{firstName}` ≠ `{firstname}`

### Low acceptance rates
- Improve personalization quality (review generated messages)
- Reduce daily limit (50-100 is safe, >100 risks LinkedIn restrictions)
- Check targeting (are you reaching the right audience?)

### Leads not being added
- Check required fields: `firstName`, `profileUrl` must exist
- Verify LinkedIn URLs are valid
- Check API response for error messages

---

## Cost Breakdown (per 100 leads)

| Item | Cost |
|------|------|
| Claude API (personalization) | $1-2 |
| HeyReach subscription | $79-99/month |
| LinkedIn Sales Navigator | $79-99/month |
| **Total per lead** | **~$1.50-2.50** |

---

## Best Practices

1. **Always personalize** - Generic messages get ignored
2. **Test with small batches** - Send to 10-20 prospects first, review results
3. **Monitor daily** - Check acceptance rates, reply rates, adjust as needed
4. **A/B test messages** - Try different personalizations on small cohorts
5. **Respect LinkedIn limits** - 50-100 requests/day max
6. **Use webhooks** - Track engagement on your side for multi-channel orchestration
7. **Keep messages short** - Under 300 characters for connection requests
8. **Timing matters** - Tuesday-Thursday, 9am-11am in prospect's timezone

---

## Next Steps

1. Set up API keys in `.env`
2. Create campaign in HeyReach UI with variables
3. Test with 10-20 prospects from your sheet
4. Review acceptance rates and message quality
5. Scale to full list
6. Set up webhooks for engagement tracking
7. Build multi-channel flows (LinkedIn → email → phone)
