#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete flow: Vayne JSON → Personalize → Upload to HeyReach
Bypasses Google Sheets entirely for simpler execution.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HEYREACH_API_BASE = "https://api.heyreach.io/api/public"

def get_personalization_prompt():
    """Get the 5-line LinkedIn DM prompt template."""
    return """You create **5-line LinkedIn DMs** that feel personal and conversational — balancing business relevance with personal connection and strict template wording.

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

---

# BUSINESS INQUIRY TEMPLATE (LINE 3)

Template: You guys do [service] right? Do that w [method]? Or what

Rules:
● Infer [service] from their company/title (e.g., "paid ads", "branding", "outbound", "CRM", "analytics")
● Infer [method] based on common methods for that service
● Keep it casual and conversational
● Use "w" instead of "with"

---

# AUTHORITY STATEMENT GENERATION (LINE 4 - 2 LINES)

You MUST follow the exact template, rules, and constraints below.

**Line 1 — X is Y.**
A simple, universally true industry insight.

**Line 2 — Business outcome (money / revenue / scaling / clients).**
Tie the idea directly to something founders actually care about.

## RULES YOU MUST FOLLOW

1. The result must always be EXACTLY 2 lines. Never more, never fewer.
2. No fluff. No generic statements.
3. No repeating the same idea twice.
4. Every term MUST be used accurately.
5. Every final line MUST connect to MONEY.
6. Use Founder Voice. Short, direct, conversational.
7. Everything must be TRUE.

---

# LOCATION HOOK TEMPLATE (LINE 5)

Template (word-for-word, only replace [city/region]):
See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland

---

# OUTPUT FORMAT

Always output 5 lines (Greeting → Profile hook → Business Inquiry → Authority Statement → Location Hook).

Take a new paragraph (blank line) between each line.

Only output the line contents - NOT section labels like "Greeting:". The full message will be sent on LinkedIn as is.

DO NOT include long dashes (---) in the output.

Only return the message - the full reply will be sent on LinkedIn directly.

---

Lead Information:
- First Name: {first_name}
- Company: {company_name}
- Title: {title}
- Location: {location}

Generate the complete 5-line LinkedIn DM now. Return ONLY the message (no explanation, no labels, no formatting)."""

def generate_personalization(lead):
    """Generate a personalized 5-line LinkedIn DM using ChatGPT."""
    if not OPENAI_API_KEY:
        print("  ⚠️  Error: OPENAI_API_KEY not found in .env")
        return None

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Extract first name
    full_name = lead.get("full_name", lead.get("first_name", ""))
    first_name = full_name.split()[0] if full_name else ""

    # Get location (extract city if full location)
    location = lead.get("location", "")
    if "," in location:
        location = location.split(",")[0].strip()

    # Fill in the prompt template
    prompt = get_personalization_prompt().format(
        first_name=first_name,
        title=lead.get("job_title", lead.get("title", "")),
        company_name=lead.get("company", lead.get("company_name", "")),
        location=location
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )

        linkedin_message = response.choices[0].message.content.strip()

        # Clean up
        if linkedin_message.startswith('"') and linkedin_message.endswith('"'):
            linkedin_message = linkedin_message[1:-1]
        linkedin_message = linkedin_message.replace("```", "").strip()

        return linkedin_message

    except Exception as e:
        print(f"  ⚠️  Error generating personalization: {e}")
        return None

def personalize_leads(input_file, output_file):
    """Generate personalized messages for all leads."""
    # Load leads
    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    print(f"\nFound {len(leads)} leads to personalize\n")

    # Process leads in parallel
    personalized_leads = []
    success_count = 0
    failed_count = 0

    def process_lead(idx_and_lead):
        idx, lead = idx_and_lead

        # Skip if already has personalization
        if lead.get("personalized_message"):
            print(f"  [SKIP] #{idx+1}: Already personalized, skipping")
            return lead

        # Generate personalization
        personalized_line = generate_personalization(lead)

        if personalized_line:
            print(f"  [OK] #{idx+1}: {lead.get('full_name', 'Unknown')}")
            lead["personalized_message"] = personalized_line
            return lead
        else:
            print(f"  [FAIL] #{idx+1}: Failed for {lead.get('full_name', 'Unknown')}")
            return lead

    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_lead, (idx, lead)): idx for idx, lead in enumerate(leads)}

        for future in as_completed(futures):
            result = future.result()
            personalized_leads.append(result)
            if result.get("personalized_message"):
                success_count += 1
            else:
                failed_count += 1

    # Sort back to original order
    personalized_leads.sort(key=lambda x: leads.index(x))

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(personalized_leads, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"PERSONALIZATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total leads: {len(leads)}")
    print(f"  [OK] Personalized: {success_count}")
    print(f"  [FAIL] Failed: {failed_count}")
    print(f"  [SAVED] Output: {output_file}")
    print(f"{'='*60}")

    return personalized_leads

