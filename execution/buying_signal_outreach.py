#!/usr/bin/env python3
"""
Buying Signal Outreach: Gojiberry CSV → Scrape Posts → Personalize → JSON (→ HeyReach upload)

Reads prospects who engaged with LinkedIn posts (buying signals from Gojiberry),
scrapes the actual posts via Apify to get real author names and full post text,
caches scraped posts to avoid re-scraping, generates personalized 5-line LinkedIn
DMs that reference the specific post, and outputs to JSON for QA.
"""

import os
import sys
import csv
import json
import re
import random
import argparse
from urllib.parse import unquote
from dotenv import load_dotenv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from prompts import get_linkedin_buying_signal_prompt

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HEYREACH_API_KEY = os.getenv("HEYREACH_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
HEYREACH_API_BASE = "https://api.heyreach.io/api/public"
POST_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", ".tmp", "post_cache.json")
PROFILE_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", ".tmp", "profile_cache.json")
PROFILE_SCRAPER_ACTOR = "dev_fusion~Linkedin-Profile-Scraper"


# --- Post cache ---

def load_post_cache():
    """Load cached post data from JSON file."""
    if os.path.exists(POST_CACHE_PATH):
        with open(POST_CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_post_cache(cache):
    """Save post cache to JSON file."""
    os.makedirs(os.path.dirname(POST_CACHE_PATH), exist_ok=True)
    with open(POST_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def normalize_post_url(url):
    """Strip UTM params to get a canonical URL for cache keys."""
    if not url:
        return None
    return url.split('?')[0]


# --- Apify scraping ---

def scrape_posts_apify(urls):
    """Scrape LinkedIn posts via Apify's supreme_coder/linkedin-post actor.

    Args:
        urls: List of LinkedIn post URLs to scrape

    Returns:
        Dict mapping normalized_url -> {author_name, post_text, author_profile_url}
    """
    if not APIFY_API_TOKEN:
        print("  Warning: APIFY_API_TOKEN not found, skipping post scraping")
        return {}

    from apify_client import ApifyClient
    client = ApifyClient(APIFY_API_TOKEN)

    print(f"  Scraping {len(urls)} posts via Apify...")

    run = client.actor('supreme_coder/linkedin-post').call(run_input={
        'urls': urls
    })

    if run.get('status') != 'SUCCEEDED':
        print(f"  Warning: Apify run status: {run.get('status')}")
        return {}

    results = {}
    for item in client.dataset(run['defaultDatasetId']).iterate_items():
        input_url = normalize_post_url(item.get('inputUrl') or item.get('url', ''))
        if input_url:
            results[input_url] = {
                'author_name': item.get('authorName', ''),
                'post_text': item.get('text', ''),
                'author_profile_url': item.get('authorProfileUrl', ''),
                'num_likes': item.get('numLikes', 0),
                'num_comments': item.get('numComments', 0),
                'posted_at': item.get('postedAtISO', ''),
            }

    print(f"  Scraped {len(results)} posts successfully")
    return results


def enrich_leads_with_post_data(leads):
    """Scrape posts, cache results, and enrich leads with real author names and post text.

    Only scrapes posts not already in cache. Same post shared by multiple leads = one scrape.
    """
    cache = load_post_cache()

    # Collect unique post URLs that need scraping
    urls_to_scrape = []
    for lead in leads:
        url = normalize_post_url(lead.get('post_url'))
        if url and url not in cache:
            urls_to_scrape.append(url)

    # Deduplicate
    urls_to_scrape = list(set(urls_to_scrape))

    cached_count = sum(1 for l in leads if normalize_post_url(l.get('post_url')) in cache)
    print(f"  Posts in cache: {cached_count}")
    print(f"  Posts to scrape: {len(urls_to_scrape)}")

    # Scrape missing posts
    if urls_to_scrape:
        new_data = scrape_posts_apify(urls_to_scrape)
        cache.update(new_data)
        save_post_cache(cache)
        print(f"  Cache updated: {len(cache)} total posts")

    # Enrich leads
    for lead in leads:
        url = normalize_post_url(lead.get('post_url'))
        if url and url in cache:
            post = cache[url]
            lead['post_author'] = post.get('author_name', '') or lead.get('post_author', '')
            lead['post_text'] = post.get('post_text', '')
            lead['post_author_profile'] = post.get('author_profile_url', '')

    return leads


# --- Profile cache ---

def load_profile_cache():
    """Load cached LinkedIn profile data from JSON file."""
    if os.path.exists(PROFILE_CACHE_PATH):
        try:
            with open(PROFILE_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_profile_cache(cache):
    """Save profile cache to JSON file."""
    os.makedirs(os.path.dirname(PROFILE_CACHE_PATH), exist_ok=True)
    with open(PROFILE_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def normalize_linkedin_url(url):
    """Normalize LinkedIn URL for cache key (strip query params, trailing slash, lowercase)."""
    if not url:
        return ""
    return url.split("?")[0].rstrip("/").lower()


# --- Profile scraping via Apify ---

def scrape_profiles_apify(profile_urls, wait_seconds=120, poll_interval=30):
    """Scrape LinkedIn profiles via Apify dev_fusion~Linkedin-Profile-Scraper.

    Args:
        profile_urls: List of LinkedIn profile URLs
        wait_seconds: Initial wait before polling
        poll_interval: Seconds between status polls

    Returns:
        List of profile dicts from Apify
    """
    import time

    if not APIFY_API_TOKEN:
        print("  Warning: APIFY_API_TOKEN not set, skipping profile scraping")
        return []

    print(f"  Starting profile scraper for {len(profile_urls)} profiles...")

    start_url = f"https://api.apify.com/v2/acts/{PROFILE_SCRAPER_ACTOR}/runs?token={APIFY_API_TOKEN}"
    payload = {"profileUrls": profile_urls}

    try:
        response = requests.post(start_url, json=payload)
        response.raise_for_status()
        run_data = response.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]
        print(f"  Run started: {run_id}")
    except Exception as e:
        print(f"  Error starting profile scraper: {e}")
        return []

    print(f"  Waiting {wait_seconds}s for scraping...")
    time.sleep(wait_seconds)

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_API_TOKEN}"
    while True:
        try:
            response = requests.get(status_url)
            response.raise_for_status()
            status = response.json()["data"]["status"]
            if status in ["SUCCEEDED", "ABORTED"]:
                print(f"  Scraper finished: {status}")
                break
            print(f"  Status: {status}, waiting {poll_interval}s...")
            time.sleep(poll_interval)
        except Exception as e:
            print(f"  Error polling status: {e}")
            break

    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_TOKEN}"
    try:
        response = requests.get(data_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        profiles = response.json()
        print(f"  Retrieved {len(profiles)} profiles")
        return profiles
    except Exception as e:
        print(f"  Error fetching profile data: {e}")
        return []


def enrich_leads_with_profile_data(leads):
    """Scrape LinkedIn profiles, cache results, enrich leads with headline/about/company info.

    Only scrapes profiles not already in cache.
    """
    cache = load_profile_cache()

    urls_to_scrape = []
    for lead in leads:
        url = normalize_linkedin_url(lead.get("linkedin_url"))
        if url and url not in cache:
            urls_to_scrape.append(lead.get("linkedin_url"))

    urls_to_scrape = list(set(urls_to_scrape))
    cached_count = sum(1 for l in leads if normalize_linkedin_url(l.get("linkedin_url")) in cache)
    print(f"  Profiles in cache: {cached_count}")
    print(f"  Profiles to scrape: {len(urls_to_scrape)}")

    if urls_to_scrape:
        new_profiles = scrape_profiles_apify(urls_to_scrape)
        for profile in new_profiles:
            profile_url = profile.get("linkedinUrl") or profile.get("profileUrl") or ""
            if profile_url:
                cache_key = normalize_linkedin_url(profile_url)
                cache[cache_key] = profile
        save_profile_cache(cache)
        print(f"  Profile cache updated: {len(cache)} total")

    # Enrich leads with profile data
    for lead in leads:
        cache_key = normalize_linkedin_url(lead.get("linkedin_url"))
        if cache_key and cache_key in cache:
            profile = cache[cache_key]
            lead["profile_headline"] = profile.get("headline", "")
            lead["profile_about"] = profile.get("about", "")
            lead["profile_company_name"] = profile.get("companyName", "")
            lead["profile_company_industry"] = profile.get("companyIndustry", "")
            lead["profile_job_title"] = profile.get("jobTitle", "")

    return leads


# --- URL parsing (fallbacks when scraping unavailable) ---

def extract_post_url(intent_html):
    """Extract the LinkedIn post URL from the Intent HTML field."""
    match = re.search(r"href='([^']+)'", intent_html or "")
    if match:
        return match.group(1)
    match = re.search(r'href="([^"]+)"', intent_html or "")
    if match:
        return match.group(1)
    return None


def extract_post_topic_from_slug(post_url):
    """Fallback: extract topic from URL slug when scraping isn't available."""
    if not post_url:
        return None

    url = unquote(post_url)
    match = re.search(r'/posts/([^?]+)', url)
    if not match:
        return None

    slug = match.group(1)
    parts = slug.split('_', 1)
    if len(parts) < 2:
        return None

    topic_part = parts[1]
    topic_part = re.split(r'-activity-', topic_part)[0]
    topic = topic_part.replace('-', ' ').strip()

    if topic:
        topic = topic[0].upper() + topic[1:]

    return topic


def extract_post_author_from_slug(post_url):
    """Fallback: extract author name from URL slug when scraping isn't available."""
    if not post_url:
        return None

    url = unquote(post_url)
    match = re.search(r'/posts/([^?]+)', url)
    if not match:
        return None

    slug = match.group(1)
    author_slug = slug.split('_', 1)[0]
    author_slug = re.sub(r'-[0-9a-f]{6,}$', '', author_slug, flags=re.IGNORECASE)
    author_name = author_slug.replace('-', ' ').strip().title()

    return author_name if author_name else None


def clean_intent_keyword(raw_keyword):
    """Clean the Intent Keyword field — strip quotes, URLs, whitespace."""
    if not raw_keyword:
        return None
    kw = raw_keyword.strip().strip('"').strip("'").strip()
    if kw.startswith("http"):
        return None
    return kw if kw else None


# --- CSV reading ---

def read_buying_signal_csv(csv_path):
    """Read the Gojiberry CSV and parse into a list of lead dicts."""
    leads = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            post_url = extract_post_url(row.get("Intent", ""))
            intent_keyword = clean_intent_keyword(row.get("Intent Keyword", ""))

            lead = {
                "_idx": idx,
                "first_name": row.get("First Name", "").strip(),
                "last_name": row.get("Last Name", "").strip(),
                "location": row.get("Location", "").strip(),
                "job_title": row.get("Job Title", "").strip(),
                "industry": row.get("Industry", "").strip(),
                "company": row.get("Company", "").strip(),
                "company_url": row.get("Company URL", "").strip(),
                "website": row.get("Website", "").strip(),
                "linkedin_url": row.get("Profile URL", "").strip(),
                "total_score": row.get("Total Score", "").strip(),
                "post_url": post_url,
                # Slug-based fallbacks (overwritten by Apify data if available)
                "post_topic": extract_post_topic_from_slug(post_url),
                "post_author": extract_post_author_from_slug(post_url),
                "post_text": "",
                "intent_keyword": intent_keyword,
                "raw_intent": row.get("Intent", "").strip(),
            }
            leads.append(lead)

    return leads


# --- Message generation ---

def detect_signal_type(lead):
    """Determine signal type: 'post' if specific post engagement, 'top5' if general activity."""
    # If no post URL or no post text/topic, it's a top 5% activity signal
    has_post = bool(lead.get("post_url") and (lead.get("post_text") or lead.get("post_topic")))
    return "post" if has_post else "top5"


def generate_buying_signal_message(lead):
    """Generate a personalized 5-line LinkedIn DM using DeepSeek with buying signal context."""
    if not DEEPSEEK_API_KEY:
        print("  Error: DEEPSEEK_API_KEY not found in .env")
        return None

    # Extract city from full location
    location = lead.get("location", "")
    if "," in location:
        location = location.split(",")[0].strip()

    signal_type = lead.get("signal_type") or detect_signal_type(lead)

    # Build the topic string — prefer full post text, fall back to slug topic, then keyword
    post_text = lead.get("post_text") or ""
    slug_topic = lead.get("post_topic") or ""
    intent_keyword = lead.get("intent_keyword") or ""

    if post_text:
        topic_for_prompt = post_text[:300]
    elif slug_topic and intent_keyword:
        topic_for_prompt = f"{slug_topic} (related to: {intent_keyword})"
    elif slug_topic:
        topic_for_prompt = slug_topic
    elif intent_keyword:
        topic_for_prompt = intent_keyword
    else:
        topic_for_prompt = "LinkedIn outreach and growth"

    prompt = get_linkedin_buying_signal_prompt(
        first_name=lead.get("first_name", ""),
        company_name=lead.get("company", ""),
        title=lead.get("job_title", ""),
        industry=lead.get("industry", ""),
        location=location,
        post_author=lead.get("post_author", ""),
        post_topic=topic_for_prompt,
        intent_keyword=intent_keyword or "(not available)",
        signal_type=signal_type,
        skip_location=lead.get("skip_location", False),
        headline=lead.get("profile_headline", ""),
        about=lead.get("profile_about", ""),
    )

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules. You write as a founder, not a salesperson."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400,
            "temperature": 0.7
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        message = data["choices"][0]["message"]["content"].strip()

        # Clean up
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        message = message.replace("```", "").strip()

        return message

    except Exception as e:
        print(f"  Error generating message: {e}")
        return None


# --- HeyReach upload ---

def upload_to_heyreach(leads, list_id):
    """Upload leads to HeyReach list with personalized messages."""
    if not HEYREACH_API_KEY:
        print("[ERROR] HEYREACH_API_KEY not found in .env")
        return 0

    headers = {
        "X-API-KEY": HEYREACH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = f"{HEYREACH_API_BASE}/list/AddLeadsToListV2"

    formatted_leads = []
    for lead in leads:
        if not lead.get("personalized_message"):
            continue

        formatted_lead = {
            "firstName": lead.get("first_name", ""),
            "lastName": lead.get("last_name", ""),
            "profileUrl": lead.get("linkedin_url", ""),
            "customUserFields": [
                {
                    "name": "personalized_message",
                    "value": lead["personalized_message"]
                }
            ]
        }

        if lead.get("company"):
            formatted_lead["companyName"] = lead["company"]
        if lead.get("job_title"):
            formatted_lead["position"] = lead["job_title"]
        if lead.get("location"):
            formatted_lead["location"] = lead["location"]

        formatted_leads.append(formatted_lead)

    print(f"\nUploading {len(formatted_leads)} leads to HeyReach list {list_id}...")

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
            print(f"  [OK] Uploaded {total_uploaded}/{len(formatted_leads)}")
        except Exception as e:
            print(f"  [ERROR] Upload chunk failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response: {e.response.text}")

    print(f"\n  Uploaded: {total_uploaded}/{len(formatted_leads)}")
    return total_uploaded


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Buying Signal Outreach: Gojiberry CSV → Scrape Posts → Personalize → JSON (→ HeyReach)"
    )
    parser.add_argument("--input", required=True,
                        help="Path to the Gojiberry buying signal CSV")
    parser.add_argument("--output", default=".tmp/buying_signal_personalized.json",
                        help="Output JSON path (default: .tmp/buying_signal_personalized.json)")
    parser.add_argument("--upload", action="store_true",
                        help="Upload to HeyReach after personalization")
    parser.add_argument("--list_id", type=int,
                        help="HeyReach list ID (required if --upload)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of leads to process (0 = all)")
    parser.add_argument("--workers", type=int, default=10,
                        help="Parallel workers for DeepSeek calls (default: 10)")
    parser.add_argument("--skip_scrape", action="store_true",
                        help="Skip Apify scraping, use URL slug parsing only")
    parser.add_argument("--signal_type", choices=["post", "top5", "auto"], default="auto",
                        help="Force signal type for line 2: 'post' (specific post), 'top5' (activity signal), 'auto' (detect per lead)")
    parser.add_argument("--scrape_profiles", action="store_true",
                        help="Scrape LinkedIn profiles via Apify for better niche/ICP inference")

    args = parser.parse_args()

    if args.upload and not args.list_id:
        print("[ERROR] --list_id required when using --upload")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    print(f"\n{'='*60}")
    print("BUYING SIGNAL OUTREACH")
    print(f"{'='*60}")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    if args.limit:
        print(f"Limit:  {args.limit} leads")
    print(f"{'='*60}\n")

    # Step 1: Read and parse CSV
    print("Step 1: Reading CSV...\n")
    leads = read_buying_signal_csv(args.input)

    if args.limit:
        leads = leads[:args.limit]

    print(f"  Total leads: {len(leads)}")

    # Step 2: Scrape posts for real author names + full text
    if not args.skip_scrape:
        print(f"\nStep 2: Enriching with scraped post data...\n")
        leads = enrich_leads_with_post_data(leads)
    else:
        print(f"\nStep 2: Skipped (using URL slug parsing)\n")

    # Step 2b: Scrape LinkedIn profiles for better niche inference
    if args.scrape_profiles:
        print(f"\nStep 2b: Enriching with LinkedIn profile data...\n")
        leads = enrich_leads_with_profile_data(leads)
    else:
        print(f"\nStep 2b: Skipped profile scraping (use --scrape_profiles to enable)\n")

    # Show post distribution
    posts = {}
    for lead in leads:
        author = lead.get("post_author") or "(unknown)"
        topic = (lead.get("post_text") or lead.get("post_topic") or "?")[:60]
        key = f"{author}: {topic}"
        posts[key] = posts.get(key, 0) + 1
    print(f"  Unique posts: {len(posts)}")
    for p, count in sorted(posts.items(), key=lambda x: -x[1])[:5]:
        print(f"    [{count}] {p[:80]}")
    print()

    # Apply signal type override
    if args.signal_type != "auto":
        for lead in leads:
            lead["signal_type"] = args.signal_type

    # 50/50 split: half get location hook, half don't
    random.shuffle(leads)  # shuffle so the split is random, not positional
    half = len(leads) // 2
    for i, lead in enumerate(leads):
        lead["skip_location"] = i >= half
    # Re-sort back to original CSV order
    leads.sort(key=lambda x: x.get("_idx", 0))

    with_loc = sum(1 for l in leads if not l.get("skip_location"))
    without_loc = sum(1 for l in leads if l.get("skip_location"))
    print(f"  Location hook split: {with_loc} with / {without_loc} without\n")

    # Step 3: Generate personalized messages
    print("Step 3: Generating personalized messages via DeepSeek...\n")

    success_count = 0
    failed_count = 0

    def process_lead(idx_and_lead):
        idx, lead = idx_and_lead
        message = generate_buying_signal_message(lead)
        if message:
            lead["personalized_message"] = message
            name = f"{lead['first_name']} {lead['last_name']}".strip()
            print(f"  [OK] #{idx+1}: {name}")
            return lead, "success"
        else:
            name = f"{lead['first_name']} {lead['last_name']}".strip()
            print(f"  [FAIL] #{idx+1}: {name}")
            return lead, "failed"

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_lead, (idx, lead)): idx for idx, lead in enumerate(leads)}

        for future in as_completed(futures):
            lead, status = future.result()
            if status == "success":
                success_count += 1
            else:
                failed_count += 1

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Personalized: {success_count}")
    print(f"  Failed:       {failed_count}")
    print(f"{'='*60}")

    # Save output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {args.output}")

    # Step 4: Upload to HeyReach (optional)
    if args.upload:
        print(f"\nStep 4: Uploading to HeyReach list {args.list_id}...")
        upload_to_heyreach(leads, args.list_id)

    print("\nDone.")


if __name__ == "__main__":
    main()
