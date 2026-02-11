#!/usr/bin/env python3
"""
Stop a lead from receiving further messages in a HeyReach campaign.

Usage:
    python stop_lead_in_campaign.py <campaign_id> <linkedin_url>
    python stop_lead_in_campaign.py 322911 https://www.linkedin.com/in/someone/
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
HEYREACH_API_BASE = "https://api.heyreach.io/api/public"


def stop_lead_in_campaign(campaign_id: int, linkedin_url: str) -> dict:
    """
    Stop a lead in a HeyReach campaign.

    Args:
        campaign_id: HeyReach campaign ID
        linkedin_url: LinkedIn profile URL of the lead

    Returns:
        dict with 'success' bool and 'message' string
    """
    if not HEYREACH_API_KEY:
        return {"success": False, "message": "HEYREACH_API_KEY not found in .env"}

    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/campaign/StopLeadInCampaign"
    payload = {
        "campaignId": campaign_id,
        "leadUrl": linkedin_url
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)

        if resp.status_code == 200:
            return {
                "success": True,
                "message": f"Lead stopped in campaign {campaign_id}",
                "status_code": 200
            }
        elif resp.status_code == 404:
            return {
                "success": False,
                "message": "Lead not found in campaign",
                "status_code": 404
            }
        else:
            return {
                "success": False,
                "message": resp.text,
                "status_code": resp.status_code
            }

    except Exception as e:
        return {"success": False, "message": str(e)}


def main():
    if len(sys.argv) < 3:
        print("Usage: python stop_lead_in_campaign.py <campaign_id> <linkedin_url>")
        print("Example: python stop_lead_in_campaign.py 322911 https://www.linkedin.com/in/someone/")
        sys.exit(1)

    campaign_id = int(sys.argv[1])
    linkedin_url = sys.argv[2]

    print(f"Stopping lead in campaign {campaign_id}...")
    print(f"LinkedIn URL: {linkedin_url}")

    result = stop_lead_in_campaign(campaign_id, linkedin_url)

    if result["success"]:
        print(f"Success: {result['message']}")
    else:
        print(f"Failed: {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
