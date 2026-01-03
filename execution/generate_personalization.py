#!/usr/bin/env python3
"""
Generate personalized 5-line LinkedIn DMs using ChatGPT 5.2.
Follows strict template rules with authority statements based on industry.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import requests
import httpx
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_credentials():
    """Load Google credentials (reuse from existing scripts)."""
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"Error refreshing token: {e}")
            creds = None

    if not creds:
        service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
        
        if os.path.exists(service_account_file):
            with open(service_account_file, 'r') as f:
                content = json.load(f)
                
            if "type" in content and content["type"] == "service_account":
                print("Using Service Account credentials...")
                creds = ServiceAccountCredentials.from_service_account_file(service_account_file, scopes=SCOPES)
            elif "installed" in content:
                print("Using OAuth 2.0 Client Credentials...")
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(service_account_file, SCOPES)
                creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            
    return creds

def scrape_linkedin_profile_light(linkedin_url):
    """
    Lightweight scrape of LinkedIn profile (public view).
    Note: This only works for public profiles. For full data, use PhantomBuster.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(linkedin_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic info from public profile
        # Note: LinkedIn's HTML structure changes often, this is best-effort
        data = {
            "headline": "",
            "about": "",
            "recent_activity": ""
        }
        
        # Try to find headline
        headline_tag = soup.find("h2", class_="top-card-layout__headline")
        if headline_tag:
            data["headline"] = headline_tag.get_text(strip=True)
        
        return data
        
    except Exception as e:
        print(f"  ⚠️  Could not scrape profile: {e}")
        return None

def get_personalization_prompt(template_name="linkedin_5_line"):
    """
    Get the personalization prompt template for ChatGPT 5.2.
    """
    templates = {
        "linkedin_5_line": """You create **5-line LinkedIn DMs** that feel personal and conversational — balancing business relevance with personal connection and strict template wording.

## TASK
Generate 5 lines:
1. **Greeting** → Hey [FirstName]
2. **Profile hook** → [CompanyName] looks interesting
3. **Business related Inquiry** → You guys do [service] right? Do that w [method]? Or what
4. **Authority building Hook** → 2-line authority statement based on industry (see rules below)
5. **Location Hook** → See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland

---

# PROFILE HOOK TEMPLATE (LINE 2)

Template: [CompanyName] looks interesting

Rules:
● Use their current company name (not past companies)
● Always "looks interesting" (not "sounds interesting" or other variations)
● No exclamation marks
● Keep it casual

Examples:
● War Room looks interesting
● KTM Agency looks interesting
● Immersion Data Solutions looks interesting
● NS Marketing looks interesting

Note: If company name is very long, you can shorten:
● "Immersion Data Solutions" → "IDS looks interesting"
● "The NS Marketing Agency" → "NS Marketing looks interesting"

---

# BUSINESS INQUIRY TEMPLATE (LINE 3)

Template: You guys do [service] right? Do that w [method]? Or what

Rules:
● Infer [service] from their company/title (e.g., "paid ads", "branding", "outbound", "CRM", "analytics")
● Infer [method] based on common methods for that service
● Keep it casual and conversational
● Use "w" instead of "with"

Examples:
● You guys do paid ads right? Do that w Google + Meta? Or what
● You guys do outbound right? Do that w LinkedIn + email? Or what
● You guys do branding right? Do that w design + positioning? Or what

---

# AUTHORITY STATEMENT GENERATION (LINE 4 - 2 LINES)

You MUST follow the exact template, rules, and constraints below. Do not deviate from examples or structure.

Your job is to generate short, punchy authority statements that:
● Sound like a founder talking to another founder
● Contain zero fluff
● Tie everything to business outcomes (revenue, scaling, margins, clients, CAC, downtime, etc.)
● Always follow the 2-line template
● Contain only true statements
● Use simple, natural, conversational language
● Are industry-accurate
● Are 2 lines maximum

## AUTHORITY STATEMENT TEMPLATE (MANDATORY)

**Line 1 — X is Y.**
A simple, universally true industry insight. Examples (do NOT alter these):
● "Ecom is a tough nut to crack."
● "Branding is so powerful."
● "Compliance is a must."
● "Outbound is a tough nut to crack."
● "A streamlined CRM is so valuable."
● "Podcasting is powerful."
● "Analytics is valuable."
● "VA placement is so valuable."

**Line 2 — Business outcome (money / revenue / scaling / clients).**
Tie the idea directly to something founders actually care about. Examples (do NOT alter these):
● "Often comes down to having a brand/offer that's truly different."
● "Without proper tracking you're literally leaving revenue on the table."
● "Great way to build trust at scale with your ideal audience."
● "So downtime saved alone makes it a no-brainer."
● "Nice way to see revenue leaks and double down on what works."
● "Higher margins and faster scaling for companies that use them right."
● "Really comes down to precise targeting + personalisation to book clients at a high level."

## RULES YOU MUST FOLLOW (NON-NEGOTIABLE)

1. The result must always be EXACTLY 2 lines. Never more, never fewer.

2. No fluff. No generic statements. No teaching tone.
Avoid phrases like:
● "helps businesses…"
● "keeps things running smoothly…"
● "boosts adoption fast…"
● "improves efficiency…"
● "keeps listeners engaged…"
● "help manage leads efficiently…"
These are forbidden.

3. No repeating the same idea twice.
Avoid tautologies such as:
● "Inboxes are crowded. Response rates are low."
● "Hiring is tough. Most candidates are similar."
Only one cause per example.

4. Every term MUST be used accurately.
If referencing: CRM, analytics, demand gen, attribution, compliance, margins, downtime, CAC, outbound, SQL/Sales pipeline, etc.
→ You MUST demonstrate correct real-world understanding.
Never misuse terms.

5. "Underrated" may only be used when the thing is ACTUALLY underrated.
Cybersecurity, VAs, branding, and CRM are NOT underrated.
Examples you MUST respect:
● ✔ "VA placement is so valuable."
● ✔ "Cybersecurity is valuable."
● ❌ "VA placement is underrated."
● ❌ "Cybersecurity is underrated."

6. Every final line MUST connect to MONEY.

7. Use the Founder Voice. Read it as if you were DM'ing a sophisticated founder. Short, direct, conversational.

8. Everything must be TRUE. If the industry reality is not obvious, you must adjust the statement to something factual.

---

# LOCATION HOOK TEMPLATE (LINE 5)

Template (word-for-word, only replace [city/region]):
See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland

---

# TEMPLATE INTEGRITY LAW

Templates must be word-for-word.
Only `[placeholders]` may be swapped.
No rephrasing.

---

# OUTPUT FORMAT

Always output 5 lines (Greeting → Profile hook → Business Inquiry → Authority Statement → Location Hook).

Take a new paragraph (blank line) between each line.

Only output the line contents - NOT section labels like "Greeting:" or "Authority Building Hook:". The full message will be sent on LinkedIn as is.

DO NOT include long dashes (---) in the output.

Only return the message - the full reply will be sent on LinkedIn directly.

---

Lead Information:
- First Name: {first_name}
- Company: {company_name}
- Title: {title}
- Location: {location}

Generate the complete 5-line LinkedIn DM now. Return ONLY the message (no explanation, no labels, no formatting).""",
    }

    return templates.get(template_name, templates["linkedin_5_line"])

def generate_personalization(lead, prompt_template):
    """
    Generate a personalized 5-line LinkedIn DM using ChatGPT 5.2.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  ⚠️  Error: OPENAI_API_KEY not found in .env")
        return None

    client = OpenAI(api_key=api_key)

    # Extract first name from full_name
    full_name = lead.get("full_name", lead.get("first_name", ""))
    first_name = full_name.split()[0] if full_name else ""

    # Fill in the prompt template
    prompt = prompt_template.format(
        first_name=first_name,
        title=lead.get("title", ""),
        company_name=lead.get("company_name", ""),
        location=lead.get("location", "")
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # ChatGPT 5.2 (latest GPT-4o model)
            messages=[
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )

        linkedin_message = response.choices[0].message.content.strip()

        # Remove quotes if ChatGPT added them
        if linkedin_message.startswith('"') and linkedin_message.endswith('"'):
            linkedin_message = linkedin_message[1:-1]

        # Remove any triple backticks or markdown formatting
        linkedin_message = linkedin_message.replace("```", "").strip()

        return linkedin_message

    except Exception as e:
        print(f"  ⚠️  Error generating personalization: {e}")
        return None

def personalize_leads(sheet_url, output_column, prompt_template_name):
    """
    Generate personalized lines for all leads in a Google Sheet.
    """
    # Authenticate
    creds = get_credentials()
    if not creds:
        print("Error: Could not authenticate with Google")
        return None
        
    client = gspread.authorize(creds)
    
    # Open the sheet
    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
    except Exception as e:
        print(f"Error opening sheet: {e}")
        return None
    
    # Get all records
    records = worksheet.get_all_records()
    
    if not records:
        print("No records found in sheet")
        return None
    
    print(f"Found {len(records)} leads in sheet")
    
    # Check if output column exists
    headers = worksheet.row_values(1)
    if output_column not in headers:
        # Add the column
        print(f"Adding '{output_column}' column...")
        worksheet.update_cell(1, len(headers) + 1, output_column)
        headers.append(output_column)
        output_col_idx = len(headers)
    else:
        output_col_idx = headers.index(output_column) + 1
    
    # Get prompt template
    prompt_template = get_personalization_prompt(prompt_template_name)
    
    # Generate personalizations
    print(f"\nGenerating personalized lines using '{prompt_template_name}' template...\n")
    
    updates_to_apply = []
    success_count = 0
    failed_count = 0
    
    # Process with limited concurrency (to avoid rate limits)
    def process_lead(idx_and_lead):
        idx, lead = idx_and_lead
        row_num = idx + 2  # +2 because header is row 1 and idx is 0-based
        
        # Skip if already has personalization
        existing_personalization = lead.get(output_column, "").strip()
        if existing_personalization:
            print(f"  ⏭️  Row {row_num}: Already personalized, skipping")
            return None
        
        # Generate personalization
        personalized_line = generate_personalization(lead, prompt_template)
        
        if personalized_line:
            print(f"  ✅ Row {row_num}: {lead['full_name']}")
            print(f"     → \"{personalized_line}\"")
            return {
                'row': row_num,
                'col': output_col_idx,
                'value': personalized_line
            }
        else:
            print(f"  ❌ Row {row_num}: Failed to generate for {lead['full_name']}")
            return None
    
    # Use ThreadPoolExecutor for parallel API calls (max 10 concurrent)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_lead, (idx, lead)): idx for idx, lead in enumerate(records)}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                updates_to_apply.append(result)
                success_count += 1
            else:
                # Check if it was a skip or a failure
                idx = futures[future]
                lead = records[idx]
                if not lead.get(output_column, "").strip():
                    failed_count += 1
    
    # Batch update sheet
    if updates_to_apply:
        print(f"\nBatch updating {len(updates_to_apply)} cells in sheet...")
        
        try:
            batch_data = []
            for update in updates_to_apply:
                col_letter = chr(64 + update['col'])  # A=65, B=66, etc.
                range_notation = f"{col_letter}{update['row']}"
                batch_data.append({
                    'range': range_notation,
                    'values': [[update['value']]]
                })

            worksheet.spreadsheet.values_batch_update(
                body={
                    'value_input_option': 'RAW',
                    'data': batch_data
                }
            )
            print(f"✅ Batch update complete!")
        except Exception as e:
            print(f"Error during batch update: {e}")
            return None
    
    print(f"\n" + "="*60)
    print(f"PERSONALIZATION SUMMARY")
    print(f"="*60)
    print(f"Total leads: {len(records)}")
    print(f"  ✅ Personalized: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  ⏭️  Skipped (already done): {len(records) - success_count - failed_count}")
    print(f"="*60)
    
    # Quality check: Sample 10 random personalizations
    if updates_to_apply:
        print("\n📋 Sample personalizations (quality check):")
        import random
        samples = random.sample(updates_to_apply, min(10, len(updates_to_apply)))
        for sample in samples:
            print(f"  • \"{sample['value']}\"")
        
        print("\n⚠️  Review these samples. If they look too generic, adjust the prompt template and re-run.")
    
    return sheet_url

def main():
    parser = argparse.ArgumentParser(description="Generate personalized 5-line LinkedIn DMs using ChatGPT 5.2")
    parser.add_argument("--sheet_url", required=True, help="Google Sheet URL with leads")
    parser.add_argument("--output_column", default="personalized_message", help="Column name for complete LinkedIn messages")
    parser.add_argument("--prompt_template", default="linkedin_5_line",
                       choices=["linkedin_5_line"],
                       help="Prompt template to use")

    args = parser.parse_args()

    result_url = personalize_leads(args.sheet_url, args.output_column, args.prompt_template)

    if result_url:
        print(f"\n✅ Success! Updated sheet: {result_url}")
    else:
        print("\n❌ Personalization failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()






