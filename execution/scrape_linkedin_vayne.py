#!/usr/bin/env python3
"""
Scrape LinkedIn profiles from Sales Navigator using Vayne.io API.
Simplified workflow: URL in → Profile list out.
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

VAYNE_API_KEY = os.getenv("VAYNE_API_KEY")
if not VAYNE_API_KEY:
    print("Error: VAYNE_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

# Vayne.io API configuration
API_BASE = "https://www.vayne.io/api"
HEADERS = {
    "Authorization": f"Bearer {VAYNE_API_KEY}",
    "Content-Type": "application/json"
}

def create_scraping_order(sales_nav_url, max_results):
    """
    Create a new scraping order with Vayne.io API.
    Returns the order ID.
    """
    print(f"Creating Vayne.io scraping order...")
    print(f"URL: {sales_nav_url}")
    print(f"Max results: {max_results}")

    # Create unique order name with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    payload = {
        "name": f"Sales Nav Scrape {max_results} profiles {timestamp}",
        "url": sales_nav_url,
        "limit": max_results,
        "email_enrichment": False,
        "saved_search": False,
        "secondary_webhook": "",
        "export_format": "advanced"
    }

    try:
        response = requests.post(f"{API_BASE}/orders", headers=HEADERS, json=payload)
        response.raise_for_status()

        order_data = response.json()
        order_id = order_data.get("order", {}).get("id")

        if not order_id:
            print(f"Error: No order ID in response: {order_data}", file=sys.stderr)
            sys.exit(1)

        print(f"Order created successfully! Order ID: {order_id}")
        return order_id

    except requests.exceptions.RequestException as e:
        print(f"Failed to create order: {e}", file=sys.stderr)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)

def poll_order_status(order_id):
    """
    Poll the order status until completion.
    Returns True if successful, False otherwise.
    """
    print(f"\nPolling order status...")
    print("(Vayne.io typically processes orders within 5-15 minutes)")

    start_time = time.time()
    poll_interval = 30  # seconds

    while True:
        try:
            response = requests.get(f"{API_BASE}/orders/{order_id}", headers=HEADERS)
            response.raise_for_status()

            order_data = response.json()
            order = order_data.get("order", {})
            status = order.get("scraping_status", "unknown")
            scraped = order.get("scraped", 0)
            total = order.get("total", 0)

            elapsed = int(time.time() - start_time)
            elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"

            if status == "initialization":
                print(f"Status: Initializing... ({elapsed_str} elapsed)")
            elif status == "scraping":
                progress = int((scraped / total * 100)) if total > 0 else 0
                print(f"Status: Scraping... Progress: {progress}% ({scraped}/{total}) ({elapsed_str} elapsed)")
            elif status == "finished":
                print(f"Order completed successfully! ({elapsed_str} total)")
                print(f"Results: {scraped} profiles extracted")
                return True
            elif status == "failed" or status == "error":
                print(f"Order failed: {status}", file=sys.stderr)
                return False
            else:
                print(f"Status: {status}, Scraped: {scraped}/{total} ({elapsed_str} elapsed)")

            time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            print(f"Error checking order status: {e}", file=sys.stderr)
            time.sleep(poll_interval)

def download_order_results(order_id):
    """
    Download the completed order results from CSV file.
    Returns the profile data as a list of dictionaries.
    """
    print(f"\nDownloading results...")

    try:
        # First get the order to find the file URL
        response = requests.get(f"{API_BASE}/orders/{order_id}", headers=HEADERS)
        response.raise_for_status()

        order_data = response.json()
        order = order_data.get("order", {})
        exports = order.get("exports", {})

        # Try to get advanced export first, then simple
        advanced_export = exports.get("advanced", {})
        simple_export = exports.get("simple", {})

        file_url = None
        if advanced_export.get("status") == "completed":
            file_url = advanced_export.get("file_url")
        elif simple_export.get("status") == "completed":
            file_url = simple_export.get("file_url")

        if not file_url:
            print("No completed export found. Generating advanced export...", file=sys.stderr)
            # Trigger export generation
            export_response = requests.post(f"{API_BASE}/orders/{order_id}/export",
                                          headers=HEADERS,
                                          json={"export_format": "advanced"})
            export_response.raise_for_status()

            # Wait a moment and try again
            time.sleep(5)
            response = requests.get(f"{API_BASE}/orders/{order_id}", headers=HEADERS)
            response.raise_for_status()
            order_data = response.json()
            file_url = order_data.get("order", {}).get("exports", {}).get("advanced", {}).get("file_url")

            if not file_url:
                print("Export still processing. Please wait and try again.", file=sys.stderr)
                return None

        # Download the CSV file
        print(f"Downloading from: {file_url}")
        csv_response = requests.get(file_url)
        csv_response.raise_for_status()

        # Parse CSV data
        import csv
        import io
        csv_data = csv_response.text
        reader = csv.DictReader(io.StringIO(csv_data))
        profiles = list(reader)

        print(f"Downloaded {len(profiles)} profiles")
        return profiles

    except requests.exceptions.RequestException as e:
        print(f"Failed to download results: {e}", file=sys.stderr)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}", file=sys.stderr)
        return None

def normalize_profiles(raw_profiles):
    """
    Normalize Vayne.io profile data to consistent schema.
    """
    normalized = []

    for profile in raw_profiles:
        # Vayne.io provides comprehensive profile data
        normalized_profile = {
            "full_name": profile.get("fullName") or profile.get("name", ""),
            "first_name": profile.get("firstName", ""),
            "last_name": profile.get("lastName", ""),
            "title": profile.get("title") or profile.get("headline", ""),
            "company_name": profile.get("companyName") or profile.get("company", ""),
            "company_domain": profile.get("companyDomain") or profile.get("companyWebsite", ""),
            "linkedin_url": profile.get("linkedinUrl") or profile.get("profileUrl", ""),
            "location": profile.get("location", ""),
            "headline": profile.get("headline", ""),
            "industry": profile.get("industry", ""),
            "connections": profile.get("connections", ""),
            "company_size": profile.get("companySize", ""),
            "company_industry": profile.get("companyIndustry", ""),
            "scraped_at": datetime.now().isoformat(),
            "source": "linkedin_sales_navigator_vayne"
        }

        # Extract first/last name from full name if needed
        if not normalized_profile["first_name"] or not normalized_profile["last_name"]:
            full_name = normalized_profile["full_name"]
            if full_name:
                parts = full_name.split(" ", 1)
                if not normalized_profile["first_name"]:
                    normalized_profile["first_name"] = parts[0]
                if not normalized_profile["last_name"] and len(parts) > 1:
                    normalized_profile["last_name"] = parts[1]

        normalized.append(normalized_profile)

    return normalized

def save_results(profiles, output_path):
    """
    Save normalized profiles to JSON file.
    """
    # Ensure .tmp directory exists
    os.makedirs(".tmp", exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(profiles, f, indent=2)

    print(f"Results saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn Sales Navigator using Vayne.io")
    parser.add_argument("--sales_nav_url", required=True, help="LinkedIn Sales Navigator search URL")
    parser.add_argument("--max_results", type=int, default=20, help="Maximum number of profiles to scrape (max: 10,000)")
    parser.add_argument("--output", default=".tmp/vayne_profiles.json", help="Output file path")
    parser.add_argument("--export_format", choices=["simple", "advanced"], default="advanced",
                       help="Export format (default: advanced for maximum data)")

    args = parser.parse_args()

    # Validate max results
    if args.max_results > 10000:
        print("Warning: Max results limited to 10,000 per Vayne.io API limits")
        args.max_results = 10000

    print(f"Starting Vayne.io LinkedIn scrape...")
    print(f"Target: {args.max_results} profiles from Sales Navigator (test run)")

    # Create scraping order
    order_id = create_scraping_order(args.sales_nav_url, args.max_results)

    # Poll until complete
    success = poll_order_status(order_id)
    if not success:
        print("Scraping failed.")
        sys.exit(1)

    # Download results
    raw_profiles = download_order_results(order_id)
    if not raw_profiles:
        print("No results downloaded.")
        sys.exit(1)

    # Normalize and save
    normalized_profiles = normalize_profiles(raw_profiles)
    save_results(normalized_profiles, args.output)

    print(f"\nSuccess! Extracted {len(normalized_profiles)} LinkedIn profiles.")
    print(f"Output: {args.output}")
    print(f"\nProfiles are ready for downstream processing:")
    print(f"  - Email enrichment")
    print(f"  - Personalization")
    print(f"  - Outreach campaigns")

if __name__ == "__main__":
    main()