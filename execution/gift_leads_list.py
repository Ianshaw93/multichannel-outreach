#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift Leads List Pipeline - Research a prospect's ICP and find qualified leads
from LinkedIn post engagers as a value-add gift.

Data Flow:
1. Scrape prospect profile (Apify, cached)
2. Research prospect's business -> derive ICP + pain points (DeepSeek)
3. Generate 3-5 Google search queries (DeepSeek)
4. Search Google for LinkedIn posts (Apify)
5. Filter posts by reactions (50+)
6. Scrape post engagers (Apify)
7. Pre-filter by headline (language + keyword rejection)
8. Deduplicate + scrape profiles (Apify, cached)
9. Filter: location + profile completeness
10. ICP qualify against prospect's dynamic ICP (DeepSeek)
11. Generate signal notes per lead (DeepSeek)
12. Export JSON + CSV -> .tmp/

Usage:
    python execution/gift_leads_list.py \
      --prospect-url "https://linkedin.com/in/johndoe" \
      [--icp "B2B SaaS founders, 10-50 employees"] \
      [--pain-points "outbound pipeline, lead gen"] \
      [--days-back 14] [--min-reactions 50] \
      [--countries "United States" "Canada"] \
      [--min-leads 10] [--max-leads 25] \
      [--dry-run] [--skip-research]
"""

import os
import sys
import json
import csv
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# API Keys
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Apify Actor IDs (reuse from competitor_post_pipeline)
GOOGLE_SEARCH_ACTOR = "nFJndFXA5zjCTuudP"
POST_REACTIONS_ACTOR = "J9UfswnR3Kae4O6vm"
PROFILE_SCRAPER_ACTOR = "supreme_coder~linkedin-profile-scraper"

# Import shared functions from competitor_post_pipeline
from competitor_post_pipeline import (
    search_google_linkedin_posts,
    filter_posts_by_reactions,
    scrape_post_engagers,
    aggregate_profile_urls,
    deduplicate_profile_urls,
    build_engagement_context,
    enrich_profiles_with_engagement,
    prefilter_engagers_by_headline,
    scrape_linkedin_profiles,
    normalize_linkedin_url,
    load_profile_cache,
    save_profile_cache,
    filter_by_location,
    is_profile_complete,
    filter_complete_profiles,
    check_icp_match_deepseek,
    qualify_leads_with_deepseek,
    CostTracker,
    casualize_company_name,
    extract_city_from_location,
    APIFY_COSTS,
    DEEPSEEK_COSTS,
)

from prompts import (
    get_prospect_research_prompt,
    get_gift_search_query_prompt,
    get_gift_signal_note_prompt,
)


# =============================================================================
# COST TRACKER (separate instance for gift pipeline)
# =============================================================================

cost_tracker = CostTracker()


# =============================================================================
# ACTIVITY SCORING HELPERS
# =============================================================================

def compute_activity_score(profile: Dict) -> float:
    """Compute activity score from LinkedIn profile data.

    Score formula (0-100):
    - Connection count: 30 points max (500+ connections = 30)
    - Follower count: 30 points max (1000+ followers = 30)
    - Is creator (has posts): 20 points
    - Has engagement context: 20 points

    Args:
        profile: LinkedIn profile dict from Apify scraper

    Returns:
        Activity score as float (0-100)
    """
    score = 0.0

    # Connection count (30 points max)
    connections = profile.get("connectionsCount") or profile.get("connection_count") or 0
    if isinstance(connections, str):
        connections = int(connections.replace(",", "").replace("+", "")) if connections.strip() else 0
    score += min(30, (connections / 500) * 30)

    # Follower count (30 points max)
    followers = profile.get("followersCount") or profile.get("follower_count") or 0
    if isinstance(followers, str):
        followers = int(followers.replace(",", "").replace("+", "")) if followers.strip() else 0
    score += min(30, (followers / 1000) * 30)

    # Is creator - has posts/articles (20 points)
    is_creator = profile.get("isCreator") or profile.get("is_creator") or False
    if not is_creator:
        # Check if they have posts as a proxy
        posts = profile.get("posts") or profile.get("articles") or []
        is_creator = len(posts) > 0 if isinstance(posts, list) else bool(posts)
    if is_creator:
        score += 20

    # Has engagement context (20 points)
    has_engagement = bool(profile.get("engagement_type") or profile.get("engagement_comment"))
    if has_engagement:
        score += 20

    return round(score, 2)


def extract_activity_fields(profile: Dict) -> Dict:
    """Extract activity-related fields from a profile for DB sync.

    Args:
        profile: LinkedIn profile dict

    Returns:
        Dict with connection_count, follower_count, is_creator, activity_score
    """
    connections = profile.get("connectionsCount") or profile.get("connection_count") or 0
    if isinstance(connections, str):
        connections = int(connections.replace(",", "").replace("+", "")) if connections.strip() else 0

    followers = profile.get("followersCount") or profile.get("follower_count") or 0
    if isinstance(followers, str):
        followers = int(followers.replace(",", "").replace("+", "")) if followers.strip() else 0

    is_creator = profile.get("isCreator") or profile.get("is_creator") or False
    if not is_creator:
        posts = profile.get("posts") or profile.get("articles") or []
        is_creator = len(posts) > 0 if isinstance(posts, list) else bool(posts)

    return {
        "connection_count": connections if connections else None,
        "follower_count": followers if followers else None,
        "is_creator": is_creator if is_creator else None,
        "activity_score": compute_activity_score(profile),
    }


# =============================================================================
# RAW GOOGLE SEARCH (for pre-formed queries)
# =============================================================================

def search_google_raw_query(raw_query: str, max_pages: int = 1, results_per_page: int = 10) -> List[Dict]:
    """
    Search Google with a raw, pre-formed query string.
    Unlike search_google_linkedin_posts(), this does NOT wrap the query.

    Args:
        raw_query: Complete Google search query (already includes site:, after:, etc.)
        max_pages: Max pages per query
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

    print(f"  Searching: {raw_query}")

    run_input = {
        "queries": raw_query,
        "maxPagesPerQuery": max_pages,
        "resultsPerPage": results_per_page,
        "mobileResults": False,
    }

    try:
        run = client.actor(GOOGLE_SEARCH_ACTOR).call(run_input=run_input)
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  Found {len(results)} results")
        cost_tracker.add_google_search(len(results))
        return results
    except Exception as e:
        print(f"  Error searching Google: {e}")
        return []


