#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Competitor Post Pipeline - Find and engage with people who react to competitor LinkedIn posts.

This pipeline:
1. Searches Google for LinkedIn posts about "CEOs" (last 7 days)
2. Filters posts with 50+ reactions
3. Scrapes post engagers via Apify
4. Scrapes LinkedIn profiles of engagers
5. Filters for US/Canada prospects
6. Qualifies leads via ICP filter (DeepSeek)
7. Generates personalized LinkedIn DMs (DeepSeek)
8. Uploads to HeyReach

Based on n8n workflow: "Competitor's post flow -> add connection"

Usage:
    python3 competitor_post_pipeline.py --keywords "ceos" --list_id 480247
    python3 competitor_post_pipeline.py --keywords "founders" --days_back 14 --dry_run
"""

import os
import sys
import json
import re
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from prompts import get_linkedin_5_line_prompt

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# API Keys
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")

# Apify Actor IDs from the n8n workflow
GOOGLE_SEARCH_ACTOR = "nFJndFXA5zjCTuudP"  # apify/google-search-scraper
POST_REACTIONS_ACTOR = "J9UfswnR3Kae4O6vm"  # apimaestro/linkedin-post-reactions
PROFILE_SCRAPER_ACTOR = "dev_fusion~Linkedin-Profile-Scraper"


# =============================================================================
# CONFIGURATION
# =============================================================================

def get_default_config() -> Dict[str, Any]:
    """Get default pipeline configuration."""
    return {
        "search_keywords": "ceos",
        "days_back": 7,
        "min_reactions": 50,
        "max_pages_per_query": 1,
        "results_per_page": 10,
        "allowed_countries": ["United States", "Canada", "USA", "America"],
        "heyreach_list_id": 480247,
        "scrape_wait_seconds": 120,
        "poll_interval_seconds": 30,
    }


# =============================================================================
# COST TRACKING
# =============================================================================

# Apify pricing estimates (USD per unit) - based on Apify pricing tiers
APIFY_COSTS = {
    "google_search": 0.004,      # ~$0.004 per search result
    "post_reactions": 0.008,     # ~$0.008 per post scraped
    "profile_scraper": 0.025,    # ~$0.025 per profile scraped
}

# DeepSeek pricing (USD per 1M tokens) - very cheap
DEEPSEEK_COSTS = {
    "input_per_1m": 0.14,        # $0.14 per 1M input tokens
    "output_per_1m": 0.28,       # $0.28 per 1M output tokens
    "avg_icp_tokens": 400,       # ~400 tokens per ICP check (input+output)
    "avg_personalization_tokens": 800,  # ~800 tokens per personalization
}


class CostTracker:
    """Track costs across pipeline operations."""

    def __init__(self):
        self.costs = {
            "apify_google_search": 0.0,
            "apify_post_reactions": 0.0,
            "apify_profile_scraper": 0.0,
            "deepseek_icp": 0.0,
            "deepseek_personalization": 0.0,
        }
        self.counts = {
            "google_results": 0,
            "posts_scraped": 0,
            "profiles_scraped": 0,
            "icp_checks": 0,
            "personalizations": 0,
        }

    def add_google_search(self, num_results: int):
        self.counts["google_results"] += num_results
        self.costs["apify_google_search"] += num_results * APIFY_COSTS["google_search"]

    def add_post_reactions(self, num_posts: int):
        self.counts["posts_scraped"] += num_posts
        self.costs["apify_post_reactions"] += num_posts * APIFY_COSTS["post_reactions"]

    def add_profile_scrape(self, num_profiles: int):
        self.counts["profiles_scraped"] += num_profiles
        self.costs["apify_profile_scraper"] += num_profiles * APIFY_COSTS["profile_scraper"]

    def add_icp_check(self, num_checks: int = 1):
        self.counts["icp_checks"] += num_checks
        tokens = num_checks * DEEPSEEK_COSTS["avg_icp_tokens"]
        cost = (tokens / 1_000_000) * (DEEPSEEK_COSTS["input_per_1m"] + DEEPSEEK_COSTS["output_per_1m"]) / 2
        self.costs["deepseek_icp"] += cost

    def add_personalization(self, num_msgs: int = 1):
        self.counts["personalizations"] += num_msgs
        tokens = num_msgs * DEEPSEEK_COSTS["avg_personalization_tokens"]
        cost = (tokens / 1_000_000) * (DEEPSEEK_COSTS["input_per_1m"] + DEEPSEEK_COSTS["output_per_1m"]) / 2
        self.costs["deepseek_personalization"] += cost

    def get_total(self) -> float:
        return sum(self.costs.values())

    def get_summary(self) -> str:
        lines = [
            "COST BREAKDOWN",
            "=" * 40,
            f"Apify Google Search:    ${self.costs['apify_google_search']:.4f}  ({self.counts['google_results']} results)",
            f"Apify Post Reactions:   ${self.costs['apify_post_reactions']:.4f}  ({self.counts['posts_scraped']} posts)",
            f"Apify Profile Scraper:  ${self.costs['apify_profile_scraper']:.4f}  ({self.counts['profiles_scraped']} profiles)",
            f"DeepSeek ICP:           ${self.costs['deepseek_icp']:.4f}  ({self.counts['icp_checks']} checks)",
            f"DeepSeek Personalize:   ${self.costs['deepseek_personalization']:.4f}  ({self.counts['personalizations']} msgs)",
            "-" * 40,
            f"TOTAL:                  ${self.get_total():.4f}",
            "=" * 40,
        ]
        return "\n".join(lines)


# Global cost tracker instance
cost_tracker = CostTracker()


# =============================================================================
# MODULE 1: GOOGLE SEARCH FOR LINKEDIN POSTS
# =============================================================================

def build_google_search_query(keywords: str, days_back: int = 7) -> str:
    """
    Build a Google search query for LinkedIn posts.

    Args:
        keywords: Search keywords (e.g., "ceos", "founders")
        days_back: Number of days to look back

    Returns:
        Formatted Google search query string
    """
    # Calculate date filter
    date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    # Build query matching n8n workflow format
    query = f'site:linkedin.com/posts "{keywords}" after:{date_cutoff}'

    return query


def extract_reaction_count(reaction_str: Optional[str]) -> int:
    """
    Extract numeric reaction count from string like "150+ reactions".

    Args:
        reaction_str: String containing reaction count

    Returns:
        Integer count of reactions
    """
    if not reaction_str:
        return 0

    # Match patterns like "150+ reactions", "1,234+ reactions"
    match = re.search(r'([\d,]+)\+?\s*reactions?', str(reaction_str), re.IGNORECASE)
    if match:
        # Remove commas and convert to int
        return int(match.group(1).replace(',', ''))

    return 0


def filter_posts_by_reactions(posts: List[Dict], min_reactions: int = 50) -> List[Dict]:
    r"""
    Filter posts to keep only those with minimum reactions.

    Uses regex pattern from n8n workflow: ^([5-9][0-9]|[1-9][0-9]{2,})\+ reactions

    Args:
        posts: List of post dictionaries with 'followersAmount' field
        min_reactions: Minimum number of reactions required

    Returns:
        Filtered list of posts
    """
    filtered = []
    no_reaction_data = True

    for post in posts:
        # Check multiple possible fields for reaction counts
        reaction_str = post.get("followersAmount", "") or post.get("description", "") or ""
        count = extract_reaction_count(reaction_str)

        if count > 0:
            no_reaction_data = False
            if count >= min_reactions:
                filtered.append(post)
        else:
            # If no reaction data, check if it's a LinkedIn post URL and include it
            url = post.get("url", post.get("link", ""))
            if "linkedin.com/posts" in url:
                filtered.append(post)

    # If no reaction data was found at all, return all LinkedIn posts
    if no_reaction_data and filtered:
        print(f"  Note: No reaction data in search results, including all {len(filtered)} LinkedIn posts")

    return filtered


def search_google_linkedin_posts(
    keywords: str,
    days_back: int = 7,
    max_pages: int = 1,
    results_per_page: int = 10
) -> List[Dict]:
    """
    Search Google for LinkedIn posts using Apify.

    Args:
        keywords: Search keywords
        days_back: Days to look back
        max_pages: Maximum pages per query
        results_per_page: Results per page

    Returns:
        List of search results
    """
    if not APIFY_API_TOKEN:
        print("Error: APIFY_API_TOKEN not found in .env")
        return []

    try:
        from apify_client import ApifyClient
        client = ApifyClient(APIFY_API_TOKEN)
    except ImportError:
        print("Error: apify-client not installed. Run: pip install apify-client")
        return []

    query = build_google_search_query(keywords, days_back)

    print(f"Searching Google for LinkedIn posts: {query}")

    run_input = {
        "queries": query,
        "maxPagesPerQuery": max_pages,
        "resultsPerPage": results_per_page,
        "mobileResults": False
    }

    try:
        run = client.actor(GOOGLE_SEARCH_ACTOR).call(run_input=run_input)

        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(item)

        print(f"Found {len(results)} search results")
        cost_tracker.add_google_search(len(results))
        return results

    except Exception as e:
        print(f"Error searching Google: {e}")
        return []


# =============================================================================
# MODULE 2: POST ENGAGERS SCRAPER
# =============================================================================

def aggregate_profile_urls(engagers: List[Dict]) -> List[str]:
    """
    Aggregate profile URLs from post engagers.

    Args:
        engagers: List of engager dictionaries

    Returns:
        List of profile URLs
    """
    urls = []

    for engager in engagers:
        reactor = engager.get("reactor", {})
        profile_url = reactor.get("profile_url", "")

        if profile_url:
            urls.append(profile_url)

    return urls


def deduplicate_profile_urls(urls: List[str]) -> List[str]:
    """
    Remove duplicate profile URLs while preserving order.

    Args:
        urls: List of profile URLs

    Returns:
        List of unique profile URLs
    """
    seen = set()
    unique = []

    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    return unique


def scrape_post_engagers(post_urls: List[str]) -> List[Dict]:
    """
    Scrape engagers (reactions) from LinkedIn posts using Apify.

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
        print(f"Scraping engagers from: {url}")

        run_input = {
            "post_urls": [url]
        }

        try:
            run = client.actor(POST_REACTIONS_ACTOR).call(run_input=run_input)

            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                all_engagers.append(item)

            cost_tracker.add_post_reactions(1)

        except Exception as e:
            print(f"Error scraping post engagers: {e}")

    print(f"Found {len(all_engagers)} total engagers")
    return all_engagers


