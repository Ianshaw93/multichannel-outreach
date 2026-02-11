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

# Test profiles with expected results (matches scraped profile structure)
TEST_PROFILES = [
    {
        "profile": {
            "full_name": "John Smith",
            "job_title": "CEO & Founder",
            "headline": "CEO & Founder @ Growth Agency | Helping B2B companies scale",
            "company": "Growth Agency",
            "company_employees": "11-50",
            "company_industry": "Marketing Services",
            "summary": "We help B2B SaaS and tech companies build their brand and automate outreach.",
            "job_description": "Leading agency strategy and client acquisition."
        },
        "expected_match": True,
        "reason": "CEO/Founder at B2B agency"
    },
    {
        "profile": {
            "full_name": "Sarah Johnson",
            "job_title": "VP of Sales",
            "headline": "VP of Sales @ SaaS Startup Inc",
            "company": "SaaS Startup Inc",
            "company_employees": "51-200",
            "company_industry": "Software",
            "summary": "Scaling revenue teams at high-growth SaaS companies.",
            "job_description": "Overseeing sales strategy, team development, and revenue targets."
        },
        "expected_match": True,
        "reason": "VP at SaaS company"
    },
    {
        "profile": {
            "full_name": "Mike Davis",
            "job_title": "Managing Partner",
            "headline": "Managing Partner | Strategy Consulting",
            "company": "Consulting Partners LLC",
            "company_employees": "11-50",
            "company_industry": "Management Consulting",
            "summary": "Helping mid-market companies with M&A and operational excellence.",
            "job_description": "Leading consulting engagements and business development."
        },
        "expected_match": True,
        "reason": "Managing Partner at consulting firm"
    },
    {
        "profile": {
            "full_name": "Emily Chen",
            "job_title": "Junior Marketing Associate",
            "headline": "Junior Marketing Associate at Tech Startup",
            "company": "Tech Startup",
            "company_employees": "11-50",
            "company_industry": "Technology",
            "summary": "Recent grad passionate about digital marketing.",
            "job_description": "Supporting social media campaigns and content creation."
        },
        "expected_match": False,
        "reason": "Junior role - not decision maker"
    },
    {
        "profile": {
            "full_name": "Carlos Martinez",
            "job_title": "Branch Manager",
            "headline": "Branch Manager at Santander Bank",
            "company": "Santander Bank",
            "company_employees": "10001+",
            "company_industry": "Banking",
            "summary": "Managing retail banking operations.",
            "job_description": "Overseeing branch operations and customer service."
        },
        "expected_match": False,
        "reason": "Traditional banking institution - hard rejection"
    },
    {
        "profile": {
            "full_name": "Lisa Anderson",
            "job_title": "Student Intern",
            "headline": "MBA Student | Summer Intern",
            "company": "ABC Corp",
            "company_employees": "201-500",
            "company_industry": "Business Services",
            "summary": "MBA candidate seeking full-time opportunities.",
            "job_description": "Supporting the marketing team with research projects."
        },
        "expected_match": False,
        "reason": "Student/Intern - not qualified"
    },
    {
        "profile": {
            "full_name": "David Kim",
            "job_title": "Delivery Driver",
            "headline": "Delivery Driver at Local Logistics",
            "company": "Local Logistics",
            "company_employees": "51-200",
            "company_industry": "Transportation",
            "summary": "Reliable driver with 5 years experience.",
            "job_description": "Delivering packages across the metro area."
        },
        "expected_match": False,
        "reason": "Physical labor role - hard rejection"
    },
    {
        "profile": {
            "full_name": "Jessica Brown",
            "job_title": "Co-Founder & CTO",
            "headline": "Co-Founder & CTO @ AI Solutions | Building the future of AI",
            "company": "AI Solutions",
            "company_employees": "11-50",
            "company_industry": "Artificial Intelligence",
            "summary": "Technical leader building AI products for enterprise.",
            "job_description": "Leading product development and engineering teams."
        },
        "expected_match": True,
        "reason": "Co-Founder at tech company"
    },
    {
        "profile": {
            "full_name": "Robert Taylor",
            "job_title": "Owner",
            "headline": "Business Coach | Helping entrepreneurs scale",
            "company": "RT Coaching",
            "company_employees": "2-10",
            "company_industry": "Professional Training and Coaching",
            "summary": "Executive coach helping founders and CEOs reach their potential.",
            "job_description": "1:1 coaching, workshops, and speaking engagements."
        },
        "expected_match": True,
        "reason": "Owner of coaching business"
    },
    {
        "profile": {
            "full_name": "Maria Garcia",
            "job_title": "Director of Marketing",
            "headline": "Director of Marketing @ Growth Agency",
            "company": "Growth Agency",
            "company_employees": "11-50",
            "company_industry": "Marketing Services",
            "summary": "Leading marketing strategy for B2B clients.",
            "job_description": "Overseeing campaigns, team, and client relationships."
        },
        "expected_match": True,
        "reason": "Director level at agency - benefit of doubt"
    },
    {
        "profile": {
            "full_name": "Tom Wilson",
            "job_title": "Account Executive",
            "headline": "Account Executive at Oracle | Crushing quota",
            "company": "Oracle",
            "company_employees": "10001+",
            "company_industry": "Software",
            "summary": "Enterprise sales professional exceeding targets.",
            "job_description": "Managing territory, hitting quota, driving new business."
        },
        "expected_match": False,
        "reason": "Salesperson at enterprise - no budget authority"
    },
    {
        "profile": {
            "fullName": "Thomas Neeck",
            "jobTitle": "Director of Product Marketing",
            "headline": "Product Marketing Director | B2B SaaS",
            "companyName": "Everest Group",
            "companySize": "501-1000",
            "industry": "Management Consulting",
            "jobStillWorking": False,
            "about": "Product marketing leader with enterprise SaaS experience."
        },
        "expected_match": False,
        "reason": "No longer at listed company - stale data"
    },
    {
        "profile": {
            "fullName": "Joe Gedeon",
            "jobTitle": "District Manager - Major Accounts",
            "headline": "Driving Business Growth with HCM Solutions",
            "companyName": "ADP",
            "companySize": "10001+",
            "industry": "Human Resources",
            "jobStillWorking": True,
            "about": "As an Owner with experience in business development..."
        },
        "expected_match": False,
        "reason": "District Manager at ADP - enterprise employee, not decision maker"
    }
]
def truncate(text, max_chars=1500):
    if not text or text == 'N/A':
        return 'N/A'
    return text[:max_chars] + '...' if len(text) > max_chars else text

