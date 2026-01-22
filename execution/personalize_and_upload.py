#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete flow: Vayne JSON → ICP Check (DeepSeek) → Personalize → Upload to HeyReach
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
from prompts import get_linkedin_5_line_prompt

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HEYREACH_API_BASE = "https://api.heyreach.io/api/public"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

def check_icp_match(lead, icp_criteria=None):
    """
    Check if lead matches ICP using DeepSeek (cheap and fast).
    Returns dict with 'match' (bool), 'confidence' (str), and 'reason' (str).

    Uses default ICP for Sales Automation and Personal Branding agency if not specified.
    """
    if not DEEPSEEK_API_KEY:
        print("  ⚠️  Warning: DEEPSEEK_API_KEY not found, skipping ICP check")
        return {"match": True, "confidence": "skipped", "reason": "No API key"}

    lead_summary = f"""
Lead: {lead.get('full_name', 'Unknown')}
Title: {lead.get('job_title', lead.get('title', 'Unknown'))}
Company: {lead.get('company', lead.get('company_name', 'Unknown'))}
Location: {lead.get('location', 'Unknown')}
Industry: {lead.get('industry', 'N/A')}
"""

    # Use custom ICP criteria if provided, otherwise use default for Sales Automation agency
    if not icp_criteria:
        system_prompt = """Role: B2B Lead Qualification Filter.

Objective: Categorize LinkedIn profiles based on Authority and Industry fit for a Sales Automation and Personal Branding agency.

Rules for Authority (Strict):
- Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, and C-Suite executives.
- Reject: Interns, Students, Junior staff, Administrative assistants (e.g., "Assessor administrativo"), and low-level individual contributors.

Rules for B2B Industry (Lenient):
- Qualify: High-ticket service industries (Agencies, SaaS, Consulting, Coaching, Tech).

The "Benefit of Doubt" Rule: If you are unsure if a business is B2B or B2C, or unsure if the person is a top-level decision-maker, Qualify them (Set to true). Only reject if they are clearly non-decision makers or in non-business roles.

Hard Rejections:
- Leads from massive traditional Banking/Financial institutions (e.g., Santander, Getnet).
- Physical labor or local retail roles (e.g., Driver, Technician, Cashier).

You are an expert at evaluating sales leads. Always respond with valid JSON."""
        user_prompt = f"""Evaluate this LinkedIn profile:

{lead_summary}

Respond in JSON format:
{{
  "match": true/false,
  "confidence": "high" | "medium" | "low",
  "reason": "Brief explanation (1 sentence)"
}}"""
    else:
        # Custom ICP criteria provided
        system_prompt = "You are an expert at evaluating sales leads against ICP criteria. Always respond with valid JSON."
        user_prompt = f"""You are verifying if a LinkedIn lead matches the Ideal Customer Profile (ICP).

ICP Criteria: {icp_criteria}

Lead Information:
{lead_summary}

Task: Determine if this lead matches the ICP.

Respond in JSON format:
{{
  "match": true/false,
  "confidence": "high" | "medium" | "low",
  "reason": "Brief explanation (1 sentence)"
}}"""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        result_text = data["choices"][0]["message"]["content"]
        result = json.loads(result_text)
        return result

    except Exception as e:
        print(f"  ⚠️  Error checking ICP: {e}")
        # Default to accepting if API fails (benefit of doubt)
        return {"match": True, "confidence": "error", "reason": str(e)}

def get_personalization_prompt():
    """
    DEPRECATED: Use prompts.get_linkedin_5_line_prompt() instead.
    This function kept for backwards compatibility.
    """
    from prompts import LINKEDIN_5_LINE_DM_PROMPT
    return LINKEDIN_5_LINE_DM_PROMPT

