#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Competitor Monitor - Find prospects engaging with SPECIFIC competitor accounts.

This is TRUE competitor monitoring (Gojiberry-style) - monitoring posts FROM specific
competitor LinkedIn profiles/companies, not just generic keyword searches.

Pipeline:
1. Input: Competitor LinkedIn profile URL
2. Scrape their recent posts (last 24-48 hours)
3. For each post with engagement, scrape who liked/commented
4. Scrape LinkedIn profiles of engagers
5. Filter for US/Canada prospects
6. ICP qualification (DeepSeek)
7. Generate personalized LinkedIn DMs (DeepSeek)
8. Save to JSON with trigger metadata

Manual Usage:
    python3 competitor_monitor.py --competitor_url "https://linkedin.com/in/competitor-ceo" --dry_run
    python3 competitor_monitor.py --config config/competitors.json --list_id 480247
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# API Keys
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")

# Apify Actor IDs
POST_REACTIONS_ACTOR = "J9UfswnR3Kae4O6vm"  # apimaestro/linkedin-post-reactions
PROFILE_SCRAPER_ACTOR = "dev_fusion~Linkedin-Profile-Scraper"

# Import reusable functions from keyword_engagement_monitor
# We'll import the core functions we need
sys.path.insert(0, os.path.dirname(__file__))
from keyword_engagement_monitor import (
    filter_by_location,
    qualify_leads_with_deepseek,
    generate_personalization_deepseek,
    scrape_linkedin_profiles,
    upload_to_heyreach,
    aggregate_profile_urls,
    deduplicate_profile_urls
)


# =============================================================================
# COMPETITOR POST SCRAPING
# =============================================================================

def get_recent_posts_from_profile(profile_url: str, max_age_hours: int = 48) -> List[str]:
    """
    Get recent post URLs from a specific LinkedIn profile.
    
    This is a SIMPLIFIED implementation - in production, you'd use a LinkedIn post scraper.
    For now, we'll require manually providing post URLs or use Apify's post scraper.
    
    Args:
        profile_url: LinkedIn profile URL
        max_age_hours: Maximum age of posts in hours
        
    Returns:
        List of post URLs
    """
    print(f"Note: Automated profile post scraping not yet implemented.")
    print(f"For now, manually provide post URLs from {profile_url}")
    print(f"Looking for posts from last {max_age_hours} hours")
    
    # TODO: Implement with Apify LinkedIn Post Scraper or similar
    # For manual testing, we'll return empty and require post URLs as input
    return []


