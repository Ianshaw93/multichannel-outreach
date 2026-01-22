#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON to HeyReach - Manual review workflow for uploading approved leads.

This tool reads leads from JSON files output by the signal monitors, uploads only
leads marked as "approved": true, and updates the JSON with upload timestamps.

Workflow:
1. Signal monitor runs → outputs .tmp/{signal_name}_{timestamp}.json
2. You review JSON file in editor
3. Set "approved": true for leads you want to upload
4. Run this script to upload approved leads to HeyReach
5. JSON file is updated with "heyreach_uploaded_at" timestamp

Usage:
    # Dry run - see what would be uploaded
    python json_to_heyreach.py --input .tmp/competitor_monitor_20260121.json --dry_run
    
    # Upload approved leads
    python json_to_heyreach.py --input .tmp/competitor_monitor_20260121.json --list_id 480247
    
    # Upload multiple files
    python json_to_heyreach.py --input .tmp/*.json --list_id 480247
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import glob

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")

# Import upload function from keyword monitor
sys.path.insert(0, os.path.dirname(__file__))
from keyword_engagement_monitor import upload_to_heyreach


def load_leads_from_json(json_file: str) -> List[Dict]:
    """
    Load leads from JSON file.
    
    Args:
        json_file: Path to JSON file
        
    Returns:
        List of lead dictionaries
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            leads = json.load(f)
        
        if not isinstance(leads, list):
            print(f"Error: Expected list in {json_file}, got {type(leads)}")
            return []
        
        return leads
    except Exception as e:
        print(f"Error loading {json_file}: {e}")
        return []


def filter_approved_leads(leads: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    Separate approved and non-approved leads.
    
    Args:
        leads: List of all leads
        
    Returns:
        Tuple of (approved_leads, not_approved_leads)
    """
    approved = []
    not_approved = []
    
    for lead in leads:
        if lead.get("approved") is True:
            approved.append(lead)
        else:
            not_approved.append(lead)
    
    return approved, not_approved


def update_json_with_upload_status(json_file: str, uploaded_leads: List[Dict]):
    """
    Update JSON file with heyreach_uploaded_at timestamp for uploaded leads.
    
    Args:
        json_file: Path to JSON file
        uploaded_leads: List of leads that were uploaded
    """
    try:
        # Load current data
        with open(json_file, 'r', encoding='utf-8') as f:
            all_leads = json.load(f)
        
        # Create a set of LinkedIn URLs that were uploaded
        uploaded_urls = {lead.get("linkedinUrl") for lead in uploaded_leads}
        
        # Update timestamp for uploaded leads
        timestamp = datetime.now().isoformat()
        for lead in all_leads:
            if lead.get("linkedinUrl") in uploaded_urls:
                lead["heyreach_uploaded_at"] = timestamp
        
        # Save back to file
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_leads, f, indent=2)
        
        print(f"Updated {json_file} with upload timestamps")
        
    except Exception as e:
        print(f"Error updating JSON file: {e}")


def process_json_file(
    json_file: str,
    list_id: int,
    dry_run: bool = True
) -> Dict:
    """
    Process a single JSON file - upload approved leads to HeyReach.
    
    Args:
        json_file: Path to JSON file
        list_id: HeyReach list ID
        dry_run: If True, don't actually upload
        
    Returns:
        Results dictionary
    """
    print("\n" + "=" * 60)
    print(f"Processing: {json_file}")
    print("=" * 60)
    
    results = {
        "file": json_file,
        "total_leads": 0,
        "approved": 0,
        "uploaded": 0,
        "already_uploaded": 0
    }
    
    # Load leads
    all_leads = load_leads_from_json(json_file)
    results["total_leads"] = len(all_leads)
    
    if not all_leads:
        print("No leads found in file.")
        return results
    
    # Filter approved vs not approved
    approved_leads, not_approved = filter_approved_leads(all_leads)
    results["approved"] = len(approved_leads)
    
    print(f"Total leads: {results['total_leads']}")
    print(f"Approved for upload: {results['approved']}")
    print(f"Not approved: {len(not_approved)}")
    
    if not approved_leads:
        print("\nNo approved leads to upload.")
        print("To approve leads, edit the JSON file and set 'approved': true")
        return results
    
    # Check for already uploaded
    already_uploaded = [
        lead for lead in approved_leads 
        if lead.get("heyreach_uploaded_at") is not None
    ]
    results["already_uploaded"] = len(already_uploaded)
    
    # Filter to only non-uploaded
    to_upload = [
        lead for lead in approved_leads 
        if lead.get("heyreach_uploaded_at") is None
    ]
    
    if already_uploaded:
        print(f"Already uploaded: {len(already_uploaded)}")
    
    if not to_upload:
        print("\nAll approved leads have already been uploaded.")
        return results
    
    print(f"Ready to upload: {len(to_upload)}")
    
    # Show sample of leads to be uploaded
    print("\nSample of leads to upload:")
    for lead in to_upload[:5]:
        name = lead.get("fullName", "Unknown")
        company = lead.get("companyName", "Unknown")
        trigger = lead.get("trigger_source", "unknown")
        print(f"  - {name} at {company} ({trigger})")
    if len(to_upload) > 5:
        print(f"  ... and {len(to_upload) - 5} more")
    
    # Upload to HeyReach
    if dry_run:
        print("\n[DRY RUN] Would upload to HeyReach list {list_id}")
        results["uploaded"] = 0
    else:
        print(f"\nUploading to HeyReach list {list_id}...")
        uploaded_count = upload_to_heyreach(
            to_upload,
            list_id,
            custom_fields=["personalized_message"]
        )
        results["uploaded"] = uploaded_count
        
        # Update JSON with upload timestamps
        if uploaded_count > 0:
            update_json_with_upload_status(json_file, to_upload)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Upload approved leads from JSON files to HeyReach"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to JSON file(s) - supports wildcards (e.g., .tmp/*.json)"
    )
    parser.add_argument(
        "--list_id", type=int,
        help="HeyReach list ID to upload to"
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Preview what would be uploaded without actually uploading"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    if not args.dry_run and not HEYREACH_API_KEY:
        print("Error: HEYREACH_API_KEY not found in .env")
        print("Either add API key or use --dry_run flag")
        sys.exit(1)
    
    # Check for list ID
    if not args.dry_run and not args.list_id:
        print("Error: --list_id required for actual upload")
        print("Use --dry_run to preview without uploading")
        sys.exit(1)
    
    # Expand wildcards
    json_files = glob.glob(args.input)
    
    if not json_files:
        print(f"No files found matching: {args.input}")
        sys.exit(1)
    
    print("=" * 60)
    print("JSON TO HEYREACH UPLOADER")
    print("=" * 60)
    print(f"Files to process: {len(json_files)}")
    print(f"HeyReach list ID: {args.list_id or 'Not set (dry run)'}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    
    # Process each file
    all_results = []
    for json_file in json_files:
        result = process_json_file(json_file, args.list_id, args.dry_run)
        all_results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("UPLOAD SUMMARY")
    print("=" * 60)
    
    total_leads = sum(r["total_leads"] for r in all_results)
    total_approved = sum(r["approved"] for r in all_results)
    total_uploaded = sum(r["uploaded"] for r in all_results)
    total_already = sum(r["already_uploaded"] for r in all_results)
    
    print(f"Files processed: {len(all_results)}")
    print(f"Total leads: {total_leads}")
    print(f"Approved for upload: {total_approved}")
    print(f"Already uploaded: {total_already}")
    print(f"Newly uploaded: {total_uploaded}")
    
    if args.dry_run:
        print("\n[DRY RUN MODE] - No actual uploads performed")
        print("Remove --dry_run flag to upload approved leads")
    
    print("=" * 60)
    
    if total_uploaded > 0 or (args.dry_run and total_approved > 0):
        sys.exit(0)
    else:
        print("\nNo leads were uploaded. Make sure to:")
        print('1. Edit JSON files and set "approved": true for leads you want')
        print("2. Run without --dry_run flag")
        print("3. Provide --list_id for HeyReach upload")
        sys.exit(1)


if __name__ == "__main__":
    main()
