#!/usr/bin/env python3
"""
Send LinkedIn outreach campaigns using HeyReach API.
Supports connection requests and direct messages with personalization.
"""

import os
import sys
import json
import argparse
from datetime import datetime
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

def load_message_template(template_path):
    """Load message template from file."""
    if not os.path.exists(template_path):
        print(f"Error: Template file not found: {template_path}", file=sys.stderr)
        return None
    
    with open(template_path, 'r') as f:
        template = f.read().strip()
    
    return template

def create_campaign(campaign_name, message_template, campaign_type, daily_limit):
    """
    Create a new HeyReach campaign.
    NOTE: It's recommended to create campaigns in the HeyReach UI and use API to add leads.
    """
    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # HeyReach API endpoint for creating campaigns
    url = f"{HEYREACH_API_BASE}/campaigns"
    
    payload = {
        "name": campaign_name,
        "type": campaign_type,  # "connection_request" or "message"
        "daily_limit": daily_limit,
        "message_template": message_template,
        "settings": {
            "random_delays": True,  # Randomize timing to avoid detection
            "delay_min_seconds": 5,
            "delay_max_seconds": 15,
            "working_hours_only": True,  # Only send during business hours
            "timezone": "America/New_York"  # Adjust as needed
        }
    }
    
    print(f"Creating campaign '{campaign_name}'...")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        campaign_id = data.get("id") or data.get("campaign_id")
        print(f"✅ Campaign created: {campaign_id}")
        
        return campaign_id
        
    except Exception as e:
        print(f"Error creating campaign: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

def upload_leads_to_campaign(campaign_id, leads):
    """
    Upload leads to HeyReach campaign.
    """
    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/campaigns/{campaign_id}/leads"

    # Format leads for HeyReach with correct API structure
    formatted_leads = []
    for lead in leads:
        # Build customUserFields array for personalization
        custom_fields = []

        # Add personalized_line if available
        if lead.get("personalized_line"):
            custom_fields.append({
                "name": "personalized_line",
                "value": lead.get("personalized_line", "")
            })

        # Add any other custom fields you want to include
        # e.g., custom_message, icebreaker, value_prop, etc.

        formatted_lead = {
            "firstName": lead.get("first_name", ""),
            "lastName": lead.get("last_name", ""),
            "profileUrl": lead.get("linkedin_url", ""),
            "companyName": lead.get("company_name", ""),
            "position": lead.get("title", ""),
            "emailAddress": lead.get("email", ""),
            "location": lead.get("location", ""),
            "customUserFields": custom_fields
        }
        formatted_leads.append(formatted_lead)
    
    print(f"Uploading {len(formatted_leads)} leads to campaign...")
    
    # HeyReach might have batch size limits, upload in chunks
    chunk_size = 100
    total_uploaded = 0
    
    for i in range(0, len(formatted_leads), chunk_size):
        chunk = formatted_leads[i:i+chunk_size]
        
        try:
            response = requests.post(url, headers=headers, json={"leads": chunk})
            response.raise_for_status()
            total_uploaded += len(chunk)
            print(f"  Uploaded {total_uploaded}/{len(formatted_leads)}...")
            
        except Exception as e:
            print(f"  ⚠️  Error uploading chunk: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response: {e.response.text}")
    
    print(f"✅ Uploaded {total_uploaded} leads")
    return total_uploaded

def start_campaign(campaign_id):
    """
    Start the campaign (begin sending).
    """
    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = f"{HEYREACH_API_BASE}/campaigns/{campaign_id}/start"
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        print(f"✅ Campaign started!")
        return True
        
    except Exception as e:
        print(f"Error starting campaign: {e}")
        return False

def update_sheet_with_campaign_id(sheet_url, campaign_id):
    """
    Update the Google Sheet with campaign ID for tracking.
    """
    creds = get_credentials()
    if not creds:
        return False
        
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        
        # Add campaign_id column if it doesn't exist
        headers = worksheet.row_values(1)
        if "campaign_id" not in headers:
            worksheet.update_cell(1, len(headers) + 1, "campaign_id")
            campaign_col_idx = len(headers) + 1
        else:
            campaign_col_idx = headers.index("campaign_id") + 1
        
        # Add outreach_status column if it doesn't exist
        headers = worksheet.row_values(1)  # Refresh headers
        if "outreach_status" not in headers:
            worksheet.update_cell(1, len(headers) + 1, "outreach_status")
            status_col_idx = len(headers) + 1
        else:
            status_col_idx = headers.index("outreach_status") + 1
        
        # Update all rows with campaign_id and status = "queued"
        records = worksheet.get_all_records()
        updates = []
        
        for idx in range(len(records)):
            row_num = idx + 2
            # Update campaign_id
            col_letter = chr(64 + campaign_col_idx)
            updates.append({
                'range': f"{col_letter}{row_num}",
                'values': [[campaign_id]]
            })
            # Update status
            col_letter = chr(64 + status_col_idx)
            updates.append({
                'range': f"{col_letter}{row_num}",
                'values': [["queued"]]
            })
        
        if updates:
            worksheet.spreadsheet.values_batch_update(
                body={
                    'value_input_option': 'RAW',
                    'data': updates
                }
            )
        
        print(f"✅ Updated sheet with campaign ID")
        return True
        
    except Exception as e:
        print(f"Error updating sheet: {e}")
        return False

def launch_campaign(sheet_url, campaign_name, message_template_path, campaign_type, daily_limit):
    """
    Main function to launch a HeyReach campaign from a Google Sheet.
    """
    # Load message template
    message_template = load_message_template(message_template_path)
    if not message_template:
        return None
    
    print(f"Message template loaded:\n{'-'*60}\n{message_template}\n{'-'*60}\n")
    
    # Load leads from sheet
    creds = get_credentials()
    if not creds:
        print("Error: Could not authenticate with Google")
        return None
        
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        records = worksheet.get_all_records()
    except Exception as e:
        print(f"Error opening sheet: {e}")
        return None
    
    if not records:
        print("Error: No records found in sheet")
        return None
    
    print(f"Found {len(records)} leads in sheet\n")
    
    # Validate required fields
    required_fields = ["first_name", "linkedin_url", "personalized_line"]
    missing_fields = [f for f in required_fields if f not in records[0]]
    
    if missing_fields:
        print(f"Error: Missing required fields: {missing_fields}")
        print("Required fields: first_name, linkedin_url, personalized_line")
        print("\nHint: Run generate_personalization.py first to add personalized lines")
        return None
    
    # Create campaign
    campaign_id = create_campaign(campaign_name, message_template, campaign_type, daily_limit)
    if not campaign_id:
        return None
    
    # Upload leads
    uploaded_count = upload_leads_to_campaign(campaign_id, records)
    if uploaded_count == 0:
        print("Error: No leads uploaded")
        return None
    
    # Update sheet with campaign ID
    update_sheet_with_campaign_id(sheet_url, campaign_id)
    
    # Start campaign
    if start_campaign(campaign_id):
        print(f"\n{'='*60}")
        print(f"✅ Campaign '{campaign_name}' is now running!")
        print(f"{'='*60}")
        print(f"Campaign ID: {campaign_id}")
        print(f"Leads: {uploaded_count}")
        print(f"Daily limit: {daily_limit} requests/day")
        print(f"Type: {campaign_type}")
        print(f"\nMonitor campaign at: https://app.heyreach.io/campaigns/{campaign_id}")
        print(f"{'='*60}")
        
        return campaign_id
    else:
        print("Error: Failed to start campaign")
        return None

def main():
    parser = argparse.ArgumentParser(description="Launch LinkedIn outreach campaign with HeyReach")
    parser.add_argument("--sheet_url", required=True, help="Google Sheet URL with leads and personalization")
    parser.add_argument("--campaign_name", required=True, help="Name for this campaign")
    parser.add_argument("--message_template", required=True, help="Path to message template file")
    parser.add_argument("--type", choices=["connection_request", "message"], default="connection_request",
                       help="Campaign type")
    parser.add_argument("--daily_limit", type=int, default=50, 
                       help="Daily limit for requests (50-100 recommended)")
    
    args = parser.parse_args()
    
    # Validate daily limit
    if args.daily_limit > 100:
        print("⚠️  WARNING: Daily limit > 100 may risk LinkedIn account restrictions")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            sys.exit(0)
    
    campaign_id = launch_campaign(
        args.sheet_url,
        args.campaign_name,
        args.message_template,
        args.type,
        args.daily_limit
    )
    
    if not campaign_id:
        print("\n❌ Campaign launch failed")
        sys.exit(1)
    
    print(f"\n✅ Success! Campaign ID: {campaign_id}")

if __name__ == "__main__":
    main()