def check_icp_match(lead):
    """Check if lead matches ICP using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY not found in .env")
        sys.exit(1)

    # Check if still working at current job (for competitor_post format)
    still_working = lead.get('jobStillWorking', True)  # Default True for scraped profiles without this field

    lead_summary = f"""
Lead: {lead.get('full_name', lead.get('fullName', 'Unknown'))}
Current Title: {lead.get('job_title', lead.get('jobTitle', 'Unknown'))}
Headline: {lead.get('headline', 'N/A')}
Current Company: {lead.get('company', lead.get('companyName', 'Unknown'))}
Company Size: {lead.get('company_employees', lead.get('companySize', 'Unknown'))}
Industry: {lead.get('company_industry', lead.get('industry', 'N/A'))}
Still Working Here: {still_working}
About: {truncate(lead.get('summary', lead.get('about', 'N/A')))}
Role Description: {truncate(lead.get('job_description', 'N/A'))}
"""

    system_prompt = """Role: Expert B2B Lead Qualification Analyst.

Objective: Categorize LinkedIn profiles to identify High-Ticket Decision Makers for a Sales Automation & Personal Branding agency.

CRITICAL RULES:
1. CURRENT ROLE ONLY: If "Still Working Here" is False, REJECT immediately. We only evaluate people in their CURRENT role, not past positions.
2. Prioritize the CURRENT TITLE field over the About section. The About section may contain aspirational or past descriptions.

Logic for Qualification (The "Authority" Check):
1. MANDATORY YES: Founders, CEOs, Owners, Managing Partners, and C-Suite (CMO, CRO, CEO).
2. COMPANY SIZE WEIGHTING:
   - Small/Mid-Market (<200 employees): VPs and Directors are QUALIFIED.
   - Enterprise (200+ employees or "10001+"): VPs are QUALIFIED; "Managers", "District Managers", and "Account Executives" are REJECTED.
3. THE SALESPERSON TRAP: Reject profiles with titles like "Account Executive", "Sales Rep", "District Manager", "Territory Manager" at large companies. They are employees, not buyers.

Rules for Industry Fit:
- TARGET: High-ticket B2B (SaaS, AI, Fintech, Consulting, Agency Owners, Professional Services).
- REJECT: Local retail, blue-collar services, traditional massive banks (Santander/Getnet), and public sector/government.

The "Red Flag" Rule: Employees at large companies like ADP, Oracle, Google, Salesforce in Manager/AE/Rep roles are ALWAYS rejected - they have no budget authority.

Output: Respond ONLY in valid JSON."""

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

        name = profile.get('full_name', profile.get('fullName', 'Unknown'))
        title = profile.get('job_title', profile.get('jobTitle', 'Unknown'))
        print(f"\n[TEST {idx}/{len(TEST_PROFILES)}] {name} - {title}")
        print(f"  Expected: {'✅ QUALIFY' if expected_match else '❌ REJECT'} ({test_reason})")

        result = check_icp_match(profile)

        if not result:
            print(f"  ❌ FAILED: API error")
            failed += 1
            results.append({
                "test": idx,
                "profile": name,
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
            "profile": name,
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
