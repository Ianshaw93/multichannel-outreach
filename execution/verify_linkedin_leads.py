#!/usr/bin/env python3
"""
Verify LinkedIn leads against ICP criteria using Claude.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

def verify_leads(leads, icp_criteria):
    """
    Verify leads against ICP criteria using Claude.
    Returns leads with verification results added.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env", file=sys.stderr)
        return None
    
    client = Anthropic(api_key=api_key)
    
    print(f"Verifying {len(leads)} leads against ICP criteria...")
    print(f"ICP: {icp_criteria}\n")
    
    verified_leads = []
    match_count = 0
    maybe_count = 0
    no_match_count = 0
    
    for idx, lead in enumerate(leads, 1):
        # Prepare lead summary for Claude
        lead_summary = f"""
Lead: {lead.get('full_name', 'Unknown')}
Title: {lead.get('title', 'Unknown')}
Company: {lead.get('company_name', 'Unknown')}
Location: {lead.get('location', 'Unknown')}
Headline: {lead.get('headline', 'N/A')}
"""
        
        # Ask Claude to verify
        prompt = f"""You are verifying if a LinkedIn lead matches the Ideal Customer Profile (ICP).

ICP Criteria: {icp_criteria}

Lead Information:
{lead_summary}

Task: Determine if this lead matches the ICP.

Respond in JSON format:
{{
  "match": "match" | "maybe" | "no_match",
  "reason": "Brief explanation (1 sentence)"
}}

Rules:
- "match": Clearly fits the ICP (e.g., exact title/role, right industry)
- "maybe": Partially fits (e.g., related role, adjacent industry, unclear info)
- "no_match": Does not fit (e.g., wrong role, wrong industry, clearly outside scope)
"""
        
        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",  # Cheap and fast for classification
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            
            # Parse JSON response
            result = json.loads(result_text)
            
            match_status = result["match"]
            reason = result["reason"]
            
            # Add verification to lead
            lead["icp_match"] = match_status
            lead["icp_reason"] = reason
            
            # Count matches
            if match_status == "match":
                match_count += 1
                icon = "✅"
            elif match_status == "maybe":
                maybe_count += 1
                icon = "❓"
            else:
                no_match_count += 1
                icon = "❌"
            
            print(f"{icon} Lead {idx}/{len(leads)}: {lead['full_name']} → {match_status}")
            print(f"   Reason: {reason}")
            
            verified_leads.append(lead)
            
        except Exception as e:
            print(f"⚠️  Error verifying lead {idx}: {e}")
            # Add as "maybe" if verification fails
            lead["icp_match"] = "maybe"
            lead["icp_reason"] = f"Verification failed: {str(e)}"
            verified_leads.append(lead)
            maybe_count += 1
    
    # Calculate match rate
    total = len(leads)
    match_rate = ((match_count + maybe_count) / total * 100) if total > 0 else 0
    
    # Print summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    print(f"Total leads: {total}")
    print(f"  ✅ Match: {match_count} ({match_count/total*100:.1f}%)")
    print(f"  ❓ Maybe: {maybe_count} ({maybe_count/total*100:.1f}%)")
    print(f"  ❌ No match: {no_match_count} ({no_match_count/total*100:.1f}%)")
    print(f"\nMatch rate (match + maybe): {match_rate:.1f}%")
    print("="*60)
    
    # Decision
    if match_rate >= 80:
        print("\n✅ PASS: Match rate ≥ 80%. Proceed with full scrape.")
    elif match_rate >= 60:
        print("\n⚠️  WARNING: Match rate 60-79%. Consider refining filters.")
    else:
        print("\n❌ FAIL: Match rate < 60%. Refine Sales Navigator filters.")
        print("\nSuggested actions:")
        
        # Analyze mismatches to suggest improvements
        wrong_titles = [l for l in verified_leads if l["icp_match"] == "no_match" and "title" in l["icp_reason"].lower()]
        wrong_industry = [l for l in verified_leads if l["icp_match"] == "no_match" and "industry" in l["icp_reason"].lower()]
        
        if wrong_titles:
            print("  - Adjust 'Job Titles' filter (many wrong roles found)")
        if wrong_industry:
            print("  - Adjust 'Industry' filter (many wrong industries found)")
        
        print("  - Try more specific keywords in Sales Navigator")
        print("  - Narrow geographic or company size filters")
    
    return verified_leads

def save_results(leads, output_path):
    """
    Save verified leads to JSON file.
    """
    os.makedirs(".tmp", exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(leads, f, indent=2)
    
    print(f"\n✅ Verified leads saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Verify LinkedIn leads against ICP")
    parser.add_argument("--input", required=True, help="Input JSON file (from scrape)")
    parser.add_argument("--icp_criteria", required=True, help="ICP criteria description")
    parser.add_argument("--output", default=".tmp/verified_leads.json", help="Output file path")
    
    args = parser.parse_args()
    
    # Load leads
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    with open(args.input, "r") as f:
        leads = json.load(f)
    
    if not leads:
        print("Error: No leads found in input file", file=sys.stderr)
        sys.exit(1)
    
    # Verify leads
    verified_leads = verify_leads(leads, args.icp_criteria)
    
    if not verified_leads:
        print("Verification failed.")
        sys.exit(1)
    
    # Save results
    save_results(verified_leads, args.output)
    
    # Exit with appropriate code
    total = len(verified_leads)
    match_count = len([l for l in verified_leads if l["icp_match"] == "match"])
    maybe_count = len([l for l in verified_leads if l["icp_match"] == "maybe"])
    match_rate = ((match_count + maybe_count) / total * 100) if total > 0 else 0
    
    if match_rate < 60:
        print("\n❌ Verification failed. Match rate too low.")
        sys.exit(1)
    elif match_rate < 80:
        print("\n⚠️  Verification passed with warning. Consider refining filters.")
        sys.exit(0)
    else:
        print("\n✅ Verification passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()


