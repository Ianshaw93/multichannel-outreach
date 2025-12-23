#!/usr/bin/env python3
"""
Scrape LinkedIn profiles from Sales Navigator using PhantomBuster.
Uses the "Sales Navigator Search Export" phantom.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

PHANTOMBUSTER_API_KEY = os.getenv("PHANTOMBUSTER_API_KEY")
if not PHANTOMBUSTER_API_KEY:
    print("Error: PHANTOMBUSTER_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

# PhantomBuster API endpoints
API_BASE = "https://api.phantombuster.com/api/v2"
PHANTOM_ID = "3061/sales-navigator-search-export"  # Sales Navigator Search Export

def launch_phantom(sales_nav_url, max_items):
    """
    Launch the PhantomBuster phantom with given parameters.
    Returns the agent ID and container ID.
    """
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY
    }
    
    # Get or create agent for this phantom
    print(f"Setting up PhantomBuster agent for Sales Navigator scrape...")
    
    # First, check if we have an existing agent for this phantom
    agents_response = requests.get(f"{API_BASE}/agents/fetch-all", headers=headers)
    agents_response.raise_for_status()
    agents = agents_response.json()
    
    # Find existing agent or create new one
    agent_id = None
    for agent in agents:
        if agent.get("scriptId") == PHANTOM_ID:
            agent_id = agent["id"]
            print(f"Found existing agent: {agent_id}")
            break
    
    if not agent_id:
        # Create new agent
        print("Creating new agent...")
        create_payload = {
            "name": f"Sales Nav Scraper {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "scriptId": PHANTOM_ID,
            "argument": {
                "sessionCookie": os.getenv("LINKEDIN_SESSION_COOKIE", "li_at=YOUR_SESSION_COOKIE"),
                "searches": sales_nav_url,
                "numberOfResultsPerSearch": max_items,
                "csvName": "linkedin_leads"
            }
        }
        create_response = requests.post(f"{API_BASE}/agents/save", headers=headers, json=create_payload)
        create_response.raise_for_status()
        agent_id = create_response.json()["id"]
        print(f"Created new agent: {agent_id}")
    else:
        # Update existing agent with new parameters
        update_payload = {
            "id": agent_id,
            "argument": {
                "sessionCookie": os.getenv("LINKEDIN_SESSION_COOKIE", "li_at=YOUR_SESSION_COOKIE"),
                "searches": sales_nav_url,
                "numberOfResultsPerSearch": max_items,
                "csvName": "linkedin_leads"
            }
        }
        update_response = requests.post(f"{API_BASE}/agents/save", headers=headers, json=update_payload)
        update_response.raise_for_status()
        print(f"Updated agent configuration")
    
    # Launch the agent
    print(f"Launching agent...")
    launch_response = requests.post(f"{API_BASE}/agents/launch", headers=headers, json={"id": agent_id})
    launch_response.raise_for_status()
    launch_data = launch_response.json()
    
    container_id = launch_data["containerId"]
    print(f"✅ Agent launched! Container ID: {container_id}")
    
    return agent_id, container_id

def poll_agent_status(container_id):
    """
    Poll the agent status until it completes.
    Returns True if successful, False otherwise.
    """
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY
    }
    
    print("\nWaiting for scrape to complete...")
    print("(This may take 5-30 minutes depending on the number of leads)")
    
    while True:
        response = requests.get(f"{API_BASE}/containers/fetch", headers=headers, params={"id": container_id})
        response.raise_for_status()
        data = response.json()
        
        status = data.get("status")
        progress = data.get("progress", 0)
        
        if status == "running":
            print(f"⏳ Status: Running... Progress: {progress}%")
            time.sleep(30)  # Poll every 30 seconds
        elif status == "success":
            print(f"✅ Scrape completed successfully!")
            return True
        elif status == "error":
            error_msg = data.get("errorMessage", "Unknown error")
            print(f"❌ Scrape failed: {error_msg}", file=sys.stderr)
            return False
        else:
            print(f"Status: {status}, Progress: {progress}%")
            time.sleep(30)

def fetch_results(agent_id):
    """
    Fetch the results from the completed agent.
    Returns a list of lead dictionaries.
    """
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY
    }
    
    print("\nFetching results...")
    
    # Fetch the agent's output (result container)
    response = requests.get(f"{API_BASE}/agents/fetch", headers=headers, params={"id": agent_id})
    response.raise_for_status()
    agent_data = response.json()
    
    # Get the result object (CSV or JSON)
    result_object = agent_data.get("resultObject")
    if not result_object:
        print("Error: No result object found", file=sys.stderr)
        return None
    
    # PhantomBuster stores results as CSV or JSON - fetch the file
    result_url = result_object
    result_response = requests.get(result_url)
    result_response.raise_for_status()
    
    # Parse results (usually JSON or CSV)
    try:
        # Try JSON first
        results = result_response.json()
    except:
        # If not JSON, try parsing as CSV
        import csv
        import io
        csv_data = result_response.text
        reader = csv.DictReader(io.StringIO(csv_data))
        results = list(reader)
    
    print(f"📥 Downloaded {len(results)} leads")
    return results

def normalize_leads(raw_results):
    """
    Normalize PhantomBuster output to consistent schema.
    """
    normalized = []
    
    for lead in raw_results:
        # PhantomBuster returns different field names - normalize them
        normalized_lead = {
            "full_name": lead.get("fullName") or lead.get("name") or "",
            "first_name": lead.get("firstName") or "",
            "last_name": lead.get("lastName") or "",
            "title": lead.get("title") or lead.get("headline") or "",
            "company_name": lead.get("companyName") or lead.get("company") or "",
            "company_domain": lead.get("companyUrl") or "",
            "linkedin_url": lead.get("profileUrl") or lead.get("url") or "",
            "location": lead.get("location") or "",
            "headline": lead.get("headline") or "",
            "current_position": lead.get("title") or "",
            "scraped_at": datetime.now().isoformat(),
            "source": "linkedin_sales_navigator"
        }
        
        # Extract first/last name if not provided
        if not normalized_lead["first_name"] or not normalized_lead["last_name"]:
            full_name = normalized_lead["full_name"]
            if full_name:
                parts = full_name.split(" ", 1)
                normalized_lead["first_name"] = parts[0]
                normalized_lead["last_name"] = parts[1] if len(parts) > 1 else ""
        
        normalized.append(normalized_lead)
    
    return normalized

def save_results(results, output_path):
    """
    Save results to JSON file.
    """
    # Ensure .tmp directory exists
    os.makedirs(".tmp", exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn Sales Navigator using PhantomBuster")
    parser.add_argument("--sales_nav_url", required=True, help="LinkedIn Sales Navigator search URL")
    parser.add_argument("--max_items", type=int, default=25, help="Maximum number of leads to scrape")
    parser.add_argument("--output", default=".tmp/linkedin_leads.json", help="Output file path")
    
    args = parser.parse_args()
    
    # Validate LinkedIn session cookie
    session_cookie = os.getenv("LINKEDIN_SESSION_COOKIE")
    if not session_cookie or session_cookie == "li_at=YOUR_SESSION_COOKIE":
        print("\n⚠️  WARNING: LINKEDIN_SESSION_COOKIE not set in .env")
        print("You need to set your LinkedIn session cookie for PhantomBuster to work.")
        print("\nTo get your session cookie:")
        print("1. Log in to LinkedIn in your browser")
        print("2. Open DevTools (F12) → Application → Cookies")
        print("3. Find the 'li_at' cookie and copy its value")
        print("4. Add to .env: LINKEDIN_SESSION_COOKIE=YOUR_COOKIE_VALUE\n")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            sys.exit(1)
    
    # Launch phantom
    agent_id, container_id = launch_phantom(args.sales_nav_url, args.max_items)
    
    # Poll until complete
    success = poll_agent_status(container_id)
    if not success:
        print("Scrape failed.")
        sys.exit(1)
    
    # Fetch results
    raw_results = fetch_results(agent_id)
    if not raw_results:
        print("No results retrieved.")
        sys.exit(1)
    
    # Normalize and save
    normalized_results = normalize_leads(raw_results)
    save_results(normalized_results, args.output)
    
    print(f"\n✅ Success! Scraped {len(normalized_results)} leads.")
    print(f"Output: {args.output}")

if __name__ == "__main__":
    main()