# =============================================================================
# MODULE 1: PROSPECT PROFILE SCRAPING
# =============================================================================

def scrape_prospect_profile(url: str) -> Optional[Dict]:
    """
    Scrape prospect's own LinkedIn profile (Apify, cache-aware).

    Args:
        url: LinkedIn profile URL

    Returns:
        Profile dictionary or None
    """
    cache = load_profile_cache()
    cache_key = normalize_linkedin_url(url)

    if cache_key in cache:
        print(f"Prospect profile found in cache: {cache_key}")
        return cache[cache_key]

    if not APIFY_API_TOKEN:
        print("Error: APIFY_API_TOKEN not found in .env")
        return None

    print(f"Scraping prospect profile: {url}")

    profiles = scrape_linkedin_profiles(
        [url],
        wait_seconds=60,
        poll_interval=15,
    )

    if profiles:
        # Update cost tracker for this pipeline instance
        cost_tracker.add_profile_scrape(1)
        profile = profiles[0]
        # Cache is already updated by scrape_linkedin_profiles
        return profile

    print("Warning: Could not scrape prospect profile")
    return None


# =============================================================================
# MODULE 2: PROSPECT BUSINESS RESEARCH (DeepSeek)
# =============================================================================

def research_prospect_business(
    profile: Dict,
    user_icp: Optional[str] = None,
    user_pain_points: Optional[str] = None,
) -> Dict:
    """
    Research prospect's business to derive ICP, pain points, and buying signals.

    Args:
        profile: Scraped LinkedIn profile dict
        user_icp: Optional user-provided ICP override
        user_pain_points: Optional user-provided pain points

    Returns:
        Dict with icp_description, target_titles, target_industries,
        pain_points, buying_signals, search_angles
    """
    import requests

    name = profile.get("fullName", profile.get("firstName", "Unknown"))
    headline = profile.get("headline", "")
    about = profile.get("about", "")
    company = profile.get("companyName", "")
    industry = profile.get("companyIndustry", "")

    # Format experiences
    experiences = profile.get("experiences", [])
    if experiences:
        exp_str = "; ".join(
            f"{e.get('title', '')} at {e.get('company', '')} ({e.get('duration', '')})"
            for e in experiences[:5]
        )
    else:
        exp_str = profile.get("jobTitle", "")

    prompt = get_prospect_research_prompt(
        name=name,
        headline=headline,
        about=about,
        company=company,
        industry=industry,
        experiences=exp_str,
        user_icp=user_icp,
        user_pain_points=user_pain_points,
    )

    if not DEEPSEEK_API_KEY:
        print("Warning: DEEPSEEK_API_KEY not found, using fallback research")
        return _fallback_research(profile, user_icp, user_pain_points)

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a B2B sales intelligence analyst. Always respond with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 500,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        result = json.loads(response.json()["choices"][0]["message"]["content"])
        cost_tracker.add_icp_check(1)

        # Validate required fields
        required = ["icp_description", "target_titles", "pain_points", "buying_signals"]
        for field in required:
            if field not in result:
                result[field] = []

        if "search_angles" not in result:
            result["search_angles"] = ["pain points", "hiring", "industry trends"]
        if "target_industries" not in result:
            result["target_industries"] = []
        if "target_verticals" not in result:
            result["target_verticals"] = []
        if "buyer_intent_phrases" not in result:
            result["buyer_intent_phrases"] = []

        print(f"Research complete: ICP = {result['icp_description'][:80]}...")
        return result

    except Exception as e:
        print(f"Warning: DeepSeek research error: {e}")
        return _fallback_research(profile, user_icp, user_pain_points)


def _fallback_research(
    profile: Dict,
    user_icp: Optional[str] = None,
    user_pain_points: Optional[str] = None,
) -> Dict:
    """Fallback research when DeepSeek is unavailable."""
    headline = profile.get("headline", "")
    industry = profile.get("companyIndustry", "")

    return {
        "icp_description": user_icp or f"Decision-makers in {industry or 'B2B services'}",
        "target_titles": ["CEO", "Founder", "Managing Director", "VP"],
        "target_industries": [industry] if industry else ["SaaS", "Agency", "Consulting"],
        "target_verticals": [],
        "pain_points": (
            user_pain_points.split(",") if user_pain_points
            else ["lead generation", "outbound sales", "scaling"]
        ),
        "buying_signals": ["discussing growth challenges", "hiring for sales roles"],
        "buyer_intent_phrases": [],
        "search_angles": ["pain points", "hiring", "industry trends"],
    }


# =============================================================================
# MODULE 3: SEARCH QUERY GENERATION (DeepSeek)
# =============================================================================

