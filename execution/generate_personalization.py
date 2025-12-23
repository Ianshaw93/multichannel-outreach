#!/usr/bin/env python3
"""
Generate personalized opening lines for LinkedIn outreach using Claude.
Analyzes LinkedIn profiles to create contextual, non-generic personalizations.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic
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

def get_personalization_prompt(template_name="default_linkedin"):
    """
    Get the personalization prompt template.
    """
    templates = {
        "default_linkedin": """You are an expert at crafting personalized LinkedIn outreach messages.

Your task: Generate a personalized opening line for a LinkedIn connection request or message.

Lead Information:
- Name: {full_name}
- Title: {title}
- Company: {company_name}
- Location: {location}
- Headline: {headline}

Requirements for the personalized line:
1. Must be SPECIFIC to this person (reference their role, company, location, or industry)
2. Must be NATURAL and conversational (not robotic or salesy)
3. Must be SHORT (under 50 words, ideally 1 sentence)
4. Must NOT be generic (avoid "I came across your profile", "I see you're in X industry")
5. Should show genuine interest or relevance
6. Can reference their location, company growth, industry trends, or role challenges

Good examples:
- "Saw you're scaling the HVAC team at {company} - hiring in this market is tough!"
- "Fellow Austin business owner here - love seeing local HVAC companies thrive"
- "Congrats on the growth at {company} - noticed you're expanding to new areas"

Bad examples (too generic):
- "I came across your profile and thought we should connect"
- "I see you work in HVAC"
- "I'd love to connect with you"

Return ONLY the personalized line (no quotes, no explanation).
""",
        
        "service_business": """You are an expert at reaching out to local service business owners.

Your task: Generate a personalized opening line for a LinkedIn message to a service business owner.

Lead Information:
- Name: {full_name}
- Title: {title}
- Company: {company_name}
- Location: {location}

Focus on:
- Common challenges (hiring, customer acquisition, scaling)
- Local pride (if same city/region)
- Industry respect (acknowledge the hard work)
- Business growth signals

Return ONLY the personalized line (under 50 words).
""",
        
        "saas_founder": """You are an expert at reaching out to SaaS and tech founders.

Your task: Generate a personalized opening line for a LinkedIn message to a SaaS founder.

Lead Information:
- Name: {full_name}
- Title: {title}
- Company: {company_name}
- Headline: {headline}

Focus on:
- Product/market fit challenges
- Scaling struggles
- Industry trends
- Growth signals (hiring, funding, expansion)

Return ONLY the personalized line (under 50 words).
"""
    }
    
    return templates.get(template_name, templates["default_linkedin"])

def generate_personalization(lead, prompt_template):
    """
    Generate a personalized line for one lead using Claude.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    
    client = Anthropic(api_key=api_key)
    
    # Fill in the prompt template
    prompt = prompt_template.format(
        full_name=lead.get("full_name", ""),
        title=lead.get("title", ""),
        company_name=lead.get("company_name", ""),
        location=lead.get("location", ""),
        headline=lead.get("headline", "")
    )
    
    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Fast and cheap for this task
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        personalized_line = response.content[0].text.strip()
        
        # Remove quotes if Claude added them
        if personalized_line.startswith('"') and personalized_line.endswith('"'):
            personalized_line = personalized_line[1:-1]
        
        return personalized_line
        
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
    parser = argparse.ArgumentParser(description="Generate personalized LinkedIn opening lines")
    parser.add_argument("--sheet_url", required=True, help="Google Sheet URL with leads")
    parser.add_argument("--output_column", default="personalized_line", help="Column name for personalized lines")
    parser.add_argument("--prompt_template", default="default_linkedin", 
                       choices=["default_linkedin", "service_business", "saas_founder"],
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


