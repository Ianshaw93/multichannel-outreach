#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete flow: Vayne JSON → ICP Check (DeepSeek) → Personalize → Validate → Re-personalize failures → Upload to HeyReach
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
from prompts import get_linkedin_5_line_prompt, LINKEDIN_5_LINE_DM_PROMPT

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

# Placeholder headlines that indicate empty/incomplete profiles
EMPTY_HEADLINE_INDICATORS = ["--", "n/a", "na", "-", ""]


def is_profile_complete(lead):
    """
    Check if a LinkedIn profile has enough data to evaluate.

    Rejects profiles that are too sparse to meaningfully assess against ICP.
    This prevents empty profiles from passing via "benefit of the doubt".

    Args:
        lead: Lead dictionary from LinkedIn scrape

    Returns:
        Dict with 'complete' boolean, 'reason', and 'missing_fields' list
    """
    missing_fields = []

    # Check headline - reject placeholders
    headline = (lead.get("headline") or lead.get("Headline") or "").strip().lower()
    if not headline or headline in EMPTY_HEADLINE_INDICATORS:
        missing_fields.append("headline")

    # Check job title
    job_title = lead.get("jobTitle") or lead.get("job_title") or lead.get("Job Title")
    if not job_title:
        missing_fields.append("jobTitle")

    # Check company name
    company_name = lead.get("companyName") or lead.get("company") or lead.get("Company")
    if not company_name:
        missing_fields.append("companyName")

    # Check experiences count
    exp_count = lead.get("experiencesCount", 0)
    experiences = lead.get("experiences", [])
    if exp_count == 0 and len(experiences) == 0:
        missing_fields.append("experiences")

    # Check profile picture (optional but adds confidence)
    profile_pic = lead.get("profilePic") or lead.get("profilePicHighQuality")
    has_profile_pic = profile_pic is not None

    # Determine if profile is complete enough
    # Require at least headline OR (jobTitle AND companyName)
    has_headline = "headline" not in missing_fields
    has_job_info = "jobTitle" not in missing_fields and "companyName" not in missing_fields
    has_experience = "experiences" not in missing_fields

    # Profile is complete if it has meaningful job info or headline + some experience
    is_complete = has_job_info or (has_headline and has_experience)

    if is_complete:
        reason = "Profile has sufficient data for ICP evaluation"
    else:
        reason = f"Incomplete profile - missing: {', '.join(missing_fields)}"
        if not has_profile_pic:
            reason += " (also no profile picture)"

    return {
        "complete": is_complete,
        "reason": reason,
        "missing_fields": missing_fields,
        "has_profile_pic": has_profile_pic
    }


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
- Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, and C-Suite executives., "Head of Sales/Revenue/Growth
- Reject: "Manager" (without Director/VP), "Head of Product/Engineering/Operations" (not revenue-facing), Interns, Students, Junior staff, Administrative assistants (e.g., "Assessor administrativo"), and low-level individual contributors.

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

VALIDATION_PROMPT = """You are a strict accuracy validator for LinkedIn outreach messages.

Given the INPUT DATA (what we know about this person) and the GENERATED MESSAGE (what we sent them), score the accuracy.

INPUT DATA:
- Full Name: {full_name}
- Headline: {headline}
- Job Title: {job_title}
- Job Description: {job_description}
- Company: {company}
- Company Description: {company_description}
- Company Industry: {company_industry}
- Summary: {summary}

GENERATED MESSAGE:
{personalized_message}

MESSAGE STRUCTURE (5 parts):
1. Greeting: "Hey [Name]"
2. Company hook: "[Company] looks interesting"
3. Service question: "You guys do [service] right? Do that w [method]? Or what"
4. Authority statement: TWO lines about their industry (e.g., "X is powerful / Really comes down to Y")
5. Location hook: Casual/informal paragraph about location - IGNORE THIS for scoring

SCORE EACH (1-5 scale, where 1=completely wrong, 3=partially accurate, 5=spot on):

1. **Service Accuracy**: Does the "[service]" in part 3 accurately reflect what the company does?
2. **Method Accuracy**: Is the "[method]" in part 3 realistic for that service type?
3. **Authority Statement Relevance**: Does the 2-line authority statement (part 4, NOT location hook) apply to their industry?

Return ONLY valid JSON:
{{"service_score": X, "method_score": X, "authority_score": X, "avg_score": X.X, "inferred_service": "what message claims they do", "actual_service": "what they actually do based on data", "flag": "PASS|REVIEW|FAIL", "reason": "1-2 sentence explanation if REVIEW or FAIL"}}

Flag rules:
- PASS: avg_score >= 4.0
- REVIEW: avg_score >= 2.5 and < 4.0
- FAIL: avg_score < 2.5
"""

CORRECTION_PROMPT = """You previously generated a LinkedIn DM that was flagged as inaccurate. Here's what went wrong:

ORIGINAL MESSAGE:
{original_message}

VALIDATION FEEDBACK:
- You said they do: "{inferred_service}"
- They ACTUALLY do: "{actual_service}"
- Problem: {reason}

NOW REGENERATE the message following the EXACT same template rules, but this time get the service/method/authority CORRECT based on the actual data.

{base_prompt}
"""