def generate_search_queries(research: Dict, days_back: int = 14,
                            prospect_profile: Optional[Dict] = None) -> List[str]:
    """
    Generate 9 Google search queries from ICP research across 3 angles.

    Args:
        research: Dict from research_prospect_business
        days_back: Days to look back
        prospect_profile: Optional prospect profile dict for context

    Returns:
        List of Google search query strings
    """
    import requests

    target_verticals = research.get("target_verticals", [])
    buyer_intent_phrases = research.get("buyer_intent_phrases", [])

    prompt = get_gift_search_query_prompt(
        icp_description=research.get("icp_description", ""),
        pain_points=research.get("pain_points", []),
        buying_signals=research.get("buying_signals", []),
        target_verticals=target_verticals,
        buyer_intent_phrases=buyer_intent_phrases,
        days_back=days_back,
        prospect_name=prospect_profile.get("fullName") if prospect_profile else None,
        prospect_headline=prospect_profile.get("headline") if prospect_profile else None,
        prospect_company=prospect_profile.get("companyName") if prospect_profile else None,
    )

    if not DEEPSEEK_API_KEY:
        print("Warning: DEEPSEEK_API_KEY not found, using fallback queries")
        return _fallback_search_queries(research, days_back)

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You generate Google search queries. Always respond with a valid JSON array of strings."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 400,
            "temperature": 0.5,
            "response_format": {"type": "json_object"},
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        cost_tracker.add_icp_check(1)

        # Handle both array and object with "queries" key
        if isinstance(result, list):
            queries = result
        elif isinstance(result, dict) and "queries" in result:
            queries = result["queries"]
        else:
            # Try to extract any list value
            for v in result.values():
                if isinstance(v, list):
                    queries = v
                    break
            else:
                queries = _fallback_search_queries(research, days_back)

        # Wrap each query with site: prefix and after: date suffix
        date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        validated = []
        for q in queries:
            if isinstance(q, str):
                q = q.strip()
                if "site:linkedin.com/posts" not in q:
                    q = f'site:linkedin.com/posts {q}'
                if "after:" not in q:
                    q = f'{q} after:{date_cutoff}'
                validated.append(q)

        print(f"Generated {len(validated)} search queries")
        for i, q in enumerate(validated, 1):
            print(f"  [{i}] {q}")
        return validated

    except Exception as e:
        print(f"Warning: DeepSeek query generation error: {e}")
        return _fallback_search_queries(research, days_back)


def _fallback_search_queries(research: Dict, days_back: int) -> List[str]:
    """Fallback search queries when DeepSeek is unavailable."""
    date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    pain_points = research.get("pain_points", ["lead generation", "outbound sales"])
    target_verticals = research.get("target_verticals", [])
    buyer_intent_phrases = research.get("buyer_intent_phrases", [])

    queries = []

    # Angle 1: Buyer intent phrases
    for phrase in buyer_intent_phrases[:2]:
        queries.append(f'site:linkedin.com/posts "{phrase}" after:{date_cutoff}')

    # Angle 2: Vertical-specific (use pain points + verticals)
    if target_verticals:
        for vertical in target_verticals[:3]:
            queries.append(f'site:linkedin.com/posts "{vertical}" after:{date_cutoff}')
    else:
        # Fall back to pain points if no verticals
        for pain in pain_points[:3]:
            queries.append(f'site:linkedin.com/posts "{pain}" after:{date_cutoff}')

    if not queries:
        queries.append(f'site:linkedin.com/posts "B2B" "growth" after:{date_cutoff}')

    return queries


# =============================================================================
# MODULE 4: SIGNAL NOTE GENERATION (DeepSeek)
# =============================================================================

def generate_signal_notes(leads: List[Dict], icp_description: str) -> List[Dict]:
    """
    Generate 1-line signal notes per lead using DeepSeek.

    Args:
        leads: List of qualified lead dicts
        icp_description: Prospect's ICP description

    Returns:
        Same leads list with 'signal_note' field added
    """
    import requests

    if not leads:
        return leads

    prompt = get_gift_signal_note_prompt(icp_description, leads)

    if not DEEPSEEK_API_KEY:
        print("Warning: DEEPSEEK_API_KEY not found, using fallback signal notes")
        return _fallback_signal_notes(leads)

    # Process in batches of 10 to stay within token limits
    batch_size = 10
    all_notes = {}

    for i in range(0, len(leads), batch_size):
        batch = leads[i:i + batch_size]
        batch_prompt = get_gift_signal_note_prompt(icp_description, batch)

        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You generate concise signal notes. Always respond with valid JSON."},
                    {"role": "user", "content": batch_prompt},
                ],
                "max_tokens": 800,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
            }

            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            cost_tracker.add_personalization(len(batch))

            # Handle both array and object with "notes"/"leads" key
            notes_list = result if isinstance(result, list) else (
                result.get("notes") or result.get("leads") or
                next((v for v in result.values() if isinstance(v, list)), [])
            )

            for note in notes_list:
                url = note.get("linkedin_url", "")
                signal = note.get("signal_note", "")
                if url and signal:
                    # Truncate to 100 chars
                    all_notes[normalize_linkedin_url(url)] = signal[:100]

        except Exception as e:
            print(f"Warning: Signal note batch error: {e}")

    # Apply notes to leads
    for lead in leads:
        url = lead.get("linkedinUrl") or lead.get("linkedin_url", "")
        key = normalize_linkedin_url(url)
        lead["signal_note"] = all_notes.get(key, _fallback_single_signal_note(lead))

    return leads


def _fallback_signal_notes(leads: List[Dict]) -> List[Dict]:
    """Fallback signal notes without DeepSeek."""
    for lead in leads:
        lead["signal_note"] = _fallback_single_signal_note(lead)
    return leads


