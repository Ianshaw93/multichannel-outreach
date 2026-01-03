#!/usr/bin/env python3
"""
Send leads from CSV to HeyReach for testing.
Usage: python test_heyreach_upload.py --limit 5
"""
import os
import sys
import csv
import json
import argparse
from dotenv import load_dotenv
import requests

load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
headers = {
    "X-API-KEY": HEYREACH_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def send_to_heyreach(csv_path, list_id, limit=None):
    # Read CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        profiles = list(reader)

    if limit:
        profiles = profiles[:limit]

    print(f"Uploading {len(profiles)} leads to HeyReach list {list_id}...")

    # Format for HeyReach
    leads = []
    for p in profiles:
        if not p.get('linkedin_url'):
            continue

        lead = {
            "firstName": p.get('first_name', ''),
            "lastName": p.get('last_name', ''),
            "profileUrl": p['linkedin_url'],
            "location": p.get('location', ''),
            "companyName": p.get('company', ''),
            "position": p.get('job_title', ''),
            "emailAddress": p.get('email', ''),
            "customUserFields": []
        }

        # Add rich data as custom fields
        if p.get('summary'):
            lead['customUserFields'].append({
                "name": "about_section",
                "value": p['summary'][:1000]
            })

        if p.get('job_description'):
            lead['customUserFields'].append({
                "name": "job_description",
                "value": p['job_description'][:500]
            })

        leads.append(lead)

    # Send to HeyReach
    payload = {"leads": leads, "listId": list_id}

    response = requests.post(
        "https://api.heyreach.io/api/public/list/AddLeadsToListV2",
        headers=headers,
        json=payload
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"Added: {result.get('addedLeadsCount', 0)}")
        print(f"Updated: {result.get('updatedLeadsCount', 0)}")
        print(f"Failed: {result.get('failedLeadsCount', 0)}")
    else:
        print(f"Error: {response.text}")

    return response.status_code == 200

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=".tmp/vayne_profiles.csv")
    parser.add_argument("--list_id", type=int, default=464435)
    parser.add_argument("--limit", type=int, help="Test with N leads")
    args = parser.parse_args()

    send_to_heyreach(args.csv, args.list_id, args.limit)