def validate_single_message(lead: dict) -> dict:
    """Validate a single lead's personalized message using DeepSeek."""
    # Support both snake_case (from sheets) and camelCase (from Apify)
    prompt = VALIDATION_PROMPT.format(
        full_name=lead.get("full_name") or lead.get("fullName") or "",
        headline=lead.get("headline") or "(not available)",
        job_title=lead.get("job_title") or lead.get("jobTitle") or "(not available)",
        job_description=lead.get("job_description") or lead.get("jobDescription") or "(not available)",
        company=lead.get("company") or lead.get("companyName") or "(not available)",
        company_description=lead.get("company_description") or lead.get("companyDescription") or "(not available)",
        company_industry=lead.get("company_industry") or lead.get("companyIndustry") or "(not available)",
        summary=lead.get("summary") or lead.get("about") or "(not available)",
        personalized_message=lead.get("personalized_message") or "(no message)"
    )

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500
        }
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        result_text = response.json()["choices"][0]["message"]["content"].strip()
        # Clean up potential markdown
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        result = json.loads(result_text)
        return result

    except Exception as e:
        return {"flag": "ERROR", "error": str(e)}


def regenerate_with_correction(lead: dict, validation_result: dict) -> str:
    """Regenerate personalized message with correction feedback."""
    # Extract first name (support both snake_case and camelCase)
    full_name = lead.get("full_name") or lead.get("fullName") or lead.get("first_name") or lead.get("firstName") or ""
    first_name = full_name.split()[0] if full_name else ""

    # Get location (extract city if full location) - support camelCase
    location = lead.get("location") or lead.get("addressWithCountry") or lead.get("jobLocation") or ""
    if "," in location:
        location = location.split(",")[0].strip()

    # Get the base prompt with lead info (support both naming conventions)
    base_prompt = get_linkedin_5_line_prompt(
        first_name=first_name,
        company_name=lead.get("company") or lead.get("companyName") or lead.get("company_name") or "",
        title=lead.get("job_title") or lead.get("jobTitle") or lead.get("title") or "",
        headline=lead.get("headline") or "",
        company_description=lead.get("company_description") or lead.get("companyDescription") or "",
        location=location
    )

    # Build correction prompt
    correction_prompt = CORRECTION_PROMPT.format(
        original_message=lead.get("personalized_message", ""),
        inferred_service=validation_result.get("inferred_service", "unknown"),
        actual_service=validation_result.get("actual_service", "unknown"),
        reason=validation_result.get("reason", "inaccurate service/method"),
        base_prompt=base_prompt
    )

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs. You made a mistake before - now correct it based on the feedback."},
                {"role": "user", "content": correction_prompt}
            ],
            "max_tokens": 400,
            "temperature": 0.5  # Lower temp for more accurate regeneration
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
        print(f"  [ERROR] Regeneration failed: {e}")
        return None


def validate_and_fix_batch(leads: list, max_retries: int = 1) -> list:
    """Validate all personalized messages and regenerate failures."""
    print(f"\n{'='*60}")
    print("VALIDATION STEP")
    print(f"{'='*60}")

    leads_to_validate = [l for l in leads if l.get("personalized_message")]
    print(f"Validating {len(leads_to_validate)} personalized messages...")

    validation_results = {}

    # Validate in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(validate_single_message, lead): lead for lead in leads_to_validate}

        for future in as_completed(futures):
            lead = futures[future]
            result = future.result()
            # Support both snake_case (from sheets) and camelCase (from Apify)
            key = lead.get("linkedin_url") or lead.get("linkedinUrl") or lead.get("fullName") or lead.get("full_name")
            validation_results[key] = result

    # Count results
    passes = sum(1 for r in validation_results.values() if r.get("flag") == "PASS")
    reviews = sum(1 for r in validation_results.values() if r.get("flag") == "REVIEW")
    fails = sum(1 for r in validation_results.values() if r.get("flag") == "FAIL")
    errors = sum(1 for r in validation_results.values() if r.get("flag") == "ERROR")

    print(f"\nInitial validation:")
    print(f"  PASS:   {passes} ({100*passes/len(leads_to_validate):.1f}%)")
    print(f"  REVIEW: {reviews} ({100*reviews/len(leads_to_validate):.1f}%)")
    print(f"  FAIL:   {fails} ({100*fails/len(leads_to_validate):.1f}%)")
    print(f"  ERROR:  {errors}")

    # Regenerate FAIL and REVIEW leads
    flagged_leads = []
    for lead in leads_to_validate:
        key = lead.get("linkedin_url") or lead.get("linkedinUrl") or lead.get("fullName") or lead.get("full_name")
        result = validation_results.get(key, {})
        if result.get("flag") in ["FAIL", "REVIEW"]:
            flagged_leads.append((lead, result))

    if flagged_leads:
        print(f"\nRegenerating {len(flagged_leads)} flagged messages with correction feedback...")

        regenerated = 0
        still_failed = 0

        for lead, validation_result in flagged_leads:
            name = lead.get("full_name", "Unknown")
            print(f"  [REGEN] {name}: {validation_result.get('reason', 'no reason')[:60]}...")

            # Store original for comparison
            lead["original_message"] = lead["personalized_message"]
            lead["validation_feedback"] = validation_result

            # Regenerate with correction
            new_message = regenerate_with_correction(lead, validation_result)

            if new_message:
                lead["personalized_message"] = new_message
                lead["regenerated"] = True
                regenerated += 1

                # Re-validate the new message
                new_validation = validate_single_message(lead)
                lead["final_validation"] = new_validation

                if new_validation.get("flag") == "PASS":
                    print(f"    [FIXED] Now passes validation")
                else:
                    print(f"    [STILL-{new_validation.get('flag', 'UNKNOWN')}] {new_validation.get('reason', '')[:50]}")
                    still_failed += 1
            else:
                still_failed += 1

        print(f"\nRegeneration results:")
        print(f"  Fixed: {regenerated - still_failed}")
        print(f"  Still flagged: {still_failed}")

    # Store validation results on leads
    for lead in leads:
        key = lead.get("linkedin_url") or lead.get("linkedinUrl") or lead.get("fullName") or lead.get("full_name")
        if key in validation_results:
            lead["validation"] = validation_results[key]

    return leads