def generate_personalization(lead):
    """Generate a personalized 5-line LinkedIn DM using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        print("  ⚠️  Error: DEEPSEEK_API_KEY not found in .env")
        return None

    # Extract first name
    full_name = lead.get("full_name", lead.get("first_name", ""))
    first_name = full_name.split()[0] if full_name else ""

    # Get location (extract city if full location)
    location = lead.get("location", "")
    if "," in location:
        location = location.split(",")[0].strip()

    # Get formatted prompt from central source (now includes headline + company description)
    prompt = get_linkedin_5_line_prompt(
        first_name=first_name,
        company_name=lead.get("company", lead.get("company_name", "")),
        title=lead.get("job_title", lead.get("title", "")),
        headline=lead.get("headline", ""),
        company_description=lead.get("company_description", ""),
        location=location
    )

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400,
            "temperature": 0.7
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        linkedin_message = data["choices"][0]["message"]["content"].strip()

        # Clean up
        if linkedin_message.startswith('"') and linkedin_message.endswith('"'):
            linkedin_message = linkedin_message[1:-1]
        linkedin_message = linkedin_message.replace("```", "").strip()

        return linkedin_message

    except Exception as e:
        print(f"  ⚠️  Error generating personalization: {e}")
        return None

def personalize_leads(input_file, output_file, icp_criteria=None, skip_icp_check=False):
    """Generate personalized messages for all leads, with optional ICP filtering."""
    # Load leads
    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    print(f"\nFound {len(leads)} leads to process\n")

    # Process leads in parallel
    personalized_leads = []
    success_count = 0
    failed_count = 0
    icp_rejected_count = 0

    def process_lead(idx_and_lead):
        idx, lead = idx_and_lead

        # Skip if already has personalization
        if lead.get("personalized_message"):
            print(f"  [SKIP] #{idx+1}: Already personalized, skipping")
            return lead, "skipped"

        # Step 1: ICP Check (if not skipped)
        if not skip_icp_check:
            icp_result = check_icp_match(lead, icp_criteria)
            lead["icp_match"] = icp_result.get("match", True)
            lead["icp_confidence"] = icp_result.get("confidence", "unknown")
            lead["icp_reason"] = icp_result.get("reason", "")

            if not icp_result.get("match", True):
                print(f"  [ICP-REJECT] #{idx+1}: {lead.get('full_name', 'Unknown')} - {icp_result.get('reason', '')}")
                return lead, "icp_rejected"

        # Step 2: Generate personalization (only if ICP passed)
        personalized_line = generate_personalization(lead)

        if personalized_line:
            print(f"  [OK] #{idx+1}: {lead.get('full_name', 'Unknown')}")
            lead["personalized_message"] = personalized_line
            return lead, "success"
        else:
            print(f"  [FAIL] #{idx+1}: Failed for {lead.get('full_name', 'Unknown')}")
            return lead, "failed"

    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_lead, (idx, lead)): idx for idx, lead in enumerate(leads)}

        for future in as_completed(futures):
            result, status = future.result()
            personalized_leads.append(result)

            if status == "success":
                success_count += 1
            elif status == "failed":
                failed_count += 1
            elif status == "icp_rejected":
                icp_rejected_count += 1

    # Sort back to original order
    personalized_leads.sort(key=lambda x: leads.index(x))

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(personalized_leads, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"PERSONALIZATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total leads: {len(leads)}")
    if not skip_icp_check:
        print(f"  [ICP-REJECT] Rejected by ICP: {icp_rejected_count}")
    print(f"  [OK] Personalized: {success_count}")
    print(f"  [FAIL] Failed: {failed_count}")
    print(f"  [SKIP] Already done: {len(leads) - success_count - failed_count - icp_rejected_count}")
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
        description="Complete flow: Vayne JSON → ICP Check → Personalize → Upload to HeyReach"
    )
    parser.add_argument("--input", default=".tmp/vayne_profiles.json",
                       help="Input JSON file with Vayne profiles")
    parser.add_argument("--output", default=".tmp/vayne_profiles_personalized.json",
                       help="Output JSON file with personalized messages")
    parser.add_argument("--list_id", type=int, default=471112,
                       help="HeyReach list ID to upload to (default: 471112)")
    parser.add_argument("--icp_criteria",
                       help="ICP criteria for filtering (e.g. 'Founders and C-level execs in B2B SaaS companies')")
    parser.add_argument("--skip_icp_check", action="store_true",
                       help="Skip ICP filtering step")
    parser.add_argument("--skip_personalization", action="store_true",
                       help="Skip personalization step (use existing output file)")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"VAYNE > ICP CHECK > PERSONALIZE > HEYREACH")
    print(f"{'='*60}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"HeyReach List ID: {args.list_id}")
    if not args.skip_icp_check:
        if args.icp_criteria:
            print(f"ICP Criteria: {args.icp_criteria}")
        else:
            print(f"ICP Criteria: Default (Sales Automation & Personal Branding)")
    else:
        print(f"ICP Check: SKIPPED")
    print(f"{'='*60}\n")

    # Step 1: ICP Check + Personalize (unless skipped)
    if not args.skip_personalization:
        if not args.skip_icp_check:
            icp_desc = f"custom ICP: {args.icp_criteria}" if args.icp_criteria else "default Sales Automation ICP"
            print(f"STEP 1: ICP filtering ({icp_desc}) + Personalization with GPT-4o...\n")
        else:
            print("STEP 1: Generating personalized 5-line LinkedIn DMs (ICP check skipped)...\n")

        personalized_leads = personalize_leads(
            args.input,
            args.output,
            icp_criteria=args.icp_criteria,
            skip_icp_check=args.skip_icp_check
        )
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
