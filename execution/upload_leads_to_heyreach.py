#!/usr/bin/env python3
"""
Upload leads from JSON file to HeyReach list.
Handles both camelCase and snake_case field names.
"""

import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
HEYREACH_API_BASE = "https://api.heyreach.io/api/public"

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

    # Format leads for HeyReach API - support both camelCase and snake_case
    formatted_leads = []
    for lead in leads:
        # Get personalized message
        msg = lead.get("personalized_message") or lead.get("personalizedMessage")
        if not msg:
            continue

        # Get LinkedIn URL - support multiple field names
        linkedin_url = (
            lead.get("linkedinUrl") or
            lead.get("linkedin_url") or
            lead.get("linkedinPublicUrl") or
            lead.get("profileUrl") or ""
        )

        formatted_lead = {
            "firstName": lead.get("firstName") or lead.get("first_name") or "",
            "lastName": lead.get("lastName") or lead.get("last_name") or "",
            "profileUrl": linkedin_url,
            "customUserFields": [
                {
                    "name": "personalized_message",
                    "value": msg
                }
            ]
        }

        # Add optional fields
        company = lead.get("companyName") or lead.get("company") or ""
        if company:
            formatted_lead["companyName"] = company

        job_title = lead.get("jobTitle") or lead.get("job_title") or ""
        if job_title:
            formatted_lead["position"] = job_title

        email = lead.get("email") or ""
        if email:
            formatted_lead["emailAddress"] = email

        location = lead.get("addressWithoutCountry") or lead.get("location") or lead.get("jobLocation") or ""
        if location:
            formatted_lead["location"] = location

        formatted_leads.append(formatted_lead)

    print(f"\nUploading {len(formatted_leads)} leads to HeyReach list {list_id}...")

    # Upload in chunks
    chunk_size = 100
    total_uploaded = 0
    failed_count = 0

    for i in range(0, len(formatted_leads), chunk_size):
        chunk = formatted_leads[i:i + chunk_size]
        payload = {
            "listId": list_id,
            "leads": chunk
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                added = result.get("addedCount", len(chunk))
                total_uploaded += added
                print(f"  Chunk {i//chunk_size + 1}: {added} leads uploaded")
            else:
                print(f"  Chunk {i//chunk_size + 1} failed: {response.status_code} - {response.text}")
                failed_count += len(chunk)
        except Exception as e:
            print(f"  Chunk {i//chunk_size + 1} error: {e}")
            failed_count += len(chunk)

    print(f"\nUpload complete: {total_uploaded} succeeded, {failed_count} failed")
    return total_uploaded


def main():
    if len(sys.argv) < 3:
        print("Usage: python upload_leads_to_heyreach.py <json_file> <list_id>")
        sys.exit(1)

    json_file = sys.argv[1]
    list_id = int(sys.argv[2])

    # Load leads
    with open(json_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    print(f"Loaded {len(leads)} leads from {json_file}")

    # Upload
    uploaded = upload_to_heyreach(leads, list_id)
    print(f"\nTotal uploaded: {uploaded}")


if __name__ == "__main__":
    main()