def upload_to_heyreach(leads, list_id):
    """Upload leads to HeyReach list with personalized messages."""
    if not HEYREACH_API_KEY:
        print("[ERROR] HEYREACH_API_KEY not found in .env")
        return 0

    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/list/AddLeadsToListV2"

    # Format leads for HeyReach API
    formatted_leads = []
    for lead in leads:
        # Only include leads with personalized messages
        if not lead.get("personalized_message"):
            continue

        formatted_lead = {
            "firstName": lead.get("first_name", ""),
            "lastName": lead.get("last_name", ""),
            "profileUrl": lead.get("linkedin_url", ""),
            "customUserFields": [
                {
                    "name": "personalized_message",
                    "value": lead["personalized_message"]
                }
            ]
        }

        # Add optional fields
        if lead.get("company"):
            formatted_lead["companyName"] = lead["company"]
        if lead.get("job_title"):
            formatted_lead["position"] = lead["job_title"]
        if lead.get("email"):
            formatted_lead["emailAddress"] = lead["email"]
        if lead.get("location"):
            formatted_lead["location"] = lead["location"]

        formatted_leads.append(formatted_lead)

    print(f"\nUploading {len(formatted_leads)} leads to HeyReach list {list_id}...")

    # Upload in chunks
    chunk_size = 100
    total_uploaded = 0
    failed_count = 0

    for i in range(0, len(formatted_leads), chunk_size):
        chunk = formatted_leads[i:i+chunk_size]

        payload = {
            "leads": chunk,
            "listId": list_id
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            total_uploaded += len(chunk)
            print(f"  [OK] Uploaded {total_uploaded}/{len(formatted_leads)}...")

        except Exception as e:
            print(f"  [ERROR] Error uploading chunk {i//chunk_size + 1}: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response: {e.response.text}")
            failed_count += len(chunk)

    print(f"\n{'='*60}")
    print(f"UPLOAD SUMMARY")
    print(f"{'='*60}")
    print(f"Total leads processed: {len(formatted_leads)}")
    print(f"  [OK] Successfully uploaded: {total_uploaded}")
    print(f"  [FAIL] Failed: {failed_count}")
    print(f"{'='*60}")

    return total_uploaded

def main():
    parser = argparse.ArgumentParser(
        description="Complete flow: Vayne JSON → Personalize → Upload to HeyReach"
    )
    parser.add_argument("--input", default=".tmp/vayne_profiles.json",
                       help="Input JSON file with Vayne profiles")
    parser.add_argument("--output", default=".tmp/vayne_profiles_personalized.json",
                       help="Output JSON file with personalized messages")
    parser.add_argument("--list_id", type=int, required=True,
                       help="HeyReach list ID to upload to")
    parser.add_argument("--skip_personalization", action="store_true",
                       help="Skip personalization step (use existing output file)")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"VAYNE > PERSONALIZE > HEYREACH")
    print(f"{'='*60}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"HeyReach List ID: {args.list_id}")
    print(f"{'='*60}\n")

    # Step 1: Personalize (unless skipped)
    if not args.skip_personalization:
        print("STEP 1: Generating personalized 5-line LinkedIn DMs...\n")
        personalized_leads = personalize_leads(args.input, args.output)
    else:
        print("STEP 1: Skipping personalization (using existing file)...\n")
        with open(args.output, 'r', encoding='utf-8') as f:
            personalized_leads = json.load(f)

    # Step 2: Upload to HeyReach
    print("\nSTEP 2: Uploading to HeyReach...\n")
    uploaded_count = upload_to_heyreach(personalized_leads, args.list_id)

    if uploaded_count > 0:
        print(f"\n[SUCCESS] Complete flow finished!")
        print(f"\nNext steps:")
        print(f"  1. Go to HeyReach and verify the leads were added to list {args.list_id}")
        print(f"  2. In your campaign message template, use: {{personalized_message}}")
        print(f"  3. Start the campaign!")
    else:
        print("\n[ERROR] Upload failed. Check error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
