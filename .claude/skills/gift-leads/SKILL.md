---
name: gift-leads
description: Run the gift leads pipeline for a prospect. Use when the user wants to find ICP-matched leads from a LinkedIn prospect's network.
argument-hint: [name-or-url] [icp-description]
---

Run the gift leads pipeline with the following inputs:

**Arguments:** $ARGUMENTS

## Step 1: Parse arguments

The first argument is either a **LinkedIn URL** or a **prospect name**. Everything after it is the **ICP description**.

- If it starts with `http` → it's a LinkedIn URL, use it directly
- Otherwise → it's a prospect name. Look up their LinkedIn URL:

```bash
curl -s "https://speedtolead-production.up.railway.app/api/prospects/lookup?name=<name>" | python -m json.tool
```

Extract the `linkedin_url` from the first match. If no match found, tell the user and stop.

## Step 2: Run pipeline

```bash
cd /c/Users/IanShaw/localProgramming/smiths/multichannel-outreach && python execution/gift_leads_list.py --prospect-url "<profile-url>" --icp "<icp-description>" --skip-research
```

## Step 3: Report results

Monitor the output. When complete, report:
- Number of leads found
- Path to the CSV file
- Top 5 leads (name, title, company, activity score)

If the pipeline fails, read the error, fix the issue, and retry (self-anneal). If it fails due to API credits/costs, ask the user before retrying.
