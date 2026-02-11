#!/usr/bin/env python3
"""
Report Activity - Send pipeline metrics to speed_to_lead reporting system.

Called after pipeline runs to record activity metrics for daily/weekly reports.

Usage:
    # From competitor_post_pipeline.py results:
    python report_activity.py --results '{"profiles_scraped": 150, "icp_qualified": 45}'

    # Manual reporting:
    python report_activity.py --profiles 150 --icp 45 --uploaded 40 --apify_cost 3.75
"""

import argparse
import json
import os
import sys
from datetime import date
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# API endpoint
SPEED_TO_LEAD_API_URL = os.getenv(
    "SPEED_TO_LEAD_API_URL",
    "https://speedtolead-production.up.railway.app"
)


def report_metrics(
    posts_scraped: int = 0,
    profiles_scraped: int = 0,
    icp_qualified: int = 0,
    heyreach_uploaded: int = 0,
    apify_cost: float = 0.0,
    deepseek_cost: float = 0.0,
    target_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Report metrics to speed_to_lead.

    Args:
        posts_scraped: Number of posts scraped.
        profiles_scraped: Number of profiles scraped.
        icp_qualified: Number of ICP-qualified prospects.
        heyreach_uploaded: Number uploaded to HeyReach.
        apify_cost: Apify cost incurred.
        deepseek_cost: DeepSeek cost incurred.
        target_date: Date for the metrics (defaults to today).

    Returns:
        API response dict.
    """
    payload = {
        "date": (target_date or date.today()).isoformat(),
        "posts_scraped": posts_scraped,
        "profiles_scraped": profiles_scraped,
        "icp_qualified": icp_qualified,
        "heyreach_uploaded": heyreach_uploaded,
        "apify_cost": apify_cost,
        "deepseek_cost": deepseek_cost,
    }

    url = f"{SPEED_TO_LEAD_API_URL}/api/metrics/multichannel"

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"Metrics reported successfully: {result}")
        return result
    except requests.RequestException as e:
        print(f"Failed to report metrics: {e}")
        return {"status": "error", "error": str(e)}


def report_from_pipeline_results(results: Dict[str, Any], cost_tracker: Any = None) -> Dict[str, Any]:
    """
    Report metrics from pipeline results dict.

    Args:
        results: Pipeline results dict (from run_full_pipeline).
        cost_tracker: Optional CostTracker instance.

    Returns:
        API response dict.
    """
    # Extract counts from results
    posts_scraped = results.get("posts_filtered", 0)
    profiles_scraped = results.get("profiles_scraped", 0)
    icp_qualified = results.get("icp_qualified", 0)
    heyreach_uploaded = results.get("uploaded", 0)

    # Extract costs if cost_tracker provided
    apify_cost = 0.0
    deepseek_cost = 0.0

    if cost_tracker:
        costs = cost_tracker.costs
        apify_cost = (
            costs.get("apify_google_search", 0) +
            costs.get("apify_post_reactions", 0) +
            costs.get("apify_profile_scraper", 0)
        )
        deepseek_cost = (
            costs.get("deepseek_icp", 0) +
            costs.get("deepseek_personalization", 0)
        )

    return report_metrics(
        posts_scraped=posts_scraped,
        profiles_scraped=profiles_scraped,
        icp_qualified=icp_qualified,
        heyreach_uploaded=heyreach_uploaded,
        apify_cost=apify_cost,
        deepseek_cost=deepseek_cost,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Report pipeline metrics to speed_to_lead"
    )
    parser.add_argument(
        "--results", type=str,
        help="JSON string of pipeline results"
    )
    parser.add_argument(
        "--posts", type=int, default=0,
        help="Number of posts scraped"
    )
    parser.add_argument(
        "--profiles", type=int, default=0,
        help="Number of profiles scraped"
    )
    parser.add_argument(
        "--icp", type=int, default=0,
        help="Number of ICP-qualified prospects"
    )
    parser.add_argument(
        "--uploaded", type=int, default=0,
        help="Number uploaded to HeyReach"
    )
    parser.add_argument(
        "--apify_cost", type=float, default=0.0,
        help="Apify cost"
    )
    parser.add_argument(
        "--deepseek_cost", type=float, default=0.0,
        help="DeepSeek cost"
    )

    args = parser.parse_args()

    if args.results:
        # Parse results JSON
        try:
            results = json.loads(args.results)
            result = report_from_pipeline_results(results)
        except json.JSONDecodeError as e:
            print(f"Failed to parse results JSON: {e}")
            sys.exit(1)
    else:
        # Use individual args
        result = report_metrics(
            posts_scraped=args.posts,
            profiles_scraped=args.profiles,
            icp_qualified=args.icp,
            heyreach_uploaded=args.uploaded,
            apify_cost=args.apify_cost,
            deepseek_cost=args.deepseek_cost,
        )

    if result.get("status") == "ok":
        print("Metrics reported successfully")
        sys.exit(0)
    else:
        print(f"Failed to report metrics: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