def _fallback_single_signal_note(lead: Dict) -> str:
    """Generate a single fallback signal note."""
    eng_type = lead.get("engagement_type", "LIKE")
    action = "Liked" if eng_type == "LIKE" else "Engaged with"
    title = lead.get("jobTitle") or lead.get("title") or "professional"
    company = lead.get("companyName") or lead.get("company") or ""
    return f"{action} relevant post - {title} at {company}"[:100]


# =============================================================================
# MODULE 5: OUTPUT FORMATTING
# =============================================================================

def format_gift_leads_json(
    leads: List[Dict],
    prospect_name: str,
    prospect_url: str,
    icp_description: str,
    cost_tracker_instance: CostTracker,
) -> Dict:
    """
    Structure final JSON output with metadata.

    Args:
        leads: List of qualified leads
        prospect_name: Prospect's name
        prospect_url: Prospect's LinkedIn URL
        icp_description: Derived ICP description
        cost_tracker_instance: Cost tracker for cost breakdown

    Returns:
        Structured JSON dict
    """
    formatted_leads = []
    for lead in leads:
        formatted_leads.append({
            "name": lead.get("fullName") or lead.get("name", "Unknown"),
            "title": lead.get("jobTitle") or lead.get("title", ""),
            "company": lead.get("companyName") or lead.get("company", ""),
            "linkedin_url": lead.get("linkedinUrl") or lead.get("linkedin_url", ""),
            "location": lead.get("addressWithCountry") or lead.get("location", ""),
            "signal_note": lead.get("signal_note", ""),
            "source_post_url": lead.get("source_post_url", ""),
            "engagement_type": lead.get("engagement_type", "LIKE"),
            "icp_confidence": lead.get("icp_confidence", ""),
            "icp_reason": lead.get("icp_reason", ""),
        })

    return {
        "prospect": {
            "name": prospect_name,
            "url": prospect_url,
            "icp": icp_description,
        },
        "generated_at": datetime.now().isoformat(),
        "lead_count": len(formatted_leads),
        "cost": {
            "total": round(cost_tracker_instance.get_total(), 4),
            "breakdown": {k: round(v, 4) for k, v in cost_tracker_instance.costs.items()},
        },
        "leads": formatted_leads,
    }


def export_gift_leads_csv(leads: List[Dict], path: str):
    """
    Write CSV with clean columns.

    Args:
        leads: List of lead dicts (from format_gift_leads_json output's "leads" key)
        path: Output file path
    """
    if not leads:
        print("No leads to export to CSV")
        return

    fieldnames = [
        "name", "title", "company", "linkedin_url", "location",
        "signal_note", "source_post_url", "engagement_type",
        "icp_confidence", "icp_reason",
    ]

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    print(f"CSV exported: {path} ({len(leads)} leads)")


# =============================================================================
# DB SYNC / LOOKUP HELPERS
# =============================================================================

