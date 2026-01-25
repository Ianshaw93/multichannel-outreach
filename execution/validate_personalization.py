#!/usr/bin/env python3
"""
Validate personalized LinkedIn DMs against source profile data.
Uses LLM-as-judge to score accuracy of service/method/industry inferences.
"""

import os
import sys
import json
import argparse
import time
from dotenv import load_dotenv
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

VALIDATION_PROMPT = """You are a strict accuracy validator for LinkedIn outreach messages.

Given the INPUT DATA (what we know about this person) and the GENERATED MESSAGE (what we sent them), score the accuracy.

INPUT DATA:
- Full Name: {full_name}
- Headline: {headline}
- Job Title: {job_title}
- Job Description: {job_description}
- Company: {company}
- Company Description: {company_description}
- Company Industry: {company_industry}
- Summary: {summary}

GENERATED MESSAGE:
{personalized_message}

SCORE EACH (1-5 scale, where 1=completely wrong, 3=partially accurate, 5=spot on):

1. **Service Accuracy**: Does the "[service]" in "You guys do [service] right?" accurately reflect what the company actually does based on headline + company description?
   - Score 1 if the service is a complete mischaracterization (e.g., calling a peer network "executive search")
   - Score 3 if it's in the right ballpark but imprecise
   - Score 5 if it's exactly what they do

2. **Method Accuracy**: Is the "[method]" realistic for that service type?
   - Score 1 if the method makes no sense for their actual business
   - Score 3 if it's a reasonable guess
   - Score 5 if it's clearly how they operate

3. **Industry/Authority Relevance**: Does the authority statement (the "X is powerful/valuable" part) actually apply to their industry?
   - Score 1 if it references a completely different industry
   - Score 3 if it's adjacent but not quite right
   - Score 5 if it's directly relevant to what they do

Return ONLY valid JSON (no markdown, no explanation):
{{"service_score": X, "method_score": X, "authority_score": X, "avg_score": X.X, "inferred_service": "what message claims they do", "actual_service": "what they actually do based on data", "flag": "PASS|REVIEW|FAIL", "reason": "1-2 sentence explanation if REVIEW or FAIL"}}

Flag rules:
- PASS: avg_score >= 4.0
- REVIEW: avg_score >= 2.5 and < 4.0
- FAIL: avg_score < 2.5
"""


