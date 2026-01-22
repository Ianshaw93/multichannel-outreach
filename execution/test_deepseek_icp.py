#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test DeepSeek ICP filtering with various profile types.
Validates that the ICP check correctly qualifies/rejects leads.
"""

import os
import sys
from dotenv import load_dotenv
import requests
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# Test profiles with expected results
TEST_PROFILES = [
    {
        "profile": {
            "full_name": "John Smith",
            "job_title": "CEO & Founder",
            "company": "Growth Agency",
            "location": "San Francisco, CA",
            "industry": "Marketing Services"
        },
        "expected_match": True,
        "reason": "CEO/Founder at B2B agency"
    },
    {
        "profile": {
            "full_name": "Sarah Johnson",
            "job_title": "VP of Sales",
            "company": "SaaS Startup Inc",
            "location": "Austin, TX",
            "industry": "Software"
        },
        "expected_match": True,
        "reason": "VP at SaaS company"
    },
    {
        "profile": {
            "full_name": "Mike Davis",
            "job_title": "Managing Partner",
            "company": "Consulting Partners LLC",
            "location": "New York, NY",
            "industry": "Consulting"
        },
        "expected_match": True,
        "reason": "Managing Partner at consulting firm"
    },
    {
        "profile": {
            "full_name": "Emily Chen",
            "job_title": "Junior Marketing Associate",
            "company": "Tech Startup",
            "location": "Seattle, WA",
            "industry": "Technology"
        },
        "expected_match": False,
        "reason": "Junior role - not decision maker"
    },
    {
        "profile": {
            "full_name": "Carlos Martinez",
            "job_title": "Branch Manager",
            "company": "Santander Bank",
            "location": "Miami, FL",
            "industry": "Banking"
        },
        "expected_match": False,
        "reason": "Traditional banking institution - hard rejection"
    },
    {
        "profile": {
            "full_name": "Lisa Anderson",
            "job_title": "Student Intern",
            "company": "ABC Corp",
            "location": "Boston, MA",
            "industry": "Business"
        },
        "expected_match": False,
        "reason": "Student/Intern - not qualified"
    },
    {
        "profile": {
            "full_name": "David Kim",
            "job_title": "Delivery Driver",
            "company": "Local Logistics",
            "location": "Chicago, IL",
            "industry": "Transportation"
        },
        "expected_match": False,
        "reason": "Physical labor role - hard rejection"
    },
    {
        "profile": {
            "full_name": "Jessica Brown",
            "job_title": "Co-Founder & CTO",
            "company": "AI Solutions",
            "location": "Toronto, Canada",
            "industry": "Artificial Intelligence"
        },
        "expected_match": True,
        "reason": "Co-Founder at tech company"
    },
    {
        "profile": {
            "full_name": "Robert Taylor",
            "job_title": "Owner",
            "company": "RT Coaching",
            "location": "Denver, CO",
            "industry": "Professional Training"
        },
        "expected_match": True,
        "reason": "Owner of coaching business"
    },
    {
        "profile": {
            "full_name": "Maria Garcia",
            "job_title": "Director of Marketing",
            "company": "Growth Agency",
            "location": "Los Angeles, CA",
            "industry": "Marketing"
        },
        "expected_match": True,
        "reason": "Director level at agency - benefit of doubt"
    }
]

def check_icp_match(lead):
    """Check if lead matches ICP using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY not found in .env")
        sys.exit(1)

    lead_summary = f"""
Lead: {lead.get('full_name', 'Unknown')}
Title: {lead.get('job_title', 'Unknown')}
Company: {lead.get('company', 'Unknown')}
Location: {lead.get('location', 'Unknown')}
Industry: {lead.get('industry', 'N/A')}
"""

    system_prompt = """Role: B2B Lead Qualification Filter.

Objective: Categorize LinkedIn profiles based on Authority and Industry fit for a Sales Automation and Personal Branding agency.

Rules for Authority (Strict):
- Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, and C-Suite executives.
- Reject: Interns, Students, Junior staff, Administrative assistants (e.g., "Assessor administrativo"), and low-level individual contributors.

Rules for B2B Industry (Lenient):
- Qualify: High-ticket service industries (Agencies, SaaS, Consulting, Coaching, Tech).

The "Benefit of Doubt" Rule: If you are 5/10 sure or above that both points are true: (i) a business is B2B, and (ii) the person is a top-level decision-maker, Qualify them (Set to true). Only reject if they are clearly non-decision makers or in non-business roles.

Hard Rejections:
- Leads from massive traditional Banking/Financial institutions (e.g., Santander, Getnet).
- Physical labor or local retail roles (e.g., Driver, Technician, Cashier).

You are an expert at evaluating sales leads. Always respond with valid JSON."""

    user_prompt = f"""Evaluate this LinkedIn profile:

{lead_summary}

Respond in JSON format:
{{
  "match": true/false,
  "confidence": "high" | "medium" | "low",
  "reason": "Brief explanation (1 sentence)"
}}"""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        result_text = data["choices"][0]["message"]["content"]
        result = json.loads(result_text)
        return result

    except Exception as e:
        print(f"❌ API Error: {e}")
        return None

