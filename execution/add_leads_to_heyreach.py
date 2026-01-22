#!/usr/bin/env python3
"""
Add leads from Google Sheet to an existing HeyReach campaign.
Supports custom message personalization via customUserFields.

Usage:
    python3 add_leads_to_heyreach.py \
        --sheet_url "https://docs.google.com/spreadsheets/d/..." \
        --list_id 12345 \
        --custom_fields "personalized_line,custom_message,icebreaker"
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
import requests
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

# Load environment variables
load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
if not HEYREACH_API_KEY:
    print("Error: HEYREACH_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

HEYREACH_API_BASE = "https://api.heyreach.io/api/v1"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_credentials():
    """Load Google credentials."""
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
                creds = ServiceAccountCredentials.from_service_account_file(service_account_file, scopes=SCOPES)
            elif "installed" in content:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(service_account_file, SCOPES)
                creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

    return creds

def get_list_info(list_id):
    """Get information about a HeyReach list."""
    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/lists/{list_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting list info: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

def add_leads_to_list(list_id, leads, custom_field_names):
    """
    Add leads to HeyReach list with custom personalization fields.

    Args:
        list_id: HeyReach list ID
        leads: List of lead dictionaries from Google Sheet
        custom_field_names: List of custom field names to include from sheet
    """
    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/lists/{list_id}/leads"

    # Format leads for HeyReach API
    formatted_leads = []
    for lead in leads:
        # Build customUserFields as array (HeyReach API format)
        custom_user_fields = []
        for field_name in custom_field_names:
            field_value = lead.get(field_name, "")
            if field_value:
                custom_user_fields.append({
                    "name": field_name,
                    "value": str(field_value)
                })

        # Required fields
        formatted_lead = {
            "firstName": lead.get("first_name", lead.get("firstName", "")),
            "lastName": lead.get("last_name", lead.get("lastName", "")),
            "profileUrl": lead.get("linkedin_url", lead.get("profileUrl", "")),
        }

        # Optional fields
        if lead.get("company_name") or lead.get("companyName"):
            formatted_lead["companyName"] = lead.get("company_name", lead.get("companyName", ""))

        if lead.get("title") or lead.get("position"):
            formatted_lead["position"] = lead.get("title", lead.get("position", ""))

        if lead.get("email") or lead.get("emailAddress"):
            formatted_lead["emailAddress"] = lead.get("email", lead.get("emailAddress", ""))

        if lead.get("location"):
            formatted_lead["location"] = lead.get("location", "")

        if lead.get("about") or lead.get("summary"):
            formatted_lead["summary"] = lead.get("about", lead.get("summary", ""))

        # Add customUserFields array if any
        if custom_user_fields:
            formatted_lead["customUserFields"] = custom_user_fields

        formatted_leads.append(formatted_lead)

    print(f"\nUploading {len(formatted_leads)} leads to HeyReach list {list_id}...")

    # Upload in chunks (HeyReach API may have limits)
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
            print(f"  ✅ Uploaded {total_uploaded}/{len(formatted_leads)}...")

        except Exception as e:
            print(f"  ❌ Error uploading chunk {i//chunk_size + 1}: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response: {e.response.text}")
            failed_count += len(chunk)

    print(f"\n{'='*60}")
    print(f"UPLOAD SUMMARY")
    print(f"{'='*60}")
    print(f"Total leads processed: {len(formatted_leads)}")
    print(f"  ✅ Successfully uploaded: {total_uploaded}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"{'='*60}")

    return total_uploaded

def update_sheet_status(sheet_url, status="added_to_heyreach"):
    """Update Google Sheet with upload status."""
    creds = get_credentials()
    if not creds:
        return False

    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)

        # Add status column if it doesn't exist
        headers = worksheet.row_values(1)
        if "heyreach_status" not in headers:
            worksheet.update_cell(1, len(headers) + 1, "heyreach_status")
            status_col_idx = len(headers) + 1
        else:
            status_col_idx = headers.index("heyreach_status") + 1

        # Update all rows with status
        records = worksheet.get_all_records()
        updates = []

        for idx in range(len(records)):
            row_num = idx + 2
            col_letter = chr(64 + status_col_idx)
            updates.append({
                'range': f"{col_letter}{row_num}",
                'values': [[status]]
            })

        if updates:
            worksheet.spreadsheet.values_batch_update(
                body={
                    'value_input_option': 'RAW',
                    'data': updates
                }
            )

        print(f"✅ Updated sheet with status: {status}")
        return True

    except Exception as e:
        print(f"⚠️  Error updating sheet: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Add leads from Google Sheet to HeyReach list with custom personalization"
    )
    parser.add_argument("--sheet_url", required=True,
                       help="Google Sheet URL with leads")
    parser.add_argument("--list_id", required=True, type=int,
                       help="HeyReach list ID (find in HeyReach UI)")
    parser.add_argument("--custom_fields", default="personalized_message",
                       help="Comma-separated custom field names to include (default: 'personalized_message')")
    parser.add_argument("--update_sheet", action="store_true",
                       help="Update Google Sheet with upload status")

    args = parser.parse_args()

    # Parse custom fields
    custom_field_names = []
    if args.custom_fields:
        custom_field_names = [f.strip() for f in args.custom_fields.split(",")]

    print(f"\n{'='*60}")
    print(f"HeyReach Lead Upload")
    print(f"{'='*60}")
    print(f"List ID: {args.list_id}")
    if custom_field_names:
        print(f"Custom fields: {', '.join(custom_field_names)}")
    print(f"{'='*60}\n")

    # Get list info
    list_info = get_list_info(args.list_id)
    if list_info:
        print(f"✅ Connected to HeyReach list: {list_info.get('name', 'Unknown')}\n")
    else:
        print(f"⚠️  Could not verify list {args.list_id}. Proceeding anyway...")

    # Load leads from sheet
    creds = get_credentials()
    if not creds:
        print("❌ Error: Could not authenticate with Google")
        sys.exit(1)

    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_url(args.sheet_url)
        worksheet = sheet.get_worksheet(0)
        records = worksheet.get_all_records()
    except Exception as e:
        print(f"❌ Error opening sheet: {e}")
        sys.exit(1)

    if not records:
        print("❌ Error: No records found in sheet")
        sys.exit(1)

    print(f"Found {len(records)} leads in sheet\n")

    # Validate required fields
    required_fields = ["first_name", "linkedin_url"]
    sample_record = records[0]

    # Check for alternate field names
    if "firstName" in sample_record and "first_name" not in sample_record:
        required_fields = ["firstName", "profileUrl"]

    missing_fields = [f for f in required_fields if f not in sample_record]

    if missing_fields:
        print(f"❌ Error: Missing required fields: {missing_fields}")
        print(f"Available fields: {list(sample_record.keys())}")
        sys.exit(1)

    # Validate custom fields exist
    if custom_field_names:
        missing_custom = [f for f in custom_field_names if f not in sample_record]
        if missing_custom:
            print(f"⚠️  Warning: Custom fields not found in sheet: {missing_custom}")
            print(f"Available fields: {list(sample_record.keys())}")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != "y":
                sys.exit(0)

    # Upload leads
    uploaded_count = add_leads_to_list(args.list_id, records, custom_field_names)

    if uploaded_count == 0:
        print("\n❌ No leads uploaded. Check error messages above.")
        sys.exit(1)

    # Update sheet if requested
    if args.update_sheet:
        update_sheet_status(args.sheet_url, f"added_to_list_{args.list_id}")

    print(f"\n✅ Success! Uploaded {uploaded_count} leads to HeyReach")
    print(f"\nNext steps:")
    print(f"  1. Go to HeyReach and verify the leads were added")
    print(f"  2. Assign the list to a campaign")
    print(f"  3. Make sure your campaign message uses the custom fields:")
    for field in custom_field_names:
        print(f"     - {{{field}}}")
    print(f"  4. Start the campaign!")

if __name__ == "__main__":
    main()
