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
- Script: `execution/generate_personalization.py` (AI personalization agent)
- Script: `execution/linkedin_outreach_heyreach.py` (send via HeyReach)
- Script: `execution/linkedin_outreach_phantombuster.py` (alternative: send via PhantomBuster)
- Dependencies: Anthropic API key, HeyReach or PhantomBuster API key

## Process

### Step 1: Generate Personalized First Lines

Before sending any messages, use Claude to analyze each prospect's LinkedIn profile and generate a personalized opening line.

```bash
python3 execution/generate_personalization.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --output_column "personalized_line" \
  --prompt_template "default_linkedin"
```

**What it does:**
1. Reads leads from Google Sheet (columns: `full_name`, `title`, `company_name`, `linkedin_url`)
2. For each lead, scrapes their LinkedIn profile (headline, about, recent posts)
3. Uses Claude to generate a personalized first line based on:
   - Their role/title
   - Their company/industry
   - Recent activity (posts, job changes)
   - Mutual interests or pain points
4. Writes `personalized_line` back to sheet

**Example outputs:**
- "Saw you recently expanded your HVAC team in Austin - congrats on the growth!"
- "Noticed you've been posting about technician retention challenges..."
- "Fellow Austin business owner here - loved your thoughts on service quality"

**Prompt templates available:**
- `default_linkedin`: Generic B2B personalization
- `service_business`: For contractors, agencies, local services
- `saas_founder`: For SaaS/tech founders
- `custom`: Provide your own prompt file

**Performance:**
- ~100 leads in 3-4 minutes
- Cost: ~$0.01-0.02 per personalization (Claude Haiku)
- Quality: High (avoids generic AI slop by using real profile data)

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

```bash
python3 execution/linkedin_outreach_heyreach.py \
  --sheet_url "https://docs.google.com/spreadsheets/d/..." \
  --campaign_name "HVAC Owners - Q1 2025" \
  --message_template message_template.txt \
  --type connection_request \
  --daily_limit 50
```

**What it does:**
1. Creates a new campaign in HeyReach
2. Uploads leads with personalized messages
3. Sets sending schedule (e.g., 50 per day, random delays)
4. Monitors campaign status and reports results

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
ANTHROPIC_API_KEY=your_key_here
HEYREACH_API_KEY=your_key_here
PHANTOMBUSTER_API_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
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


