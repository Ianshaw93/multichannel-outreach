#!/usr/bin/env python3
"""
Export personalized messages with source data for manual accuracy review.
Outputs a CSV that makes side-by-side comparison easy.
"""

import os
import sys
import json
import csv
import argparse
import re


def extract_inferred_service(message: str) -> str:
    """Extract what the message claims they do from the 'You guys do X right?' pattern."""
    # Pattern: "You guys do X right?"
    match = re.search(r"You guys do (.+?) right\?", message)
    if match:
        return match.group(1).strip()
    return "(couldn't extract)"


def extract_inferred_method(message: str) -> str:
    """Extract the method from 'Do that w X + Y? Or what' pattern."""
    match = re.search(r"Do that w (.+?)\? Or what", message)
    if match:
        return match.group(1).strip()
    return "(couldn't extract)"


def export_for_review(input_file: str, output_file: str = None, sample_size: int = None):
    """Export leads to CSV for manual accuracy review."""

    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    # Filter to only leads with personalized_message
    leads_with_messages = [l for l in leads if l.get("personalized_message")]

    if sample_size and sample_size < len(leads_with_messages):
        import random
        random.seed(42)  # Reproducible sampling
        leads_with_messages = random.sample(leads_with_messages, sample_size)

    if output_file is None:
        output_file = input_file.replace('.json', '_review.csv')

    # CSV columns for easy review
    fieldnames = [
        'full_name',
        'linkedin_url',
        'headline',
        'company',
        'company_description_excerpt',
        'inferred_service',
        'inferred_method',
        'personalized_message',
        'accuracy_score',  # For manual scoring
        'notes'  # For manual notes
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in leads_with_messages:
            msg = lead.get("personalized_message", "")
            company_desc = lead.get("company_description", "")

            # Truncate company description for readability
            if len(company_desc) > 300:
                company_desc = company_desc[:300] + "..."

            row = {
                'full_name': lead.get("full_name", ""),
                'linkedin_url': lead.get("linkedin_url", ""),
                'headline': lead.get("headline", ""),
                'company': lead.get("company", ""),
                'company_description_excerpt': company_desc,
                'inferred_service': extract_inferred_service(msg),
                'inferred_method': extract_inferred_method(msg),
                'personalized_message': msg,
                'accuracy_score': '',  # User fills this
                'notes': ''  # User fills this
            }
            writer.writerow(row)

    print(f"Exported {len(leads_with_messages)} leads for review")
    print(f"Output: {output_file}")
    print(f"\nInstructions:")
    print(f"  1. Open in spreadsheet")
    print(f"  2. Compare inferred_service vs headline + company_description")
    print(f"  3. Score accuracy 1-5 (1=wrong, 5=exact)")
    print(f"  4. Add notes for FAIL cases")

    # Also print a quick summary of inferred services for pattern analysis
    services = {}
    for lead in leads_with_messages:
        svc = extract_inferred_service(lead.get("personalized_message", ""))
        services[svc] = services.get(svc, 0) + 1

    print(f"\nTop inferred services:")
    for svc, count in sorted(services.items(), key=lambda x: -x[1])[:10]:
        print(f"  {count:3d}x  {svc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export personalized messages for manual review")
    parser.add_argument("input_file", help="JSON file with personalized messages")
    parser.add_argument("--output", "-o", help="Output CSV file")
    parser.add_argument("--sample", "-s", type=int, help="Export only N random samples")

    args = parser.parse_args()
    export_for_review(args.input_file, args.output, args.sample)
