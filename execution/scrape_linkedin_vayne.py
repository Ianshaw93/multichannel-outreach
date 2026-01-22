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
            print("No completed export found. Generating advanced export...")
            # Trigger export generation
            export_response = requests.post(f"{API_BASE}/orders/{order_id}/export",
                                          headers=HEADERS,
                                          json={"export_format": "advanced"})
            export_response.raise_for_status()

            # Wait for export to process (can take 30-60 seconds)
            print("Waiting for export to process...")
            max_retries = 12  # 12 × 5s = 60 seconds max wait
            for attempt in range(max_retries):
                time.sleep(5)
                response = requests.get(f"{API_BASE}/orders/{order_id}", headers=HEADERS)
                response.raise_for_status()
                order_data = response.json()

                advanced_export = order_data.get("order", {}).get("exports", {}).get("advanced", {})
                export_status = advanced_export.get("status")
                file_url = advanced_export.get("file_url")

                print(f"  Attempt {attempt+1}/{max_retries}: Export status = {export_status}")

                if export_status == "completed" and file_url:
                    break

            if not file_url:
                print(f"Export not ready after {max_retries} attempts. Order ID: {order_id}", file=sys.stderr)
                print("You can manually download later using the order ID.", file=sys.stderr)
                return None

        # Download the CSV file
        print(f"Downloading from: {file_url}")
        csv_response = requests.get(file_url)
        csv_response.raise_for_status()

        # Save raw CSV for debugging
        raw_csv_path = ".tmp/vayne_raw_export.csv"
        os.makedirs(".tmp", exist_ok=True)
        with open(raw_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_response.text)
        print(f"Raw CSV saved to: {raw_csv_path}")

        # Parse CSV data
        import csv
        import io
        csv_data = csv_response.text
        reader = csv.DictReader(io.StringIO(csv_data))
        profiles = list(reader)

        # Print column names for debugging
        if profiles:
            print(f"CSV columns: {list(profiles[0].keys())}")

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
    Captures ALL rich profile data for personalization.
    """
    normalized = []

    for profile in raw_profiles:
        # Basic info
        normalized_profile = {
            "first_name": profile.get("first name", ""),
            "last_name": profile.get("last name", ""),
            "full_name": f"{profile.get('first name', '')} {profile.get('last name', '')}".strip(),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "linkedin_url": profile.get("linkedin url", ""),
            "location": profile.get("location", ""),
            "headline": profile.get("headline", ""),
            "connections": profile.get("number of connections", ""),

            # RICH PROFILE DATA (the good stuff!)
            "summary": profile.get("summary", ""),  # About section - KEY for personalization
            "skills": profile.get("skills", ""),
            "languages": profile.get("languages", ""),
            "certifications": profile.get("certifications", ""),

            # Current job
            "job_title": profile.get("job title", ""),
            "job_description": profile.get("job description", ""),
            "job_started_on": profile.get("job started on", ""),
            "company": profile.get("company", ""),
            "company_linkedin_url": profile.get("corporate linkedin url", ""),
            "company_website": profile.get("corporate website", ""),
            "company_description": profile.get("linkedin description", ""),
            "company_specialities": profile.get("linkedin specialities", ""),
            "company_employees": profile.get("linkedin employees", ""),
            "company_industry": profile.get("linkedin industry", ""),
            "company_founded": profile.get("linkedin founded year", ""),
            "company_location": profile.get("linkedin company location", ""),

            # Previous jobs (for context on career trajectory)
            "previous_job_title": profile.get("job title (2)", ""),
            "previous_job_description": profile.get("job description (2)", ""),
            "previous_company": profile.get("company (2)", ""),

            # Education
            "education_degree": profile.get("education degree (1)", ""),
            "education_field": profile.get("education fields of study (1)", ""),
            "education_school": profile.get("education school (1)", ""),

            # Meta
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