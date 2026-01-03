# LinkedIn Outreach & Personalization

## Goal
Send personalized LinkedIn connection requests and follow-up messages using HeyReach (or PhantomBuster), with AI-generated personalized first lines to avoid "AI slop" and maximize response rates.

## Inputs
- **Google Sheet URL**: Enriched leads from Phase 2 (with emails and LinkedIn URLs)
- **Outreach Campaign Name**: Name for this campaign (e.g., "HVAC Owners - Q1 2025")
- **Message Template**: Your base message with `{{personalized_line}}` placeholder
- **Campaign Type**: `connection_request` or `message` (for existing connections)
- **Outreach Tool**: `heyreach` (recommended) or `phantombuster`

## Tools/Scripts
- Script: `execution/generate_personalization.py` (AI personalization agent - uses ChatGPT 5.2)
- Script: `execution/add_leads_to_heyreach.py` (add leads to existing HeyReach campaign - RECOMMENDED)
- Script: `execution/linkedin_outreach_heyreach.py` (legacy: creates new campaigns via API)
- Script: `execution/linkedin_outreach_phantombuster.py` (alternative: send via PhantomBuster)
- Dependencies: OpenAI API key (ChatGPT 5.2), HeyReach or PhantomBuster API key

## HeyReach API Details

**Authentication:**
- Use `X-API-KEY` header (get API key from HeyReach → Integrations)
- Rate limit: 300 requests/minute

**Recommended Workflow:**
1. Create campaign in HeyReach UI with message templates
2. Use variables in templates: `{custom_message}`, `{personalized_line}`, `{icebreaker}`, etc.
3. Add leads via API with `customUserFields` matching your variable names EXACTLY
4. Track engagement via webhooks

**Available Webhook Events:**
- `connection_request_sent` - When connection request is sent
- `connection_request_accepted` - When prospect accepts connection
- `message_sent` - When message is sent
- `message_reply_received` - When prospect replies (first reply)
- `every_message_reply_received` - Every subsequent reply
- `InMail_sent` / `InMail_reply_received` - InMail tracking
- `status_tag_updated` - When lead status changes

**Custom Field Requirements:**
- Field names must EXACT MATCH between API payload and campaign variables
- No spaces in variable names (use `_` or `-`)
- Good examples: `{AI_Icebreaker_1}`, `{custom_message}`, `{value_prop}`
- Bad examples: `{AI Icebreaker}`, `{custom message}` (spaces break it)

## Process

### Step 1: Generate Personalized 5-Line LinkedIn DMs

Before sending any messages, use ChatGPT 5.2 to generate complete 5-line LinkedIn DMs following strict template rules.

```bash
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --output_column "linkedin_message" \
  --prompt_template "linkedin_5_line"
```

**What it does:**
1. Reads leads from Google Sheet (columns: `first_name`, `company_name`, `location`, `title`)
2. Uses ChatGPT 5.2 to generate a complete 5-line DM:
   - **Line 1:** Hey [FirstName]
   - **Line 2:** [CompanyName] looks interesting
   - **Line 3:** You guys do [service] right? Do that w [method]? Or what
   - **Line 4:** Authority statement (2 lines using strict template - based on industry)
   - **Line 5:** Location hook (Glasgow, Scotland reference)
3. Writes complete `linkedin_message` back to sheet

**Template Integrity:**
- All templates are word-for-word (NO rephrasing allowed)
- Only placeholders like [FirstName], [CompanyName], [service] can be changed
- Authority statements follow exact 2-line format from knowledge base
- Output is ready to send directly on LinkedIn (no section labels, no formatting)

**Example output:**
```
Hey John

KTM Agency looks interesting

You guys do paid ads right? Do that w Google + Meta? Or what

Paid ads is a tough nut to crack
Really comes down to precise targeting + personalisation to book clients at a high level

See you're in Miami. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland
```

**Performance:**
- ~100 leads in 3-4 minutes
- Cost: ~$0.02-0.03 per message (ChatGPT 5.2)
- Quality: High (follows strict template rules, avoids AI slop)

### Step 2: Prepare Message Template