# =============================================================================
# MODULE 3: LINKEDIN PROFILE SCRAPER
# =============================================================================

def scrape_linkedin_profiles(
    profile_urls: List[str],
    wait_seconds: int = 120,
    poll_interval: int = 30
) -> List[Dict]:
    """
    Scrape LinkedIn profiles using Apify.

    Args:
        profile_urls: List of profile URLs to scrape
        wait_seconds: Initial wait time for scraper
        poll_interval: Polling interval to check completion

    Returns:
        List of profile dictionaries
    """
    if not APIFY_API_TOKEN:
        print("Error: APIFY_API_TOKEN not found in .env")
        return []

    import requests

    print(f"Starting LinkedIn profile scraper for {len(profile_urls)} profiles...")

    # Start the actor run
    start_url = f"https://api.apify.com/v2/acts/{PROFILE_SCRAPER_ACTOR}/runs?token={APIFY_API_TOKEN}"

    payload = {
        "profileUrls": profile_urls
    }

    try:
        response = requests.post(start_url, json=payload)
        response.raise_for_status()
        run_data = response.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        print(f"Run started: {run_id}")

    except Exception as e:
        print(f"Error starting profile scraper: {e}")
        return []

    # Wait for initial scraping
    print(f"Waiting {wait_seconds}s for scraping...")
    time.sleep(wait_seconds)

    # Poll for completion
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_API_TOKEN}"

    while True:
        try:
            response = requests.get(status_url)
            response.raise_for_status()
            status = response.json()["data"]["status"]

            if status in ["SUCCEEDED", "ABORTED"]:
                print(f"Scraper finished with status: {status}")
                break

            print(f"Status: {status}, waiting {poll_interval}s...")
            time.sleep(poll_interval)

        except Exception as e:
            print(f"Error polling status: {e}")
            break

    # Fetch results
    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_TOKEN}"

    try:
        response = requests.get(data_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        profiles = response.json()

        print(f"Retrieved {len(profiles)} profiles")
        cost_tracker.add_profile_scrape(len(profiles))
        return profiles

    except Exception as e:
        print(f"Error fetching profile data: {e}")
        return []


# =============================================================================
# MODULE 4: LOCATION FILTER
# =============================================================================

def filter_by_location(
    profiles: List[Dict],
    allowed_countries: List[str]
) -> List[Dict]:
    """
    Filter profiles by location (country).

    Args:
        profiles: List of profile dictionaries
        allowed_countries: List of allowed country names/variations

    Returns:
        Filtered list of profiles
    """
    filtered = []

    # Normalize allowed countries for comparison
    allowed_normalized = [c.lower() for c in allowed_countries]

    for profile in profiles:
        country = profile.get("addressCountryOnly", "")

        if country and country.lower() in allowed_normalized:
            filtered.append(profile)

    print(f"Location filter: {len(profiles)} -> {len(filtered)} profiles")
    return filtered


# =============================================================================
# MODULE 5: ICP QUALIFICATION (Reusing DeepSeek ICP from personalize_and_upload.py)
# =============================================================================

# Authority titles that qualify (for local fallback)
QUALIFIED_TITLES = [
    "ceo", "founder", "co-founder", "cofounder",
    "managing director", "owner", "partner",
    "president", "vp", "vice president",
    "cto", "cfo", "coo", "cmo", "chief"
]

# Titles that are rejected (for local fallback)
REJECTED_TITLES = [
    "intern", "student", "junior", "associate",
    "assistant", "trainee", "apprentice",
    "driver", "technician", "cashier"
]

# Industries that are rejected (for local fallback)
REJECTED_INDUSTRIES = [
    "banking", "financial services",
    "insurance", "retail"
]

# Industries that qualify (for local fallback)
QUALIFIED_INDUSTRIES = [
    "software", "saas", "technology", "tech",
    "agency", "marketing", "consulting",
    "coaching", "professional services"
]

# Company names that are rejected (for local fallback)
REJECTED_COMPANIES = [
    "santander", "getnet", "jpmorgan", "wells fargo",
    "bank of america", "citi", "hsbc"
]


def check_icp_authority(lead: Dict) -> Dict[str, Any]:
    """
    Check if lead has authority based on job title (local fallback).

    Args:
        lead: Lead dictionary with jobTitle

    Returns:
        Dict with 'qualified' boolean and 'reason'
    """
    title = (lead.get("jobTitle") or lead.get("job_title") or lead.get("headline") or "").lower()

    # Check for rejected titles first
    for rejected in REJECTED_TITLES:
        if rejected in title:
            return {
                "qualified": False,
                "reason": f"Rejected title: {rejected}"
            }

    # Check for qualified titles
    for qualified in QUALIFIED_TITLES:
        if qualified in title:
            return {
                "qualified": True,
                "reason": f"Qualified title: {qualified}"
            }

    # Benefit of doubt - if unclear, qualify
    return {
        "qualified": True,
        "reason": "Benefit of doubt - title not clearly rejected"
    }


def check_icp_industry(lead: Dict) -> Dict[str, Any]:
    """
    Check if lead's industry qualifies (local fallback).

    Args:
        lead: Lead dictionary with companyIndustry and companyName

    Returns:
        Dict with 'qualified' boolean and 'reason'
    """
    industry = (lead.get("companyIndustry") or lead.get("industry") or "").lower()
    company = (lead.get("companyName") or lead.get("company") or "").lower()

    # Check for rejected companies (hard rejection)
    for rejected in REJECTED_COMPANIES:
        if rejected in company:
            return {
                "qualified": False,
                "reason": f"Hard rejection: company {rejected}"
            }

    # Check for rejected industries
    for rejected in REJECTED_INDUSTRIES:
        if rejected in industry:
            return {
                "qualified": False,
                "reason": f"Rejected industry: {rejected}"
            }

    # Check for qualified industries
    for qualified in QUALIFIED_INDUSTRIES:
        if qualified in industry:
            return {
                "qualified": True,
                "reason": f"Qualified industry: {qualified}"
            }

    # Benefit of doubt
    return {
        "qualified": True,
        "reason": "Benefit of doubt - industry not clearly rejected"
    }


def qualify_lead_icp(lead: Dict) -> Dict[str, Any]:
    """
    Full ICP qualification combining authority and industry checks (local fallback).

    Args:
        lead: Lead dictionary

    Returns:
        Dict with 'qualified' boolean, 'reason', and original lead data
    """
    authority = check_icp_authority(lead)
    industry = check_icp_industry(lead)

    # Both must pass
    qualified = authority["qualified"] and industry["qualified"]

    if not authority["qualified"]:
        reason = authority["reason"]
    elif not industry["qualified"]:
        reason = industry["reason"]
    else:
        reason = f"{authority['reason']}; {industry['reason']}"

    return {
        "qualified": qualified,
        "reason": reason,
        **lead
    }


def check_icp_match_deepseek(lead: Dict, icp_criteria: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if lead matches ICP using DeepSeek (same logic as personalize_and_upload.py).
    Returns dict with 'match' (bool), 'confidence' (str), and 'reason' (str).

    Uses default ICP for Sales Automation and Personal Branding agency if not specified.
    """
    import requests

    if not DEEPSEEK_API_KEY:
        print("  Warning: DEEPSEEK_API_KEY not found, using local ICP rules")
        local_result = qualify_lead_icp(lead)
        return {
            "match": local_result["qualified"],
            "confidence": "local",
            "reason": local_result["reason"]
        }

    # Build lead summary (handle both Vayne and Apify field names)
    headline = lead.get('headline', 'N/A')
    company_desc = (lead.get('company_description') or lead.get('about') or '')[:300]

    lead_summary = f"""
Lead: {lead.get('fullName', lead.get('full_name', 'Unknown'))}
Title: {lead.get('jobTitle', lead.get('job_title', lead.get('title', 'Unknown')))}
Headline: {headline}
Company: {lead.get('companyName', lead.get('company', lead.get('company_name', 'Unknown')))}
Company Description: {company_desc if company_desc else 'N/A'}
Location: {lead.get('addressWithCountry', lead.get('location', 'Unknown'))}
Industry: {lead.get('companyIndustry', lead.get('industry', 'N/A'))}
"""

    # Use custom ICP criteria if provided, otherwise use default
    if not icp_criteria:
        system_prompt = """Role: B2B Lead Qualification Filter.

Objective: Categorize LinkedIn profiles based on Authority and Industry fit for a Sales Automation and Personal Branding agency.

Rules for Authority (Strict):
- Qualify: CEOs, Founders, Co-Founders, Managing Directors, Owners, Partners, VPs, and C-Suite executives.
- Reject: Interns, Students, Junior staff, Administrative assistants (e.g., "Assessor administrativo"), and low-level individual contributors.

Rules for B2B Industry (Lenient):
- Qualify: High-ticket service industries (Agencies, SaaS, Consulting, Coaching, Tech).

The "Benefit of Doubt" Rule: If you are unsure if a business is B2B or B2C, or unsure if the person is a top-level decision-maker, Qualify them (Set to true). Only reject if they are clearly non-decision makers or in non-business roles.

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
    else:
        system_prompt = "You are an expert at evaluating sales leads against ICP criteria. Always respond with valid JSON."
        user_prompt = f"""You are verifying if a LinkedIn lead matches the Ideal Customer Profile (ICP).

ICP Criteria: {icp_criteria}

Lead Information:
{lead_summary}

Task: Determine if this lead matches the ICP.

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

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        result_text = data["choices"][0]["message"]["content"]
        result = json.loads(result_text)
        return result

    except Exception as e:
        print(f"  Warning: DeepSeek ICP error: {e}")
        # Default to local rules if API fails (benefit of doubt)
        local_result = qualify_lead_icp(lead)
        return {
            "match": local_result["qualified"],
            "confidence": "error",
            "reason": str(e)
        }


def qualify_leads_with_deepseek(leads: List[Dict], icp_criteria: Optional[str] = None) -> List[Dict]:
    """
    Qualify leads using DeepSeek API (same as personalize_and_upload.py).

    Args:
        leads: List of lead dictionaries
        icp_criteria: Optional custom ICP criteria

    Returns:
        List of leads that pass ICP qualification with icp_* fields added
    """
    qualified_leads = []

    for idx, lead in enumerate(leads):
        lead_name = lead.get('fullName', lead.get('full_name', 'Unknown'))

        # Check ICP with DeepSeek
        icp_result = check_icp_match_deepseek(lead, icp_criteria)
        cost_tracker.add_icp_check(1)

        lead["icp_match"] = icp_result.get("match", True)
        lead["icp_confidence"] = icp_result.get("confidence", "unknown")
        lead["icp_reason"] = icp_result.get("reason", "")

        if icp_result.get("match", True):
            qualified_leads.append(lead)
            print(f"  [OK] #{idx+1}: {lead_name}")
        else:
            print(f"  [ICP-REJECT] #{idx+1}: {lead_name} - {icp_result.get('reason', '')}")

    print(f"\nICP qualification: {len(leads)} -> {len(qualified_leads)} leads")
    return qualified_leads


# =============================================================================
# MODULE 6: PERSONALIZATION (Using DeepSeek instead of OpenAI)
# =============================================================================

def casualize_company_name(company: str) -> str:
    """
    Casualize company name by removing suffixes and optionally abbreviating.

    Args:
        company: Full company name

    Returns:
        Casualized company name
    """
    if not company:
        return ""

    # Remove common suffixes
    suffixes = [
        ", Inc.", ", Inc", ", LLC", ", LTD", ", Ltd",
        " Inc.", " Inc", " LLC", " LTD", " Ltd",
        ", Corp", " Corp", " Corporation",
        " PLC", " plc", " Limited"
    ]

    for suffix in suffixes:
        if company.endswith(suffix):
            company = company[:-len(suffix)]

    # Clean up trailing commas/spaces
    company = company.strip().rstrip(',').strip()

    # Check if should abbreviate (3+ words)
    words = company.split()
    if len(words) >= 3:
        # Create abbreviation from first letters
        abbreviation = ''.join(w[0].upper() for w in words if w[0].isalpha())
        if len(abbreviation) >= 2:
            return abbreviation

    return company


def extract_city_from_location(location: str) -> str:
    """
    Extract city from full location string.

    Args:
        location: Full location like "San Francisco, California, United States"

    Returns:
        City name
    """
    if not location:
        return ""

    # Split by comma and take first part
    parts = location.split(',')
    return parts[0].strip()


def generate_mock_personalization(lead: Dict) -> str:
    """
    Generate a mock personalized message (for testing without API).

    Args:
        lead: Lead dictionary

    Returns:
        Personalized message string
    """
    first_name = lead.get("firstName", lead.get("first_name", "there"))
    company = casualize_company_name(lead.get("companyName", lead.get("company", "your company")))
    location = extract_city_from_location(lead.get("addressWithCountry", lead.get("location", "")))

    message = f"""Hey {first_name}

{company} looks interesting

You guys do consulting right? Do that w LinkedIn + email? Or what

Outbound is a tough nut to crack.
Really comes down to precise targeting + personalisation to book clients at a high level.

See you're in {location}. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland"""

    return message


def generate_personalization_deepseek(lead: Dict) -> str:
    """
    Generate personalized LinkedIn DM using DeepSeek.
    Uses the centralized 5-line template from prompts.py.

    Args:
        lead: Lead dictionary with profile information

    Returns:
        Personalized message string
    """
    import requests

    if not DEEPSEEK_API_KEY:
        print("  Warning: DEEPSEEK_API_KEY not found, using mock personalization")
        return generate_mock_personalization(lead)

    # Handle both Vayne and Apify field names
    first_name = lead.get("firstName", lead.get("first_name", ""))
    if not first_name:
        full_name = lead.get("fullName", lead.get("full_name", ""))
        first_name = full_name.split()[0] if full_name else "there"

    company = casualize_company_name(lead.get("companyName", lead.get("company", lead.get("company_name", ""))))
    title = lead.get("jobTitle", lead.get("job_title", lead.get("title", "")))
    headline = lead.get("headline", lead.get("jobTitle", ""))
    company_description = (lead.get("companyDescription") or lead.get("about") or lead.get("summary") or "")[:200]
    location = extract_city_from_location(lead.get("addressWithCountry", lead.get("location", "")))

    # Get formatted prompt from centralized source (prompts.py)
    prompt = get_linkedin_5_line_prompt(
        first_name=first_name,
        company_name=company,
        title=title,
        headline=headline,
        company_description=company_description,
        location=location
    )

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400,
            "temperature": 0.7
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        message = response.json()["choices"][0]["message"]["content"].strip()

        # Clean up any formatting artifacts
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        message = message.replace("```", "").strip()

        cost_tracker.add_personalization(1)
        return message

    except Exception as e:
        print(f"  Warning: DeepSeek personalization error: {e}")
        return generate_mock_personalization(lead)


# =============================================================================
# MODULE 7: HEYREACH UPLOAD
# =============================================================================

def format_lead_for_heyreach(
    lead: Dict,
    custom_fields: List[str] = None
) -> Dict:
    """
    Format a lead for HeyReach API.

    Args:
        lead: Lead dictionary
        custom_fields: List of custom field names to include

    Returns:
        Formatted lead dictionary for HeyReach
    """
    if custom_fields is None:
        custom_fields = ["personalized_message"]

    formatted = {
        "firstName": lead.get("firstName") or lead.get("first_name") or "",
        "lastName": lead.get("lastName") or lead.get("last_name") or "",
        "profileUrl": lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("profileUrl") or "",
    }

    # Optional fields
    if lead.get("companyName"):
        formatted["companyName"] = lead["companyName"]

    if lead.get("jobTitle"):
        formatted["position"] = lead["jobTitle"]

    if lead.get("email"):
        formatted["emailAddress"] = lead["email"]

    if lead.get("addressWithCountry"):
        formatted["location"] = lead["addressWithCountry"]

    if lead.get("about"):
        formatted["summary"] = lead["about"]

    # Custom fields
    custom_user_fields = []
    for field_name in custom_fields:
        field_value = lead.get(field_name, "")
        if field_value:
            custom_user_fields.append({
                "name": field_name,
                "value": str(field_value)
            })

    if custom_user_fields:
        formatted["customUserFields"] = custom_user_fields

    return formatted


def upload_to_heyreach(
    leads: List[Dict],
    list_id: int,
    custom_fields: List[str] = None
) -> int:
    """
    Upload leads to HeyReach list.

    Args:
        leads: List of lead dictionaries
        list_id: HeyReach list ID
        custom_fields: Custom field names to include

    Returns:
        Number of successfully uploaded leads
    """
    if not HEYREACH_API_KEY:
        print("Error: HEYREACH_API_KEY not found in .env")
        return 0

    import requests

    if custom_fields is None:
        custom_fields = ["personalized_message"]

    # Format leads
    formatted_leads = [
        format_lead_for_heyreach(lead, custom_fields)
        for lead in leads
    ]

    print(f"Uploading {len(formatted_leads)} leads to HeyReach list {list_id}...")

    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = "https://api.heyreach.io/api/public/list/AddLeadsToListV2"

    # Upload in chunks
    chunk_size = 100
    total_uploaded = 0

    for i in range(0, len(formatted_leads), chunk_size):
        chunk = formatted_leads[i:i+chunk_size]

        payload = {
            "leads": chunk,
            "listId": list_id
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            total_uploaded += len(chunk)
            print(f"  Uploaded {total_uploaded}/{len(formatted_leads)}...")

        except Exception as e:
            print(f"  Error uploading chunk: {e}")

    print(f"Successfully uploaded {total_uploaded} leads")
    return total_uploaded


# =============================================================================
# MODULE 8: MAIN PIPELINE
# =============================================================================

def process_leads_pipeline(
    profiles: List[Dict],
    allowed_countries: List[str],
    skip_api_calls: bool = False
) -> List[Dict]:
    """
    Process leads through the pipeline (for testing).

    Args:
        profiles: List of profile dictionaries
        allowed_countries: Countries to allow
        skip_api_calls: If True, skip DeepSeek API calls

    Returns:
        List of qualified leads
    """
    # Filter by location
    location_filtered = filter_by_location(profiles, allowed_countries)

    if skip_api_calls:
        # Use local ICP rules only
        qualified = []
        for lead in location_filtered:
            result = qualify_lead_icp(lead)
            if result["qualified"]:
                lead["icp_qualified"] = True
                lead["icp_reason"] = result["reason"]
                qualified.append(lead)
        return qualified

    # Use DeepSeek for qualification
    return qualify_leads_with_deepseek(location_filtered)


def run_full_pipeline(
    keywords: str = "ceos",
    days_back: int = 7,
    min_reactions: int = 50,
    allowed_countries: List[str] = None,
    heyreach_list_id: int = None,
    dry_run: bool = False,
    skip_icp: bool = False
) -> Dict[str, Any]:
    """
    Run the full competitor post pipeline.

    Args:
        keywords: Search keywords
        days_back: Days to look back
        min_reactions: Minimum reactions threshold
        allowed_countries: Allowed country list
        skip_icp: Skip ICP filtering (accept all location-filtered leads)
        heyreach_list_id: HeyReach list ID for upload
        dry_run: If True, don't upload to HeyReach

    Returns:
        Pipeline results dictionary
    """
    if allowed_countries is None:
        allowed_countries = ["United States", "Canada", "USA", "America"]

    config = get_default_config()

    print("=" * 60)
    print("COMPETITOR POST PIPELINE")
    print("=" * 60)
    print(f"Keywords: {keywords}")
    print(f"Days back: {days_back}")
    print(f"Min reactions: {min_reactions}")
    print(f"Target countries: {', '.join(allowed_countries)}")
    print(f"HeyReach list ID: {heyreach_list_id}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    results = {
        "posts_found": 0,
        "posts_filtered": 0,
        "engagers_found": 0,
        "profiles_scraped": 0,
        "location_filtered": 0,
        "icp_qualified": 0,
        "personalized": 0,
        "uploaded": 0
    }

    # Step 1: Search Google for LinkedIn posts
    print("\n[1/7] Searching Google for LinkedIn posts...")
    search_results = search_google_linkedin_posts(keywords, days_back)
    results["posts_found"] = len(search_results)

    if not search_results:
        print("No posts found. Exiting.")
        return results

    # Step 2: Filter by reactions
    print("\n[2/7] Filtering posts by reactions...")

    # Extract organic results if nested
    posts = []
    for result in search_results:
        if "organicResults" in result:
            if isinstance(result["organicResults"], list):
                posts.extend(result["organicResults"])
            else:
                posts.append(result["organicResults"])
        else:
            posts.append(result)

    filtered_posts = filter_posts_by_reactions(posts, min_reactions)
    results["posts_filtered"] = len(filtered_posts)

    if not filtered_posts:
        print("No posts meet reaction threshold. Exiting.")
        return results

    # Step 3: Scrape post engagers
    print("\n[3/7] Scraping post engagers...")
    post_urls = [p.get("url", p.get("link", "")) for p in filtered_posts if p.get("url") or p.get("link")]
    engagers = scrape_post_engagers(post_urls)
    results["engagers_found"] = len(engagers)

    if not engagers:
        print("No engagers found. Exiting.")
        return results

    # Step 4: Aggregate and deduplicate profile URLs
    print("\n[4/7] Aggregating profile URLs...")
    profile_urls = aggregate_profile_urls(engagers)
    profile_urls = deduplicate_profile_urls(profile_urls)
    print(f"Found {len(profile_urls)} unique profile URLs")

    # Step 5: Scrape LinkedIn profiles
    print("\n[5/7] Scraping LinkedIn profiles...")
    profiles = scrape_linkedin_profiles(
        profile_urls,
        wait_seconds=config["scrape_wait_seconds"],
        poll_interval=config["poll_interval_seconds"]
    )
    results["profiles_scraped"] = len(profiles)

    if not profiles:
        print("No profiles scraped. Exiting.")
        return results

    # Step 6: Filter by location
    print("\n[6/7] Filtering by location...")
    location_filtered = filter_by_location(profiles, allowed_countries)
    results["location_filtered"] = len(location_filtered)

    if not location_filtered:
        print("No leads in target locations. Exiting.")
        return results

    # Step 7: ICP qualification
    if skip_icp:
        print("\n[7/7] Skipping ICP qualification (--skip_icp flag)...")
        qualified_leads = location_filtered
        for lead in qualified_leads:
            lead["icp_match"] = True
            lead["icp_confidence"] = "skipped"
            lead["icp_reason"] = "ICP check skipped"
    else:
        print("\n[7/7] Qualifying leads (ICP)...")
        qualified_leads = qualify_leads_with_deepseek(location_filtered)

    results["icp_qualified"] = len(qualified_leads)

    if not qualified_leads:
        print("No leads passed ICP qualification. Exiting.")
        return results

    # Step 8: Generate personalization
    print("\n[8/8] Generating personalized messages...")
    for lead in qualified_leads:
        lead["personalized_message"] = generate_personalization_deepseek(lead)
    results["personalized"] = len(qualified_leads)

    # Step 9: Upload to HeyReach
    if not dry_run and heyreach_list_id:
        print("\n[9/9] Uploading to HeyReach...")
        uploaded = upload_to_heyreach(
            qualified_leads,
            heyreach_list_id,
            custom_fields=["personalized_message"]
        )
        results["uploaded"] = uploaded
    else:
        print("\n[9/9] Skipping HeyReach upload (dry run)")

    # Save intermediate results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f".tmp/competitor_post_leads_{timestamp}.json"
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

    # Cost breakdown
    print("\n" + cost_tracker.get_summary())

    return results


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Competitor Post Pipeline - Find leads from LinkedIn post engagers"
    )
    parser.add_argument(
        "--keywords", default="ceos",
        help="Search keywords (default: 'ceos')"
    )
    parser.add_argument(
        "--days_back", type=int, default=7,
        help="Days to look back (default: 7)"
    )
    parser.add_argument(
        "--min_reactions", type=int, default=50,
        help="Minimum reactions threshold (default: 50)"
    )
    parser.add_argument(
        "--countries", nargs="+",
        default=["United States", "Canada"],
        help="Allowed countries (default: 'United States' 'Canada')"
    )
    parser.add_argument(
        "--list_id", type=int, default=480247,
        help="HeyReach list ID (default: 480247)"
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Don't upload to HeyReach (for testing)"
    )
    parser.add_argument(
        "--skip_icp", action="store_true",
        help="Skip ICP filtering (accept all location-filtered leads)"
    )

    args = parser.parse_args()

    results = run_full_pipeline(
        keywords=args.keywords,
        days_back=args.days_back,
        min_reactions=args.min_reactions,
        allowed_countries=args.countries,
        heyreach_list_id=args.list_id,
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