def _sync_all_profiles_to_db(
    all_profiles: List[Dict],
    icp_qualified_urls: set,
    icp_description: str,
    source_type: str = "competitor_post",
    engagement_context: Optional[Dict] = None,
) -> None:
    """Sync ALL scraped profiles to the DB, not just ICP-qualified ones.

    Args:
        all_profiles: All profiles that were scraped
        icp_qualified_urls: Set of LinkedIn URLs that passed ICP filter
        icp_description: The ICP description used
        source_type: Source type for DB
        engagement_context: Optional engagement context dict
    """
    import requests

    api_url = os.getenv("SPEED_TO_LEAD_API_URL", "https://speedtolead-production.up.railway.app")

    prospects = []
    for p in all_profiles:
        li_url = normalize_linkedin_url(
            p.get("linkedinUrl") or p.get("profileUrl") or p.get("url") or ""
        )
        if not li_url:
            continue

        activity = extract_activity_fields(p)
        is_icp = li_url in icp_qualified_urls

        prospects.append({
            "linkedin_url": li_url,
            "full_name": p.get("fullName") or p.get("full_name"),
            "first_name": p.get("firstName") or p.get("first_name"),
            "last_name": p.get("lastName") or p.get("last_name"),
            "job_title": p.get("jobTitle") or p.get("job_title") or p.get("position"),
            "company_name": p.get("companyName") or p.get("company_name") or p.get("company"),
            "company_industry": p.get("companyIndustry") or p.get("company_industry"),
            "location": p.get("addressWithCountry") or p.get("location"),
            "headline": p.get("headline"),
            "email": p.get("email") or p.get("emailAddress"),
            "engagement_type": p.get("engagement_type"),
            "source_post_url": p.get("source_post_url"),
            "icp_match": is_icp,
            "icp_reason": p.get("icp_reason", "") if is_icp else "",
            "connection_count": activity["connection_count"],
            "follower_count": activity["follower_count"],
            "is_creator": activity["is_creator"],
            "activity_score": activity["activity_score"],
        })

    if not prospects:
        print("  No profiles to sync")
        return

    # Send in batches
    batch_size = 100
    total_created = 0
    total_updated = 0

    for i in range(0, len(prospects), batch_size):
        batch = prospects[i:i + batch_size]
        try:
            resp = requests.post(
                f"{api_url}/api/prospects",
                json={
                    "prospects": batch,
                    "source_type": source_type,
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            total_created += result.get("created", 0)
            total_updated += result.get("updated", 0)
        except Exception as e:
            print(f"  Error syncing batch: {e}")

    print(f"  Synced {total_created} new + {total_updated} updated profiles to DB")


def check_db_for_existing_leads(keywords: List[str], min_leads: int = 10) -> Optional[List[Dict]]:
    """Check DB for existing leads matching ICP keywords before scraping.

    Args:
        keywords: List of ICP keyword terms to search
        min_leads: Minimum leads needed to skip scraping

    Returns:
        List of matching leads if enough found, None otherwise
    """
    import requests

    api_url = os.getenv("SPEED_TO_LEAD_API_URL", "https://speedtolead-production.up.railway.app")

    try:
        resp = requests.get(
            f"{api_url}/api/prospects/by-icp",
            params={"keywords": ",".join(keywords), "limit": min_leads + 5},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("matches", 0)
        prospects = data.get("prospects", [])
        pool_size = data.get("pool_size", 0)

        print(f"  DB check: {matches} matches from {pool_size} total prospects with activity scores")

        if matches >= min_leads:
            print(f"  Found {matches} leads in DB -- skipping scrape!")
            return prospects
        else:
            print(f"  Only {matches} leads in DB (need {min_leads}) -- will scrape")
            return None

    except Exception as e:
        print(f"  DB check failed: {e} -- will scrape")
        return None


# =============================================================================
# PIPELINE RUN TRACKING
# =============================================================================

def _post_pipeline_run(run_data: Dict) -> None:
    """Post pipeline run record to speed_to_lead API.

    Args:
        run_data: Dict with run metrics, costs, and status
    """
    import requests

    api_url = os.getenv("SPEED_TO_LEAD_API_URL", "https://speedtolead-production.up.railway.app")

    try:
        resp = requests.post(
            f"{api_url}/api/pipeline-runs",
            json=run_data,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  Pipeline run recorded: {result.get('id', 'unknown')}")
    except Exception as e:
        print(f"  Warning: Failed to record pipeline run: {e}")


def _build_run_data(
    results: Dict,
    cost_tracker_instance: CostTracker,
    status: str,
    elapsed: float,
    error_message: Optional[str] = None,
) -> Dict:
    """Build run data dict from pipeline results and cost tracker.

    Args:
        results: Pipeline results dict
        cost_tracker_instance: CostTracker instance
        status: "completed" or "failed"
        elapsed: Elapsed time in seconds
        error_message: Error message if failed

    Returns:
        Dict ready to POST to /api/pipeline-runs
    """
    costs = cost_tracker_instance.costs
    counts = cost_tracker_instance.counts

    return {
        "run_type": "gift_leads",
        "prospect_url": results.get("prospect_url"),
        "prospect_name": results.get("prospect_name"),
        "icp_description": results.get("icp_description"),
        "status": status,
        # Pipeline metrics
        "queries_generated": results.get("queries_generated", 0),
        "posts_found": results.get("posts_found", 0),
        "engagers_found": results.get("engagers_found", 0),
        "profiles_scraped": results.get("profiles_scraped", 0),
        "location_filtered": results.get("location_filtered", 0),
        "icp_qualified": results.get("icp_qualified", 0),
        "final_leads": results.get("final_leads", 0),
        # Cost breakdown (keys match CostTracker.costs dict)
        "cost_apify_google": costs.get("apify_google_search", 0),
        "cost_apify_reactions": costs.get("apify_post_reactions", 0),
        "cost_apify_profiles": costs.get("apify_profile_scraper", 0),
        "cost_deepseek_icp": costs.get("deepseek_icp", 0),
        "cost_deepseek_personalize": costs.get("deepseek_personalization", 0),
        "cost_total": cost_tracker_instance.get_total(),
        # API call counts (keys match CostTracker.counts dict)
        "count_google_searches": counts.get("google_results", 0),
        "count_posts_scraped": counts.get("posts_scraped", 0),
        "count_profiles_scraped": counts.get("profiles_scraped", 0),
        "count_icp_checks": counts.get("icp_checks", 0),
        "count_personalizations": counts.get("personalizations", 0),
        # Timing
        "duration_seconds": int(elapsed),
        "error_message": error_message,
    }


# =============================================================================
# MODULE 6: MAIN PIPELINE ORCHESTRATOR
# =============================================================================

def run_gift_leads_pipeline(
    prospect_url: str,
    user_icp: Optional[str] = None,
    user_pain_points: Optional[str] = None,
    days_back: int = 14,
    min_reactions: int = 50,
    countries: Optional[List[str]] = None,
    min_leads: int = 10,
    max_leads: int = 25,
    dry_run: bool = False,
    skip_research: bool = False,
    queries_file: Optional[str] = None,
    force_scrape: bool = False,
) -> Dict[str, Any]:
    """
    Main orchestrator for the gift leads list pipeline.

    Args:
        prospect_url: LinkedIn profile URL of the prospect
        user_icp: Optional ICP description override
        user_pain_points: Optional pain points override
        days_back: Days to look back for posts
        min_reactions: Minimum reactions to consider a post
        countries: Allowed countries for leads
        min_leads: Target minimum number of leads
        max_leads: Maximum leads to return
        dry_run: If True, use cached data only, skip Apify calls
        skip_research: If True, skip research step (requires user_icp)
        force_scrape: If True, skip DB check and always scrape fresh

    Returns:
        Pipeline results dict
    """
    if countries is None:
        countries = ["United States", "Canada", "USA", "America"]

    start_time = time.time()

    print("=" * 60)
    print("GIFT LEADS LIST PIPELINE")
    print("=" * 60)
    print(f"Prospect: {prospect_url}")
    print(f"ICP: {user_icp or '(will derive from profile)'}")
    print(f"Pain Points: {user_pain_points or '(will derive from profile)'}")
    print(f"Days back: {days_back}")
    print(f"Min reactions: {min_reactions}")
    print(f"Countries: {', '.join(countries)}")
    print(f"Target leads: {min_leads}-{max_leads}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    results = {
        "prospect_url": prospect_url,
        "prospect_name": "",
        "icp_description": "",
        "queries_generated": 0,
        "posts_found": 0,
        "posts_filtered": 0,
        "engagers_found": 0,
        "prefilter_kept": 0,
        "profiles_scraped": 0,
        "location_filtered": 0,
        "complete_profiles": 0,
        "icp_qualified": 0,
        "leads_with_notes": 0,
        "final_leads": 0,
    }

    # ── Step 1: Scrape prospect profile ──
    print("\n[1/12] Scraping prospect profile...")
    if dry_run:
        cache = load_profile_cache()
        cache_key = normalize_linkedin_url(prospect_url)
        prospect_profile = cache.get(cache_key)
        if not prospect_profile:
            print("Dry run: prospect profile not in cache. Provide cached data or run without --dry-run.")
            return results
    else:
        prospect_profile = scrape_prospect_profile(prospect_url)

    if not prospect_profile:
        print("Could not get prospect profile. Exiting.")
        return results

    prospect_name = prospect_profile.get("fullName") or prospect_profile.get("firstName")
    if not prospect_name:
        # Fallback: parse name from URL slug (e.g., "brodyzastrow" -> "Brody Zastrow")
        slug = prospect_url.rstrip("/").split("/")[-1]
        # Try common patterns: first+last concatenated, or hyphenated
        import re
        clean_slug = re.sub(r'[^a-zA-Z]', ' ', slug).strip()
        if clean_slug:
            prospect_name = clean_slug.title()
        else:
            prospect_name = "Unknown"
    results["prospect_name"] = prospect_name
    print(f"  Prospect: {prospect_name}")

    # ── Step 2: Research prospect's business ──
    if skip_research and user_icp:
        print("\n[2/12] Skipping research (--skip-research, using provided ICP)...")
        research = {
            "icp_description": user_icp,
            "target_titles": ["CEO", "Founder", "Managing Director"],
            "target_industries": [],
            "target_verticals": [],
            "pain_points": user_pain_points.split(",") if user_pain_points else ["growth", "scaling"],
            "buying_signals": ["discussing challenges", "hiring"],
            "buyer_intent_phrases": [],
            "search_angles": ["pain points", "hiring"],
        }
    else:
        print("\n[2/12] Researching prospect's business...")
        research = research_prospect_business(prospect_profile, user_icp, user_pain_points)

    icp_description = research.get("icp_description", "")
    results["icp_description"] = icp_description
    print(f"  ICP: {icp_description}")
    print(f"  Pain points: {research.get('pain_points', [])}")
    print(f"  Buying signals: {research.get('buying_signals', [])}")

    # ── Step 2.5: Check DB for existing leads ──
    if not dry_run and not force_scrape:
        print("\n[2.5/12] Checking DB for existing leads...")
        # Extract keywords from ICP description for DB search
        icp_keywords = [w.strip() for w in icp_description.split(",") if len(w.strip()) > 2]
        # Also use target_titles if available
        target_titles = research.get("target_titles", [])
        if target_titles:
            icp_keywords.extend(target_titles[:3])

        if icp_keywords:
            db_leads = check_db_for_existing_leads(icp_keywords, min_leads=min_leads)
            if db_leads:
                # We have enough from DB -- skip scraping entirely
                print(f"  Using {len(db_leads)} leads from DB pool")
                qualified = []
                for lead in db_leads[:max_leads]:
                    qualified.append({
                        "fullName": lead.get("full_name"),
                        "linkedinUrl": lead.get("linkedin_url"),
                        "jobTitle": lead.get("job_title"),
                        "companyName": lead.get("company_name"),
                        "addressWithCountry": lead.get("location"),
                        "headline": lead.get("headline"),
                        "activity_score": lead.get("activity_score"),
                        "icp_confidence": "db_match",
                        "icp_reason": "Matched from existing prospect pool",
                    })

                # Skip to signal notes (step 11)
                results["icp_qualified"] = len(qualified)
                results["final_leads"] = len(qualified)

                # Generate signal notes
                print("\n[11/12] Generating signal notes...")
                qualified = generate_signal_notes(qualified, icp_description)
                results["leads_with_notes"] = len(qualified)

                # Export
                print("\n[12/12] Exporting results...")
                safe_name = "".join(c for c in prospect_name if c.isalnum() or c in " -_").strip().replace(" ", "_")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                output_json = format_gift_leads_json(
                    leads=qualified,
                    prospect_name=prospect_name,
                    prospect_url=prospect_url,
                    icp_description=icp_description,
                    cost_tracker_instance=cost_tracker,
                )

                json_path = f".tmp/gift_leads_{safe_name}_{timestamp}.json"
                os.makedirs(".tmp", exist_ok=True)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(output_json, f, indent=2, ensure_ascii=False)
                print(f"  JSON: {json_path}")

                csv_path = f".tmp/gift_leads_{safe_name}_{timestamp}.csv"
                export_gift_leads_csv(output_json["leads"], csv_path)

                # Summary
                print("\n" + "=" * 60)
                print("PIPELINE SUMMARY (from DB pool)")
                print("=" * 60)
                for key, value in results.items():
                    print(f"  {key}: {value}")
                print("=" * 60)

                # Post run record
                elapsed = time.time() - start_time
                _post_pipeline_run(_build_run_data(results, cost_tracker, "completed", elapsed))

                return results

    # ── Step 3: Generate search queries ──
    if queries_file:
        print(f"\n[3/12] Loading queries from file: {queries_file}")
        with open(queries_file, "r", encoding="utf-8") as qf:
            queries = [line.strip() for line in qf if line.strip() and not line.strip().startswith("#")]
        print(f"  Loaded {len(queries)} queries from file")
    else:
        print("\n[3/12] Generating search queries...")
        queries = generate_search_queries(research, days_back, prospect_profile=prospect_profile)
    results["queries_generated"] = len(queries)

    if not queries:
        print("No queries generated. Exiting.")
        return results

    # ── Step 4: Search Google for LinkedIn posts ──
    print("\n[4/12] Searching Google for LinkedIn posts...")
    all_search_results = []
    for i, query in enumerate(queries, 1):
        print(f"  Query [{i}/{len(queries)}]: {query}")
        if dry_run:
            print("    (dry run: skipping API call)")
            continue
        query_results = search_google_raw_query(query, max_pages=1, results_per_page=10)
        all_search_results.extend(query_results)

    results["posts_found"] = len(all_search_results)
    print(f"  Total search results: {len(all_search_results)}")

    if not all_search_results and not dry_run:
        print("No posts found. Exiting.")
        return results

    # ── Step 5: Filter posts by reactions ──
    print("\n[5/12] Filtering posts by reactions...")
    # Extract organic results if nested
    posts = []
    for result in all_search_results:
        if "organicResults" in result:
            if isinstance(result["organicResults"], list):
                posts.extend(result["organicResults"])
            else:
                posts.append(result["organicResults"])
        else:
            posts.append(result)

    filtered_posts = filter_posts_by_reactions(posts, min_reactions)
    results["posts_filtered"] = len(filtered_posts)
    print(f"  Posts with {min_reactions}+ reactions: {len(filtered_posts)}")

    if not filtered_posts:
        print("No posts meet reaction threshold. Exiting.")
        return results

    # ── Step 6: Scrape post engagers ──
    print("\n[6/12] Scraping post engagers...")
    post_urls = [
        p.get("url", p.get("link", ""))
        for p in filtered_posts
        if p.get("url") or p.get("link")
    ]

    if dry_run:
        print("  (dry run: skipping engager scraping)")
        engagers = []
    else:
        engagers = scrape_post_engagers(post_urls)
        cost_tracker.add_post_reactions(len(post_urls))

    results["engagers_found"] = len(engagers)

    if not engagers:
        print("No engagers found. Exiting.")
        return results

    # Build engagement context
    engagement_context = build_engagement_context(engagers)
    print(f"  Engagement context for {len(engagement_context)} profiles")

    # ── Step 7: Pre-filter by headline ──
    print("\n[7/12] Pre-filtering engagers by headline...")
    engagers, kept, rejected, non_english = prefilter_engagers_by_headline(engagers)
    results["prefilter_kept"] = kept

    if not engagers:
        print("All engagers filtered out. Exiting.")
        return results

    # ── Steps 8-10: Batched scrape → filter → qualify (early-stop) ──
    print("\n[8-10/12] Batched profile scraping with early-stop...")
    profile_urls = aggregate_profile_urls(engagers)
    profile_urls = deduplicate_profile_urls(profile_urls)
    print(f"  Unique profile URLs: {len(profile_urls)}")

    BATCH_SIZE = 100
    qualified = []
    _all_scraped_profiles = []
    total_scraped = 0
    total_location_filtered = 0
    total_complete = 0

    if dry_run:
        print("  (dry run: using cached profiles only)")
        cache = load_profile_cache()
        profiles = [
            cache[normalize_linkedin_url(url)]
            for url in profile_urls
            if normalize_linkedin_url(url) in cache
        ]
        profiles = enrich_profiles_with_engagement(profiles, engagement_context)
        _all_scraped_profiles.extend(profiles)
        location_filtered = filter_by_location(profiles, countries)
        complete = filter_complete_profiles(location_filtered)
        if complete:
            qualified = qualify_leads_with_deepseek(complete, icp_criteria=icp_description)
            cost_tracker.add_icp_check(len(complete))
        total_scraped = len(profiles)
        total_location_filtered = len(location_filtered)
        total_complete = len(complete)
    else:
        num_batches = (len(profile_urls) + BATCH_SIZE - 1) // BATCH_SIZE
        for batch_idx in range(num_batches):
            batch_start = batch_idx * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, len(profile_urls))
            batch_urls = profile_urls[batch_start:batch_end]

            print(f"\n  --- Batch {batch_idx + 1}/{num_batches} ({len(batch_urls)} profiles) ---")

            profiles = scrape_linkedin_profiles(batch_urls, wait_seconds=120, poll_interval=30)
            cost_tracker.add_profile_scrape(len(profiles))
            total_scraped += len(profiles)

            profiles = enrich_profiles_with_engagement(profiles, engagement_context)
            _all_scraped_profiles.extend(profiles)
            location_filtered = filter_by_location(profiles, countries)
            total_location_filtered += len(location_filtered)
            complete = filter_complete_profiles(location_filtered)
            total_complete += len(complete)

            if complete:
                batch_qualified = qualify_leads_with_deepseek(complete, icp_criteria=icp_description)
                cost_tracker.add_icp_check(len(complete))
                qualified.extend(batch_qualified)
                print(f"  Batch result: {len(batch_qualified)} qualified ({len(qualified)} total)")
            else:
                print(f"  Batch result: 0 qualified ({len(qualified)} total)")

            if len(qualified) >= min_leads:
                remaining = len(profile_urls) - batch_end
                saved = remaining * 0.025  # ~$0.025 per profile
                print(f"\n  *** Early stop: {len(qualified)} leads >= {min_leads} target ***")
                print(f"  Skipped {remaining} profiles, saved ~${saved:.2f}")
                break

    results["profiles_scraped"] = total_scraped
    results["location_filtered"] = total_location_filtered
    results["complete_profiles"] = total_complete
    results["icp_qualified"] = len(qualified)
    print(f"\n  Total scraped: {total_scraped}, Location filtered: {total_location_filtered}")
    print(f"  Complete: {total_complete}, ICP qualified: {len(qualified)}")

    # ── Sync ALL scraped profiles to DB for future reuse ──
    print("\n  Syncing all scraped profiles to DB...")
    _sync_all_profiles_to_db(
        all_profiles=_all_scraped_profiles,
        icp_qualified_urls={normalize_linkedin_url(q.get("linkedinUrl") or q.get("linkedin_url", "")) for q in qualified},
        icp_description=icp_description,
        source_type="competitor_post",
        engagement_context=engagement_context,
    )

    if not qualified:
        print("No leads passed ICP qualification. Exiting.")
        return results

    # Cap at max_leads
    if len(qualified) > max_leads:
        confidence_order = {"high": 0, "medium": 1, "low": 2, "local": 3, "error": 4}
        qualified.sort(key=lambda x: confidence_order.get(x.get("icp_confidence", "low"), 3))
        qualified = qualified[:max_leads]
        print(f"  Capped to {max_leads} leads")

    # ── Step 11: Generate signal notes ──
    print("\n[11/12] Generating signal notes...")
    qualified = generate_signal_notes(qualified, icp_description)
    results["leads_with_notes"] = len(qualified)

    # ── Step 12: Export JSON + CSV ──
    print("\n[12/12] Exporting results...")

    # Build safe filename
    safe_name = "".join(c for c in prospect_name if c.isalnum() or c in " -_").strip().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Format JSON
    output_json = format_gift_leads_json(
        leads=qualified,
        prospect_name=prospect_name,
        prospect_url=prospect_url,
        icp_description=icp_description,
        cost_tracker_instance=cost_tracker,
    )

    # Write JSON
    json_path = f".tmp/gift_leads_{safe_name}_{timestamp}.json"
    os.makedirs(".tmp", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {json_path}")

    # Write CSV
    csv_path = f".tmp/gift_leads_{safe_name}_{timestamp}.csv"
    export_gift_leads_csv(output_json["leads"], csv_path)

    results["final_leads"] = len(qualified)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for key, value in results.items():
        print(f"  {key}: {value}")
    print("=" * 60)
    print("\n" + cost_tracker.get_summary())

    # Post run record
    elapsed = time.time() - start_time
    _post_pipeline_run(_build_run_data(results, cost_tracker, "completed", elapsed))

    return results


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gift Leads List - Find qualified leads as a value-add for prospects"
    )
    parser.add_argument(
        "--prospect-url", required=True,
        help="LinkedIn profile URL of the prospect"
    )
    parser.add_argument(
        "--icp", default=None,
        help='Optional ICP description (e.g., "B2B SaaS founders, 10-50 employees")'
    )
    parser.add_argument(
        "--pain-points", default=None,
        help='Optional pain points (e.g., "outbound pipeline, lead gen")'
    )
    parser.add_argument(
        "--days-back", type=int, default=14,
        help="Days to look back for posts (default: 14)"
    )
    parser.add_argument(
        "--min-reactions", type=int, default=50,
        help="Minimum reactions threshold (default: 50)"
    )
    parser.add_argument(
        "--countries", nargs="+", default=["United States", "Canada"],
        help='Allowed countries (default: "United States" "Canada")'
    )
    parser.add_argument(
        "--min-leads", type=int, default=10,
        help="Target minimum leads (default: 10)"
    )
    parser.add_argument(
        "--max-leads", type=int, default=25,
        help="Maximum leads to return (default: 25)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use cached data only, skip Apify calls"
    )
    parser.add_argument(
        "--skip-research", action="store_true",
        help="Skip research step (requires --icp)"
    )
    parser.add_argument(
        "--queries-file", default=None,
        help="Path to file with pre-formed search queries (one per line, skips query generation)"
    )
    parser.add_argument(
        "--force-scrape", action="store_true",
        help="Skip DB check and always scrape fresh leads"
    )

    args = parser.parse_args()

    if args.skip_research and not args.icp:
        parser.error("--skip-research requires --icp")

    try:
        results = run_gift_leads_pipeline(
            prospect_url=args.prospect_url,
            user_icp=args.icp,
            user_pain_points=args.pain_points,
            days_back=args.days_back,
            min_reactions=args.min_reactions,
            countries=args.countries,
            min_leads=args.min_leads,
            max_leads=args.max_leads,
            dry_run=args.dry_run,
            skip_research=args.skip_research,
            queries_file=args.queries_file,
            force_scrape=args.force_scrape,
        )
    except Exception as e:
        # Post failed run record
        elapsed = time.time() - time.time()  # approximate
        _post_pipeline_run({
            "run_type": "gift_leads",
            "prospect_url": args.prospect_url,
            "prospect_name": None,
            "status": "failed",
            "error_message": str(e),
            "duration_seconds": 0,
        })
        print(f"\nPipeline FAILED: {e}")
        sys.exit(2)

    if results["final_leads"] > 0:
        print(f"\nPipeline completed: {results['final_leads']} leads found!")
        sys.exit(0)
    else:
        print("\nPipeline completed but no leads qualified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