Create your message template with the personalized line placeholder:

```
Hi {{first_name}},

{{personalized_line}}

I help HVAC companies like {{company_name}} [your value prop here].

Would you be open to a quick chat about [specific outcome]?

Best,
[Your Name]
```

**Best practices:**
- Keep it under 300 characters for connection requests (LinkedIn limit)
- Put personalized line at the top (grabs attention)
- Clear, specific value proposition
- Low-friction CTA (just a chat, not a sales call)

### Step 3A: Send via HeyReach (Recommended)

HeyReach is purpose-built for LinkedIn outreach and has better deliverability than PhantomBuster.

**RECOMMENDED APPROACH: Create campaign in HeyReach UI first**

1. **Set up campaign in HeyReach UI:**
   - Create a new campaign with your desired settings
   - Write message templates with variables: `{personalized_line}`, `{custom_message}`, etc.
   - Configure sequence (connection request → follow-up after accepted → etc.)
   - Note the List ID from the campaign

2. **Generate personalized messages:**
   ```bash
   python3 execution/generate_personalization.py \
     --sheet_url "https://docs.google.com/spreadsheets/d/..." \
     --output_column "personalized_line" \
     --prompt_template "default_linkedin"
   ```

3. **Add leads to campaign via API:**
   ```bash
   python3 execution/add_leads_to_heyreach.py \
     --sheet_url "https://docs.google.com/spreadsheets/d/..." \
     --list_id 12345 \
     --custom_fields "personalized_line,custom_message" \
     --update_sheet
   ```

**What it does:**
1. Reads leads from Google Sheet
2. Formats them with customUserFields for personalization
3. Uploads to your HeyReach list via API
4. Updates sheet with status

**ALTERNATIVE: Create campaign via API (legacy script)**
```bash
python3 execution/linkedin_outreach_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --campaign_name "HVAC Owners - Q1 2025" \
  --message_template message_template.txt \
  --type connection_request \
  --daily_limit 50
```
Note: Creating campaigns via UI gives you more control over sequences and settings.

**Features:**
- Smart delays (randomized to avoid LinkedIn detection)
- Auto-follow-up sequences (send message after connection accepted)
- Response tracking (detects replies, pauses outreach)
- A/B testing (test different message variations)

**Limits:**
- 50-100 connection requests per day (LinkedIn safe limit)
- 5-10 second delays between actions
- Campaign runs in background, reports results daily

### Step 3B: Send via PhantomBuster (Alternative)

If you don't have HeyReach, PhantomBuster's "LinkedIn Send Message" or "LinkedIn Send Invitations" phantoms work.

```bash
python3 execution/linkedin_outreach_phantombuster.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --phantom "linkedin-send-invitations" \
  --message_template message_template.txt \
  --daily_limit 50
```

**What it does:**
1. Launches PhantomBuster phantom with your LinkedIn session
2. Sends connection requests or messages with personalized content
3. Tracks sent status in Google Sheet

**Limitations vs HeyReach:**
- No built-in follow-up sequences
- Less sophisticated deliverability features
- Requires manual monitoring of responses
- Higher risk of LinkedIn restrictions

## Outputs (Deliverables)

**Updated Google Sheet** with new columns:
- `personalized_line`: The AI-generated opener
- `outreach_status`: `queued`, `sent`, `accepted`, `replied`, `bounced`
- `sent_at`: Timestamp of when message was sent
- `campaign_id`: HeyReach or PhantomBuster campaign ID

**Campaign Dashboard** (HeyReach only):
- Real-time stats (sent, accepted, replied, bounced)
- Response inbox (see all replies in one place)
- Performance metrics (acceptance rate, reply rate)

## Campaign Monitoring

### Track Performance Daily

```bash
python3 execution/linkedin_campaign_stats.py \
  --campaign_id "hvac_owners_q1_2025" \
  --sheet_url "https://docs.google.com/spreadsheets/d/..."
```

**Metrics to watch:**
- **Acceptance rate**: Target 20-40% (good personalization)
- **Reply rate**: Target 5-15% (interested prospects)
- **Bounce rate**: Keep under 5% (sign of bad data)