def scrape_post_engagers(post_urls: List[str]) -> List[Dict]:
    """
    Scrape engagers (reactions) from LinkedIn posts using Apify.
    (Reused from keyword_engagement_monitor)
    
    Args:
        post_urls: List of LinkedIn post URLs
        
    Returns:
        List of engager dictionaries
    """
    if not APIFY_API_TOKEN:
        print("Error: APIFY_API_TOKEN not found in .env")
        return []

    try:
        from apify_client import ApifyClient
        client = ApifyClient(APIFY_API_TOKEN)
    except ImportError:
        print("Error: apify-client not installed")
        return []

    all_engagers = []

    for url in post_urls:
        print(f"  Scraping engagers from: {url}")

        run_input = {
            "post_urls": [url]
        }

        try:
            run = client.actor(POST_REACTIONS_ACTOR).call(run_input=run_input)

            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                all_engagers.append(item)

        except Exception as e:
            print(f"  Error scraping post engagers: {e}")

    print(f"  Found {len(all_engagers)} total engagers")
    return all_engagers


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_competitor_monitor(
    competitor_url: str = None,
    post_urls: List[str] = None,
    competitor_name: str = "Competitor",
    allowed_countries: List[str] = None,
    heyreach_list_id: int = None,
    dry_run: bool = True,
    skip_icp: bool = False
) -> Dict[str, Any]:
    """
    Run the competitor monitoring pipeline.
    
    Args:
        competitor_url: LinkedIn profile URL of competitor
        post_urls: Specific post URLs to scrape (if not scraping profile)
        competitor_name: Name of competitor for logging
        allowed_countries: Allowed country list
        heyreach_list_id: HeyReach list ID for upload
        dry_run: If True, don't upload to HeyReach
        skip_icp: Skip ICP filtering
        
    Returns:
        Pipeline results dictionary
    """
    if allowed_countries is None:
        allowed_countries = ["United States", "Canada", "USA", "America"]

    print("=" * 60)
    print("COMPETITOR MONITOR")
    print("=" * 60)
    print(f"Signal Type: Competitor Engagement")
    print(f"Competitor: {competitor_name}")
    print(f"Competitor URL: {competitor_url or 'Manual post URLs'}")
    print(f"Post URLs provided: {len(post_urls) if post_urls else 0}")
    print(f"Target countries: {', '.join(allowed_countries)}")
    print(f"HeyReach list ID: {heyreach_list_id or 'Not set (dry run only)'}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    results = {
        "competitor": competitor_name,
        "posts_scraped": 0,
        "engagers_found": 0,
        "profiles_scraped": 0,
        "location_filtered": 0,
        "icp_qualified": 0,
        "personalized": 0,
        "uploaded": 0
    }

    # Step 1: Get post URLs
    if not post_urls:
        print("\n[1/7] Scraping recent posts from competitor profile...")
        post_urls = get_recent_posts_from_profile(competitor_url)
        
        if not post_urls:
            print("\nNo post URLs available.")
            print("MANUAL INPUT REQUIRED: Please provide post URLs with --post_urls flag")
            print(f"Example: --post_urls 'https://linkedin.com/posts/abc123' 'https://linkedin.com/posts/def456'")
            return results
    else:
        print(f"\n[1/7] Using {len(post_urls)} provided post URLs")
    
    results["posts_scraped"] = len(post_urls)

    # Step 2: Scrape post engagers
    print("\n[2/7] Scraping post engagers...")
    engagers = scrape_post_engagers(post_urls)
    results["engagers_found"] = len(engagers)

    if not engagers:
        print("No engagers found. Exiting.")
        return results

    # Step 3: Aggregate and deduplicate profile URLs
    print("\n[3/7] Aggregating profile URLs...")
    profile_urls = aggregate_profile_urls(engagers)
    profile_urls = deduplicate_profile_urls(profile_urls)
    print(f"  Found {len(profile_urls)} unique profile URLs")

    # Step 4: Scrape LinkedIn profiles
    print("\n[4/7] Scraping LinkedIn profiles...")
    profiles = scrape_linkedin_profiles(profile_urls, wait_seconds=120, poll_interval=30)
    results["profiles_scraped"] = len(profiles)

    if not profiles:
        print("No profiles scraped. Exiting.")
        return results

    # Step 5: Filter by location
    print("\n[5/7] Filtering by location...")
    location_filtered = filter_by_location(profiles, allowed_countries)
    results["location_filtered"] = len(location_filtered)

    if not location_filtered:
        print("No leads in target locations. Exiting.")
        return results

    # Step 6: ICP qualification
    if skip_icp:
        print("\n[6/7] Skipping ICP qualification...")
        qualified_leads = location_filtered
        for lead in qualified_leads:
            lead["icp_match"] = True
            lead["icp_confidence"] = "skipped"
            lead["icp_reason"] = "ICP check skipped"
    else:
        print("\n[6/7] Qualifying leads (ICP)...")
        qualified_leads = qualify_leads_with_deepseek(location_filtered)

    results["icp_qualified"] = len(qualified_leads)

    if not qualified_leads:
        print("No leads passed ICP qualification. Exiting.")
        return results

    # Step 7: Generate personalization and add trigger metadata
    print("\n[7/7] Generating personalized messages...")
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    for lead in qualified_leads:
        lead["personalized_message"] = generate_personalization_deepseek(lead)
        
        # Add trigger metadata (Gojiberry-style)
        lead["trigger_source"] = "competitor_monitoring"
        lead["trigger_detail"] = f"Engaged with {competitor_name}'s post"
        lead["trigger_date"] = timestamp
        lead["trigger_url"] = post_urls[0] if post_urls else ""
        lead["competitor_name"] = competitor_name
        lead["competitor_url"] = competitor_url
        lead["approved"] = False  # Manual review required
        lead["notes"] = ""
        lead["heyreach_uploaded_at"] = None
    
    results["personalized"] = len(qualified_leads)

    # Step 8: Upload to HeyReach (only if not dry_run and has list_id)
    if not dry_run and heyreach_list_id:
        print("\n[8/8] Uploading to HeyReach...")
        uploaded = upload_to_heyreach(
            qualified_leads,
            heyreach_list_id,
            custom_fields=["personalized_message"]
        )
        results["uploaded"] = uploaded
    else:
        print("\n[8/8] Skipping HeyReach upload (dry run mode)")

    # Save results
    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f".tmp/competitor_monitor_{timestamp_file}.json"
    os.makedirs(".tmp", exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(qualified_leads, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for key, value in results.items():
        print(f"  {key}: {value}")
    print("=" * 60)

    return results


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Competitor Monitor - Find prospects engaging with specific competitor accounts"
    )
    parser.add_argument(
        "--config",
        help="Path to config JSON file (e.g., config/competitors.json)"
    )
    parser.add_argument(
        "--competitor_url",
        help="LinkedIn profile URL of competitor"
    )
    parser.add_argument(
        "--competitor_name",
        help="Name of competitor for logging"
    )
    parser.add_argument(
        "--post_urls", nargs="+",
        help="Specific LinkedIn post URLs to scrape (space-separated)"
    )
    parser.add_argument(
        "--countries", nargs="+",
        help="Allowed countries"
    )
    parser.add_argument(
        "--list_id", type=int,
        help="HeyReach list ID (optional, for direct upload)"
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Don't upload to HeyReach (always save to JSON)"
    )
    parser.add_argument(
        "--skip_icp", action="store_true",
        help="Skip ICP filtering"
    )

    args = parser.parse_args()

    # Load config if provided
    config_data = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
            print(f"Loaded config from: {args.config}")
            
            # Use first competitor from config if not specified
            if not args.competitor_url and config_data.get("competitors"):
                first_comp = config_data["competitors"][0]
                args.competitor_url = first_comp.get("linkedin_url")
                args.competitor_name = first_comp.get("name", "Competitor")
                
        except Exception as e:
            print(f"Error loading config: {e}")
            sys.exit(1)

    # Validate inputs
    if not args.competitor_url and not args.post_urls:
        print("Error: Must provide either --competitor_url or --post_urls")
        print("\nManual testing example:")
        print('  python competitor_monitor.py --post_urls "https://linkedin.com/posts/abc123" --dry_run')
        sys.exit(1)

    # CLI args override config
    competitor_url = args.competitor_url
    competitor_name = args.competitor_name or config_data.get("competitor_name", "Competitor")
    post_urls = args.post_urls
    countries = args.countries or config_data.get("countries", ["United States", "Canada"])
    list_id = args.list_id

    results = run_competitor_monitor(
        competitor_url=competitor_url,
        post_urls=post_urls,
        competitor_name=competitor_name,
        allowed_countries=countries,
        heyreach_list_id=list_id,
        dry_run=args.dry_run,
        skip_icp=args.skip_icp
    )

    if results["icp_qualified"] > 0:
        print("\nPipeline completed successfully!")
        sys.exit(0)
    else:
        print("\nPipeline completed but no leads qualified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
