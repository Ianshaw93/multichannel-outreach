#!/usr/bin/env python3
"""Look up a prospect by name or email.

Used to find LinkedIn URL for Calendly bookers etc.

Usage:
    python execution/lookup_prospect.py --email "john@example.com"
    python execution/lookup_prospect.py --name "John Smith"
    python execution/lookup_prospect.py --first_name "John" --last_name "Smith"

Environment:
    SPEED_TO_LEAD_API_URL - API URL (default: https://speedtolead-production.up.railway.app)
"""

import argparse
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SPEED_TO_LEAD_API_URL = os.getenv(
    "SPEED_TO_LEAD_API_URL",
    "https://speedtolead-production.up.railway.app"
)


def lookup_prospect(
    email: str = None,
    name: str = None,
    first_name: str = None,
    last_name: str = None,
) -> dict:
    """Look up a prospect by email or name.

    Args:
        email: Email address to search
        name: Full name to search
        first_name: First name
        last_name: Last name

    Returns:
        dict with matches and count
    """
    params = {}
    if email:
        params["email"] = email
    if name:
        params["name"] = name
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name

    if not params:
        return {"error": "Must provide at least one search parameter"}

    url = f"{SPEED_TO_LEAD_API_URL}/api/prospects/lookup"

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Look up a prospect by name or email")
    parser.add_argument("--email", help="Email address to search")
    parser.add_argument("--name", help="Full name to search")
    parser.add_argument("--first_name", help="First name")
    parser.add_argument("--last_name", help="Last name")

    args = parser.parse_args()

    if not any([args.email, args.name, args.first_name, args.last_name]):
        parser.print_help()
        print("\nError: Must provide at least one search parameter")
        return

    print(f"API URL: {SPEED_TO_LEAD_API_URL}")
    print(f"Searching for:")
    if args.email:
        print(f"  Email: {args.email}")
    if args.name:
        print(f"  Name: {args.name}")
    if args.first_name:
        print(f"  First name: {args.first_name}")
    if args.last_name:
        print(f"  Last name: {args.last_name}")
    print()

    result = lookup_prospect(
        email=args.email,
        name=args.name,
        first_name=args.first_name,
        last_name=args.last_name,
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    if result.get("count", 0) == 0:
        print("No matches found")
        return

    print(f"Found {result['count']} match(es):\n")

    for i, match in enumerate(result["matches"], 1):
        print(f"Match {i}:")
        print(f"  Name: {match.get('full_name') or f'{match.get(\"first_name\", \"\")} {match.get(\"last_name\", \"\")}'.strip()}")
        print(f"  LinkedIn: {match.get('linkedin_url')}")
        if match.get("email"):
            print(f"  Email: {match.get('email')}")
        if match.get("company_name"):
            print(f"  Company: {match.get('company_name')}")
        if match.get("job_title"):
            print(f"  Title: {match.get('job_title')}")
        print()


if __name__ == "__main__":
    main()
