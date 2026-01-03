#!/usr/bin/env python3
"""
Enrich missing emails using Apollo.io API.
Alternative to AnyMailFinder with potentially higher match rates for US B2B leads.
"""

import os
import sys
import json
import argparse
import time
from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

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

def find_email_with_apollo(linkedin_url, full_name, company_name):
    """
    Query Apollo.io API to find an email using LinkedIn URL.
    """
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        print("Error: APOLLO_API_KEY not found in .env")
        return None
    
    url = "https://api.apollo.io/v1/people/match"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    
    # Apollo's match endpoint can use LinkedIn URL directly
    body = {
        "api_key": api_key,
        "linkedin_url": linkedin_url
    }
    
    # If no LinkedIn URL, try name + company
    if not linkedin_url and full_name and company_name:
        body = {
            "api_key": api_key,
            "first_name": full_name.split()[0] if full_name else "",
            "last_name": " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
            "organization_name": company_name
        }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Apollo returns person data
        person = data.get("person")
        if person:
            email = person.get("email")
            phone = person.get("phone_numbers", [{}])[0].get("raw_number") if person.get("phone_numbers") else None
            
            return {
                "email": email,
                "phone": phone,
                "title": person.get("title"),
                "company": person.get("organization", {}).get("name")
            }
        
        return None
        
    except Exception as e:
        print(f"Error querying Apollo: {e}")
        return None

def enrich_sheet_with_apollo(sheet_url):
    """
    Enrich a Google Sheet by finding missing emails using Apollo.
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
        return sheet_url
    
    # Find column indices
    headers = worksheet.row_values(1)
    email_col = headers.index("email") + 1 if "email" in headers else None
    phone_col = headers.index("phone") + 1 if "phone" in headers else None
    
    if not email_col:
        print("Error: Could not find 'email' column in sheet")
        return None
    
    # Add phone column if it doesn't exist
    if not phone_col:
        worksheet.update_cell(1, len(headers) + 1, "phone")
        phone_col = len(headers) + 1
    
    # Collect rows that need enrichment
    rows_to_enrich = []
    for idx, record in enumerate(records):
        row_num = idx + 2
        
        # Check if email is missing
        email = record.get("email", "").strip()
        if email:
            continue
        
        # Extract required fields
        linkedin_url = record.get("linkedin_url", "").strip()
        full_name = record.get("full_name", "").strip()
        company_name = record.get("company_name", "").strip()
        
        rows_to_enrich.append({
            'row_num': row_num,
            'linkedin_url': linkedin_url,
            'full_name': full_name,
            'company_name': company_name
        })
    
    if not rows_to_enrich:
        print("No rows need email enrichment")
        return sheet_url
    
    print(f"Processing {len(rows_to_enrich)} rows with missing emails using Apollo.io...\n")
    
    enriched_count = 0
    failed_count = 0
    
    def enrich_row(row_data):
        """Helper function to enrich a single row."""
        row_num = row_data['row_num']
        display_name = row_data['full_name']
        
        print(f"Row {row_num}: Querying Apollo for {display_name}")
        
        result = find_email_with_apollo(
            row_data['linkedin_url'],
            row_data['full_name'],
            row_data['company_name']
        )
        
        return {
            'row_num': row_num,
            'result': result,
            'display_name': display_name
        }
    
    # Use ThreadPoolExecutor (Apollo rate limit: ~60 requests/min)
    updates_to_apply = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_row = {executor.submit(enrich_row, row): row for row in rows_to_enrich}
        
        for future in as_completed(future_to_row):
            result_data = future.result()
            result = result_data['result']
            
            if result and result.get('email'):
                # Stage updates
                updates_to_apply.append({
                    'row': result_data['row_num'],
                    'col': email_col,
                    'value': result['email']
                })
                
                # Also update phone if available
                if result.get('phone'):
                    updates_to_apply.append({
                        'row': result_data['row_num'],
                        'col': phone_col,
                        'value': result['phone']
                    })
                
                print(f"  ✅ Row {result_data['row_num']}: Found: {result['email']}")
                enriched_count += 1
            else:
                print(f"  ⚠️  Row {result_data['row_num']}: Email not found for {result_data['display_name']}")
                failed_count += 1
            
            # Rate limiting: Apollo allows ~60/min
            time.sleep(0.1)
    
    # Batch update sheet
    if updates_to_apply:
        print(f"\nBatch updating {len(updates_to_apply)} cells in sheet...")
        
        try:
            batch_data = []
            for update in updates_to_apply:
                col_letter = chr(64 + update['col'])
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
    
    print(f"\nEnrichment complete:")
    print(f"  - Emails found: {enriched_count}")
    print(f"  - Not found: {failed_count}")
    
    return sheet_url

def main():
    parser = argparse.ArgumentParser(description="Enrich missing emails using Apollo.io")
    parser.add_argument("sheet_url", help="Google Sheet URL to enrich")
    
    args = parser.parse_args()
    
    result_url = enrich_sheet_with_apollo(args.sheet_url)
    
    if result_url:
        print(f"\nSuccess! Updated sheet: {result_url}")
    else:
        print("Enrichment failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()







