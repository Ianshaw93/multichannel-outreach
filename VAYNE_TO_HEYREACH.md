# Vayne → HeyReach Pipeline

Complete pipeline from Vayne profile data to HeyReach campaigns with ICP filtering and AI personalization.

## Overview

**Flow:**
1. Export profiles from Vayne → `.tmp/vayne_profiles.json`
2. **ICP Check** with DeepSeek (filters non-qualifying leads)
3. **Personalize** with GPT-4o (generates 5-line LinkedIn DMs)
4. **Upload** to HeyReach (with personalized messages)

**Why this works:**
- DeepSeek ICP check is **10x cheaper** than GPT-4o ($0.14/1M tokens vs $2.50/1M)
- Only personalize leads that match ICP = massive cost savings
- Only upload qualified leads to HeyReach = higher campaign performance

## Setup

### 1. Get API Keys

Add to `.env`:

```bash
# DeepSeek API (for ICP filtering)
DEEPSEEK_API_KEY=your_key_here

# OpenAI API (for personalization)
OPENAI_API_KEY=your_key_here

# HeyReach API (for campaign upload)
HEYREACH_API_KEY=your_key_here
```

Get keys:
- DeepSeek: https://platform.deepseek.com/api_keys
- OpenAI: https://platform.openai.com/api-keys
- HeyReach: https://app.heyreach.io/settings/integrations

### 2. Export from Vayne

Export your Vayne profiles to `.tmp/vayne_profiles.json`

Expected JSON format:
```json
[
  {
    "full_name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "job_title": "CEO",
    "company": "Acme Inc",
    "location": "San Francisco, CA",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "industry": "SaaS"
  }
]
```

## Usage

### Basic Usage (Default ICP)

Uses built-in ICP for Sales Automation & Personal Branding agency:

```bash
python execution/personalize_and_upload.py \
  --input .tmp/vayne_profiles.json \
  --output .tmp/vayne_profiles_personalized.json \
  --list_id 12345
```

**What happens:**
1. ✅ ICP Check (DeepSeek) - Filters for C-level/founders in B2B high-ticket services
2. ✅ Personalization (GPT-4o) - Generates 5-line LinkedIn DMs for qualifying leads
3. ✅ Upload (HeyReach) - Adds to list with personalized messages

### Custom ICP Criteria

```bash
python execution/personalize_and_upload.py \
  --input .tmp/vayne_profiles.json \
  --output .tmp/vayne_profiles_personalized.json \
  --list_id 12345 \
  --icp_criteria "Marketing Directors at B2B SaaS companies with 50-500 employees"
```

### Skip ICP Check

If you already filtered leads externally:

```bash
python execution/personalize_and_upload.py \
  --input .tmp/vayne_profiles.json \
  --output .tmp/vayne_profiles_personalized.json \
  --list_id 12345 \
  --skip_icp_check
```

### Resume After Personalization

If personalization completed but upload failed:

```bash
python execution/personalize_and_upload.py \
  --output .tmp/vayne_profiles_personalized.json \
  --list_id 12345 \
  --skip_personalization
```

## Default ICP Criteria

**Authority (Strict):**
- ✅ Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, C-Suite
- ❌ Reject: Interns, Students, Junior staff, Administrative assistants, low-level contributors

**Industry (Lenient):**
- ✅ Qualify: High-ticket B2B services (Agencies, SaaS, Consulting, Coaching, Tech)
- 🤔 Benefit of Doubt: When unsure if B2B or decision-maker → Qualify

**Hard Rejections:**
- ❌ Massive traditional banks/financial institutions (e.g., Santander, Getnet)
- ❌ Physical labor or local retail (e.g., Driver, Technician, Cashier)

## Output

### Console Output

```
VAYNE > ICP CHECK > PERSONALIZE > HEYREACH
============================================================
Input: .tmp/vayne_profiles.json
Output: .tmp/vayne_profiles_personalized.json
HeyReach List ID: 12345
ICP Criteria: [Default Sales Automation ICP]
============================================================

STEP 1: ICP filtering with DeepSeek + Personalization with GPT-4o...

  [ICP-REJECT] #3: Sarah Johnson - Junior role in target industry
  [OK] #1: John Smith
  [OK] #2: Mike Davis
  [ICP-REJECT] #5: Carlos Martinez - Works at Santander Bank
  [OK] #4: Emily Chen

============================================================
PERSONALIZATION SUMMARY
============================================================
Total leads: 100
  [ICP-REJECT] Rejected by ICP: 25
  [OK] Personalized: 73
  [FAIL] Failed: 2
  [SKIP] Already done: 0
  [SAVED] Output: .tmp/vayne_profiles_personalized.json
============================================================

STEP 2: Uploading to HeyReach...

  [OK] Uploaded 73/73...

============================================================
UPLOAD SUMMARY
============================================================
Total leads processed: 73
  [OK] Successfully uploaded: 73
  [FAIL] Failed: 0
============================================================

[SUCCESS] Complete flow finished!

Next steps:
  1. Go to HeyReach and verify the leads were added to list 12345
  2. In your campaign message template, use: {personalized_message}
  3. Start the campaign!
```