### Auto-Pause on Low Performance

If acceptance rate drops below 15%, the agent should:
1. Pause campaign
2. Analyze the rejections/non-responses
3. Suggest message improvements
4. Update personalization prompt
5. Resume with new approach

## Edge Cases

### LinkedIn Account Restrictions
- **Warning signs**: Low acceptance rates, account warnings
- **Solution**: Reduce daily limit to 20-30, increase delays
- **Prevention**: Always use personalization, never spam

### Generic Personalization
- **Problem**: AI generates generic lines like "I saw your profile..."
- **Solution**: Improve prompt to require specific details from profile
- **Test**: Review 10-20 personalized lines before sending to all

### No Email Available
- **Scenario**: Some leads from Phase 2 didn't get emails enriched
- **Options**:
  - Still send LinkedIn messages (doesn't require email)
  - Mark as "LinkedIn-only" campaign
  - Skip leads without emails if multi-channel campaign

### Response Management
- **HeyReach**: Built-in inbox shows all replies
- **PhantomBuster**: Manual checking via LinkedIn
- **Recommendation**: Set up HeyReach webhook to notify you of replies

## Multi-Channel Campaigns (Advanced)

For leads with both LinkedIn and email, run parallel campaigns:

1. **Day 0**: Send LinkedIn connection request (personalized)
2. **Day 3**: If accepted, send LinkedIn follow-up message
3. **Day 7**: If no response, send cold email (different angle)
4. **Day 14**: Final LinkedIn message or cold call

This is implemented in `directives/multichannel_outreach_campaign.md`

## Cost Breakdown (per 100 leads)

| Component | Cost |
|-----------|------|
| Personalization (Claude) | $1-2 |
| HeyReach (per seat/month) | $79-99 |
| PhantomBuster (per month) | $30-60 |
| LinkedIn Sales Nav (required) | $79-99/month |
| **Total per lead** | **~$1.50-2.50** |

## Dependencies in .env
```
OPENAI_API_KEY=your_key_here
HEYREACH_API_KEY=your_key_here
PHANTOMBUSTER_API_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

## Webhook Setup (Optional but Recommended)

To track replies and connections in real-time on your side:

1. **Set up webhook endpoint** (can use Modal, Zapier, Make, or custom server)
2. **Configure in HeyReach:**
   - Go to Settings → Integrations → Webhooks
   - Add webhook URL
   - Select events to track: `connection_request_accepted`, `message_reply_received`
3. **Handle webhook data:**
   - Parse incoming JSON payload
   - Update your Google Sheet or database with engagement status
   - Trigger next steps in your outreach flow

**Example webhook payload (connection accepted):**
```json
{
  "event": "connection_request_accepted",
  "lead": {
    "firstName": "John",
    "lastName": "Doe",
    "profileUrl": "https://linkedin.com/in/johndoe",
    "customUserFields": [
      {"name": "personalized_line", "value": "..."}
    ]
  },
  "campaign": {
    "id": 12345,
    "name": "HVAC Owners Q1"
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## Learnings
- Personalization is THE most important factor for LinkedIn response rates
- Generic AI lines ("I came across your profile...") get ignored
- Specific references to their role, company, or posts perform 3-5x better
- Connection requests with notes have 2x acceptance rate vs no note
- HeyReach's follow-up sequences dramatically improve response rates
- LinkedIn has soft limits (50-100 requests/day) - never exceed them
- Best times to send: Tuesday-Thursday, 9am-11am in recipient's timezone
- A/B test message variations on small batches before scaling
- Always monitor the first 50 sends closely - catch issues early
- Response rate drops significantly after 300 characters (keep it short!)
- **CRITICAL**: Custom field names must EXACTLY match between API and campaign templates
- Creating campaigns in HeyReach UI gives better control than API campaign creation
- Webhooks let you track engagement on your side while HeyReach handles sending
- Use `customUserFields` array in API payload (not `custom_variables`)
- HeyReach API rate limit: 300 requests/minute (plan batching accordingly)
- Only ACTIVE campaigns can receive leads via API (not drafts)