def validate_single(lead: dict, client: anthropic.Anthropic, model: str) -> dict:
    """Validate a single lead's personalized message."""
    prompt = VALIDATION_PROMPT.format(
        full_name=lead.get("full_name", ""),
        headline=lead.get("headline", "(not available)"),
        job_title=lead.get("job_title", "(not available)"),
        job_description=lead.get("job_description", "(not available)"),
        company=lead.get("company", "(not available)"),
        company_description=lead.get("company_description", "(not available)"),
        company_industry=lead.get("company_industry", "(not available)"),
        summary=lead.get("summary", "(not available)"),
        personalized_message=lead.get("personalized_message", "(no message)")
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()
        # Clean up potential markdown
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        result = json.loads(result_text)
        result["full_name"] = lead.get("full_name", "Unknown")
        result["linkedin_url"] = lead.get("linkedin_url", "")
        return result

    except json.JSONDecodeError as e:
        return {
            "full_name": lead.get("full_name", "Unknown"),
            "linkedin_url": lead.get("linkedin_url", ""),
            "error": f"JSON parse error: {e}",
            "raw_response": result_text if 'result_text' in dir() else "no response",
            "flag": "ERROR"
        }
    except Exception as e:
        return {
            "full_name": lead.get("full_name", "Unknown"),
            "linkedin_url": lead.get("linkedin_url", ""),
            "error": str(e),
            "flag": "ERROR"
        }


def validate_batch(input_file: str, output_file: str = None, sample_size: int = None, model: str = "claude-3-5-haiku-latest"):
    """Validate a batch of personalized messages."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Load leads
    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    # Filter to only leads with personalized_message
    leads_with_messages = [l for l in leads if l.get("personalized_message")]

    if sample_size and sample_size < len(leads_with_messages):
        import random
        leads_with_messages = random.sample(leads_with_messages, sample_size)

    print(f"Validating {len(leads_with_messages)} messages using {model}...")

    results = []

    # Process sequentially to avoid rate limits (Anthropic has lower limits)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(validate_single, lead, client, model): lead for lead in leads_with_messages}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)

            flag = result.get("flag", "ERROR")
            name = result.get("full_name", "Unknown")

            if flag == "FAIL":
                print(f"  [{i}/{len(leads_with_messages)}] FAIL: {name} - {result.get('reason', 'no reason')}")
            elif flag == "REVIEW":
                print(f"  [{i}/{len(leads_with_messages)}] REVIEW: {name} - {result.get('reason', 'no reason')}")
            elif flag == "ERROR":
                print(f"  [{i}/{len(leads_with_messages)}] ERROR: {name} - {result.get('error', 'unknown error')}")
            else:
                print(f"  [{i}/{len(leads_with_messages)}] PASS: {name}")

    # Summary stats
    passes = len([r for r in results if r.get("flag") == "PASS"])
    reviews = len([r for r in results if r.get("flag") == "REVIEW"])
    fails = len([r for r in results if r.get("flag") == "FAIL"])
    errors = len([r for r in results if r.get("flag") == "ERROR"])

    print(f"\n{'='*50}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*50}")
    print(f"Total validated: {len(results)}")
    print(f"  PASS:   {passes} ({100*passes/len(results):.1f}%)")
    print(f"  REVIEW: {reviews} ({100*reviews/len(results):.1f}%)")
    print(f"  FAIL:   {fails} ({100*fails/len(results):.1f}%)")
    print(f"  ERROR:  {errors} ({100*errors/len(results):.1f}%)")

    # Show fails and reviews
    if fails > 0:
        print(f"\n{'='*50}")
        print("FAILED MESSAGES (need correction):")
        print(f"{'='*50}")
        for r in results:
            if r.get("flag") == "FAIL":
                print(f"\n{r.get('full_name')} ({r.get('linkedin_url', 'no url')})")
                print(f"  Inferred service: {r.get('inferred_service', 'N/A')}")
                print(f"  Actual service:   {r.get('actual_service', 'N/A')}")
                print(f"  Scores: service={r.get('service_score')}, method={r.get('method_score')}, authority={r.get('authority_score')}")
                print(f"  Reason: {r.get('reason', 'no reason')}")

    if reviews > 0:
        print(f"\n{'='*50}")
        print("REVIEW NEEDED (borderline accuracy):")
        print(f"{'='*50}")
        for r in results:
            if r.get("flag") == "REVIEW":
                print(f"\n{r.get('full_name')} ({r.get('linkedin_url', 'no url')})")
                print(f"  Inferred service: {r.get('inferred_service', 'N/A')}")
                print(f"  Actual service:   {r.get('actual_service', 'N/A')}")
                print(f"  Scores: service={r.get('service_score')}, method={r.get('method_score')}, authority={r.get('authority_score')}")
                print(f"  Reason: {r.get('reason', 'no reason')}")

    # Save results
    if output_file is None:
        output_file = input_file.replace('.json', '_validation.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total": len(results),
                "pass": passes,
                "review": reviews,
                "fail": fails,
                "error": errors,
                "pass_rate": f"{100*passes/len(results):.1f}%"
            },
            "results": results
        }, f, indent=2)

    print(f"\nFull results saved to: {output_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate personalized LinkedIn DMs")
    parser.add_argument("input_file", help="JSON file with personalized messages")
    parser.add_argument("--output", "-o", help="Output file for validation results")
    parser.add_argument("--sample", "-s", type=int, help="Validate only N random samples")
    parser.add_argument("--model", "-m", default="claude-3-5-haiku-latest", help="Model to use for validation (default: claude-3-5-haiku-latest)")

    args = parser.parse_args()

    validate_batch(args.input_file, args.output, args.sample, args.model)