### Output File Fields

The personalized JSON includes:

```json
{
  "full_name": "John Smith",
  "job_title": "CEO",
  "company": "Acme Inc",
  "location": "San Francisco",
  "linkedin_url": "https://linkedin.com/in/johnsmith",

  "icp_match": true,
  "icp_confidence": "high",
  "icp_reason": "CEO at B2B SaaS company - clear authority and industry fit",

  "personalized_message": "Hey John\n\nAcme Inc looks interesting\n\nYou guys do outbound right? Do that w LinkedIn + email? Or what\n\nOutbound is a tough nut to crack\nReally comes down to precise targeting + personalisation to book clients at a high level\n\nSee you're in San Francisco. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland"
}
```

## Cost Breakdown (per 100 leads)

| Step | Model | Cost |
|------|-------|------|
| ICP Check | DeepSeek Chat | ~$0.01 |
| Personalization (75 qualify) | GPT-4o | ~$1.50 |
| HeyReach Upload | API | Free |
| **Total** | | **~$1.51** |

**Without ICP filtering:** $2.00 (100 leads × GPT-4o)
**With ICP filtering:** $1.51 (saves 25% by not personalizing rejected leads)

*Note: Savings increase with lower ICP match rates*

## Troubleshooting

### DeepSeek API Error

If ICP check fails, script defaults to accepting leads (benefit of doubt):

```
⚠️  Error checking ICP: Connection timeout
```

**Solution:** Check `DEEPSEEK_API_KEY` in `.env` and internet connection

### Personalization Failed

```
⚠️  Error generating personalization: Rate limit exceeded
```

**Solution:** Script uses 10 parallel workers. Reduce by editing `max_workers=5` in script if hitting rate limits.

### HeyReach Upload Failed

```
[ERROR] Error uploading chunk 1: 401 Unauthorized
```

**Solution:** Check `HEYREACH_API_KEY` and verify list ID exists

### Fields Missing in Vayne Export

If Vayne export doesn't have `job_title`, `company`, or `industry`, the script handles it:
- Falls back to `title`, `company_name` fields
- Uses "Unknown" if field missing
- ICP check uses available data (may result in "low confidence")

## Best Practices

1. **Always use ICP check** - Even if you pre-filtered, it's a cheap double-check
2. **Review rejections** - Check `.tmp/vayne_profiles_personalized.json` for `icp_match: false` to see if criteria too strict
3. **Custom ICP for different campaigns** - Use `--icp_criteria` for targeting specific verticals
4. **Test on small batch first** - Run 10-20 leads, verify quality before full batch
5. **Monitor costs** - Check OpenAI usage dashboard after large batches

## Advanced: Custom Personalization Template

To use different message templates, edit `execution/prompts.py` or pass custom template name:

```python
# In prompts.py, add new template
CUSTOM_TEMPLATE = "..."

# In personalize_and_upload.py, import and use it
```

## Integration with HeyReach Campaign

### 1. Create Campaign in HeyReach UI

- Go to HeyReach → New Campaign
- Set up connection request + follow-up sequence
- In message template, use variable: `{personalized_message}`

Example:
```
{personalized_message}

Quick question - would you be open to a chat about streamlining your outbound?

Best,
[Your Name]
```

### 2. Get List ID

- Go to Lists → Your List
- Copy the List ID from URL: `https://app.heyreach.io/lists/12345` → `12345`

### 3. Upload via Script

```bash
python execution/personalize_and_upload.py --list_id 12345 ...
```

### 4. Start Campaign

- Go back to HeyReach → Campaigns
- Click "Start Campaign"
- Monitor performance in real-time

## Summary

**Vayne2HeyReach pipeline automates:**
- ✅ ICP filtering with cheap AI (DeepSeek)
- ✅ Personalization with quality AI (GPT-4o)
- ✅ Upload to HeyReach with custom fields
- ✅ Cost optimization (only personalize qualifying leads)
- ✅ Quality control (strict authority, lenient industry)

**Result:** Higher acceptance rates, lower cost per qualified conversation.