def personalize_leads(input_file, output_file, icp_criteria=None, skip_icp_check=False, skip_validation=False):
    """Generate personalized messages for all leads, with optional ICP filtering and validation."""
    # Load leads
    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    print(f"\nFound {len(leads)} leads to process\n")

    # Process leads in parallel
    personalized_leads = []
    success_count = 0
    failed_count = 0
    icp_rejected_count = 0
    incomplete_count = 0

    def process_lead(idx_and_lead):
        idx, lead = idx_and_lead

        # Skip if already has personalization
        if lead.get("personalized_message"):
            print(f"  [SKIP] #{idx+1}: Already personalized, skipping")
            return lead, "skipped"

        # Step 0: Profile completeness check (always run)
        completeness = is_profile_complete(lead)
        lead["profile_complete"] = completeness["complete"]
        lead["profile_completeness_reason"] = completeness["reason"]

        if not completeness["complete"]:
            print(f"  [INCOMPLETE] #{idx+1}: {lead.get('full_name', lead.get('fullName', 'Unknown'))} - {completeness['reason']}")
            return lead, "incomplete"

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
            elif status == "incomplete":
                incomplete_count += 1

    # Sort back to original order
    personalized_leads.sort(key=lambda x: leads.index(x))

    print(f"\n{'='*60}")
    print(f"PERSONALIZATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total leads: {len(leads)}")
    print(f"  [INCOMPLETE] Missing profile data: {incomplete_count}")
    if not skip_icp_check:
        print(f"  [ICP-REJECT] Rejected by ICP: {icp_rejected_count}")
    print(f"  [OK] Personalized: {success_count}")
    print(f"  [FAIL] Failed: {failed_count}")
    print(f"  [SKIP] Already done: {len(leads) - success_count - failed_count - icp_rejected_count - incomplete_count}")
    print(f"{'='*60}")

    # Step 3: Validate and fix flagged messages
    if not skip_validation:
        personalized_leads = validate_and_fix_batch(personalized_leads)

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(personalized_leads, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] Output: {output_file}")

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
        description="Complete flow: Vayne JSON → ICP Check → Personalize → Validate → Upload to HeyReach"
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
    parser.add_argument("--skip_validation", action="store_true",
                       help="Skip validation and auto-fix step")
    parser.add_argument("--skip_upload", action="store_true",
                       help="Skip HeyReach upload step")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"VAYNE > ICP CHECK > PERSONALIZE > VALIDATE > HEYREACH")
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
    print(f"Validation: {'SKIPPED' if args.skip_validation else 'ENABLED (auto-fix flagged)'}")
    print(f"{'='*60}\n")

    # Step 1: ICP Check + Personalize + Validate (unless skipped)
    if not args.skip_personalization:
        if not args.skip_icp_check:
            icp_desc = f"custom ICP: {args.icp_criteria}" if args.icp_criteria else "default Sales Automation ICP"
            print(f"STEP 1: ICP filtering ({icp_desc}) + Personalization + Validation...\n")
        else:
            print("STEP 1: Generating personalized 5-line LinkedIn DMs (ICP check skipped)...\n")

        personalized_leads = personalize_leads(
            args.input,
            args.output,
            icp_criteria=args.icp_criteria,
            skip_icp_check=args.skip_icp_check,
            skip_validation=args.skip_validation
        )
    else:
        print("STEP 1: Skipping personalization (using existing file)...\n")
        with open(args.output, 'r', encoding='utf-8') as f:
            personalized_leads = json.load(f)

    # Step 2: Upload to HeyReach (unless skipped)
    if not args.skip_upload:
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
    else:
        print("\nSTEP 2: Skipping HeyReach upload")
        print(f"\n[SUCCESS] Personalization complete! Output saved to: {args.output}")

if __name__ == "__main__":
    main()