def main():
    print("\n" + "="*80)
    print("DEEPSEEK ICP FILTERING TEST")
    print("="*80)
    print(f"API Key: {DEEPSEEK_API_KEY[:20]}..." if DEEPSEEK_API_KEY else "❌ NOT FOUND")
    print("="*80 + "\n")

    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set in .env")
        print("Get your key from: https://platform.deepseek.com/api_keys")
        sys.exit(1)

    results = []
    passed = 0
    failed = 0

    for idx, test_case in enumerate(TEST_PROFILES, 1):
        profile = test_case["profile"]
        expected_match = test_case["expected_match"]
        test_reason = test_case["reason"]

        print(f"\n[TEST {idx}/{len(TEST_PROFILES)}] {profile['full_name']} - {profile['job_title']}")
        print(f"  Expected: {'✅ QUALIFY' if expected_match else '❌ REJECT'} ({test_reason})")

        result = check_icp_match(profile)

        if not result:
            print(f"  ❌ FAILED: API error")
            failed += 1
            results.append({
                "test": idx,
                "profile": profile['full_name'],
                "expected": expected_match,
                "actual": None,
                "status": "ERROR"
            })
            continue

        actual_match = result.get("match", False)
        confidence = result.get("confidence", "unknown")
        reason = result.get("reason", "")

        # Check if result matches expected
        if actual_match == expected_match:
            print(f"  ✅ PASSED: match={actual_match}, confidence={confidence}")
            print(f"     Reason: {reason}")
            passed += 1
            status = "PASS"
        else:
            print(f"  ❌ FAILED: Expected {expected_match}, got {actual_match}")
            print(f"     Confidence: {confidence}")
            print(f"     Reason: {reason}")
            failed += 1
            status = "FAIL"

        results.append({
            "test": idx,
            "profile": profile['full_name'],
            "expected": expected_match,
            "actual": actual_match,
            "confidence": confidence,
            "reason": reason,
            "status": status
        })

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(TEST_PROFILES)}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Success Rate: {(passed/len(TEST_PROFILES)*100):.1f}%")
    print("="*80)

    # Detailed failures
    if failed > 0:
        print("\nFAILED TESTS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  • {r['profile']}: Expected {r['expected']}, got {r['actual']}")
                print(f"    Reason: {r.get('reason', 'N/A')}")

    print("\n")

    # Exit code
    if failed == 0:
        print("✅ ALL TESTS PASSED - DeepSeek ICP filtering is working correctly!")
        sys.exit(0)
    else:
        print(f"❌ {failed} TESTS FAILED - Review ICP criteria or test cases")
        sys.exit(1)

if __name__ == "__main__":
    main()
