#!/usr/bin/env python3
"""Sync prospects to speed_to_lead database.

This script:
1. Reads prospect JSON files from .tmp/
2. Sends them to the speed_to_lead API for storage
3. Can be run for backfill or incremental sync

Usage:
    # Backfill all prospects
    python execution/sync_prospects_to_db.py --backfill

    # Sync specific file
    python execution/sync_prospects_to_db.py --file .tmp/ceo_leads_unique.json --source competitor_post --keyword "ceo"

Environment:
    SPEED_TO_LEAD_API_URL - API URL (default: https://speed-to-lead-production.up.railway.app)
"""

import argparse
import json
import os
import glob
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Default to Railway production URL
SPEED_TO_LEAD_API_URL = os.getenv(
    "SPEED_TO_LEAD_API_URL",
    "https://speed-to-lead-production.up.railway.app"
)


def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn URL."""
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    if "?" in url:
        url = url.split("?")[0]
    return url


def infer_source_type(filename: str) -> str:
    """Infer source type from filename."""
    filename = filename.lower()
    if "competitor_post" in filename:
        return "competitor_post"
    elif "cold_outreach" in filename:
        return "cold_outreach"
    elif "sales_nav" in filename:
        return "sales_nav"
    elif "vayne" in filename:
        return "vayne"
    return "other"


def load_prospects_from_file(filepath: str) -> list:
    """Load prospects from a JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    prospects = []
    for p in data:
        linkedin_url = normalize_linkedin_url(
            p.get("linkedinUrl") or p.get("linkedin_url") or p.get("profileUrl") or ""
        )
        if not linkedin_url:
            continue

        prospects.append({
            "linkedin_url": linkedin_url,
            "full_name": p.get("fullName") or p.get("full_name"),
            "first_name": p.get("firstName") or p.get("first_name"),
            "last_name": p.get("lastName") or p.get("last_name"),
            "job_title": p.get("jobTitle") or p.get("job_title") or p.get("position"),
            "company_name": p.get("companyName") or p.get("company_name") or p.get("company"),
            "company_industry": p.get("companyIndustry") or p.get("company_industry"),
            "location": p.get("addressWithCountry") or p.get("location"),
            "headline": p.get("headline"),
            "personalized_message": p.get("personalized_message"),
            "icp_match": p.get("icp_match"),
            "icp_reason": p.get("icp_reason"),
            "heyreach_list_id": p.get("heyreach_list_id"),
            # Engagement context
            "engagement_type": p.get("engagement_type"),
            "source_post_url": p.get("source_post_url"),
            "post_date": p.get("post_date"),
            "scraped_at": p.get("scraped_at"),
            "source_keyword": p.get("source_keyword"),
        })

    return prospects


def sync_prospects(prospects: list, source_type: str, source_keyword: str = None, heyreach_list_id: int = None) -> dict:
    """Send prospects to speed_to_lead API."""
    if not prospects:
        return {"status": "error", "message": "No prospects to sync"}

    url = f"{SPEED_TO_LEAD_API_URL}/api/prospects"

    payload = {
        "prospects": prospects,
        "source_type": source_type,
        "source_keyword": source_keyword,
        "heyreach_list_id": heyreach_list_id,
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def backfill_all(tmp_dir: str = ".tmp") -> dict:
    """Backfill all prospects from .tmp directory."""
    all_prospects = []
    seen_urls = set()

    json_files = glob.glob(f"{tmp_dir}/*.json")
    print(f"Found {len(json_files)} JSON files in {tmp_dir}")

    for filepath in json_files:
        filename = os.path.basename(filepath)

        # Skip non-prospect files
        if any(skip in filename for skip in ["validation", "cache", "heyreach_campaigns", "sample"]):
            continue

        try:
            prospects = load_prospects_from_file(filepath)
            source_type = infer_source_type(filename)

            added = 0
            for p in prospects:
                if p["linkedin_url"] not in seen_urls:
                    p["source_type"] = source_type
                    all_prospects.append(p)
                    seen_urls.add(p["linkedin_url"])
                    added += 1

            if added > 0:
                print(f"  {filename}: {added} new prospects (source: {source_type})")

        except Exception as e:
            print(f"  Error reading {filename}: {e}")

    print(f"\nTotal unique prospects: {len(all_prospects)}")

    if not all_prospects:
        return {"status": "ok", "message": "No prospects to backfill"}

    # Send to API in batches
    batch_size = 100
    total_created = 0
    total_skipped = 0

    for i in range(0, len(all_prospects), batch_size):
        batch = all_prospects[i:i + batch_size]

        url = f"{SPEED_TO_LEAD_API_URL}/api/prospects/backfill"
        payload = {"prospects": batch}

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            total_created += result.get("created", 0)
            total_skipped += result.get("skipped", 0)
            print(f"  Batch {i // batch_size + 1}: created={result.get('created', 0)}, skipped={result.get('skipped', 0)}")
        except Exception as e:
            print(f"  Error sending batch {i // batch_size + 1}: {e}")

    return {
        "status": "ok",
        "total_created": total_created,
        "total_skipped": total_skipped,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync prospects to speed_to_lead database")
    parser.add_argument("--backfill", action="store_true", help="Backfill all prospects from .tmp/")
    parser.add_argument("--file", help="Sync specific JSON file")
    parser.add_argument("--source", default="other", help="Source type (competitor_post, cold_outreach, etc.)")
    parser.add_argument("--keyword", help="Source keyword (e.g., 'ceo')")
    parser.add_argument("--list_id", type=int, help="HeyReach list ID")
    parser.add_argument("--tmp_dir", default=".tmp", help="Directory containing JSON files")

    args = parser.parse_args()

    print(f"API URL: {SPEED_TO_LEAD_API_URL}")

    if args.backfill:
        print("\n=== BACKFILLING ALL PROSPECTS ===")
        result = backfill_all(args.tmp_dir)
        print(f"\nResult: {result}")

    elif args.file:
        print(f"\n=== SYNCING FILE: {args.file} ===")
        prospects = load_prospects_from_file(args.file)
        print(f"Loaded {len(prospects)} prospects")

        result = sync_prospects(
            prospects,
            source_type=args.source,
            source_keyword=args.keyword,
            heyreach_list_id=args.list_id,
        )
        print(f"Result: {result}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
