#!/usr/bin/env python3
"""
Quick test of the new ChatGPT 5.2 LinkedIn personalization
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Test with a few sample leads
test_leads = [
    {
        "first_name": "Brian",
        "company_name": "Rabben Hood Ventures",
        "title": "Founding Partner",
        "location": "United States"
    },
    {
        "first_name": "Carlos",
        "company_name": "Peoplebound",
        "title": "Managing Partner",
        "location": "Tucson, Arizona"
    },
    {
        "first_name": "Laura",
        "company_name": "HVM Communications",
        "title": "Founder / CEO",
        "location": "New York, New York"
    }
]

# The full ChatGPT 5.2 prompt from generate_personalization.py
prompt_template = """You create **5-line LinkedIn DMs** that feel personal and conversational — balancing business relevance with personal connection and strict template wording.

## TASK
Generate 5 lines:
1. **Greeting** → Hey [FirstName]
2. **Profile hook** → [CompanyName] looks interesting
3. **Business related Inquiry** → You guys do [service] right? Do that w [method]? Or what
4. **Authority building Hook** → 2-line authority statement based on industry (see rules below)
5. **Location Hook** → See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland

---

# PROFILE HOOK TEMPLATE (LINE 2)

Template: [CompanyName] looks interesting

Rules:
● Use their current company name (not past companies)
● Always "looks interesting" (not "sounds interesting" or other variations)
● No exclamation marks
● Keep it casual

Examples:
● War Room looks interesting
● KTM Agency looks interesting
● Immersion Data Solutions looks interesting
● NS Marketing looks interesting

Note: If company name is very long, you can shorten:
● "Immersion Data Solutions" → "IDS looks interesting"
● "The NS Marketing Agency" → "NS Marketing looks interesting"

---

# BUSINESS INQUIRY TEMPLATE (LINE 3)

Template: You guys do [service] right? Do that w [method]? Or what

Rules:
● Infer [service] from their company/title (e.g., "paid ads", "branding", "outbound", "CRM", "analytics")
● Infer [method] based on common methods for that service
● Keep it casual and conversational
● Use "w" instead of "with"

Examples:
● You guys do paid ads right? Do that w Google + Meta? Or what
● You guys do outbound right? Do that w LinkedIn + email? Or what
● You guys do branding right? Do that w design + positioning? Or what

---

# AUTHORITY STATEMENT GENERATION (LINE 4 - 2 LINES)

You MUST follow the exact template, rules, and constraints below. Do not deviate from examples or structure.

Your job is to generate short, punchy authority statements that:
● Sound like a founder talking to another founder
● Contain zero fluff
● Tie everything to business outcomes (revenue, scaling, margins, clients, CAC, downtime, etc.)
● Always follow the 2-line template
● Contain only true statements
● Use simple, natural, conversational language
● Are industry-accurate
● Are 2 lines maximum

## AUTHORITY STATEMENT TEMPLATE (MANDATORY)

**Line 1 — X is Y.**
A simple, universally true industry insight. Examples (do NOT alter these):
● "Ecom is a tough nut to crack."
● "Branding is so powerful."
● "Compliance is a must."
● "Outbound is a tough nut to crack."
● "A streamlined CRM is so valuable."
● "Podcasting is powerful."
● "Analytics is valuable."
● "VA placement is so valuable."

**Line 2 — Business outcome (money / revenue / scaling / clients).**
Tie the idea directly to something founders actually care about. Examples (do NOT alter these):
● "Often comes down to having a brand/offer that's truly different."
● "Without proper tracking you're literally leaving revenue on the table."
● "Great way to build trust at scale with your ideal audience."
● "So downtime saved alone makes it a no-brainer."
● "Nice way to see revenue leaks and double down on what works."
● "Higher margins and faster scaling for companies that use them right."
● "Really comes down to precise targeting + personalisation to book clients at a high level."

## RULES YOU MUST FOLLOW (NON-NEGOTIABLE)

1. The result must always be EXACTLY 2 lines. Never more, never fewer.

2. No fluff. No generic statements. No teaching tone.
Avoid phrases like:
● "helps businesses…"
● "keeps things running smoothly…"
● "boosts adoption fast…"
● "improves efficiency…"
● "keeps listeners engaged…"
● "help manage leads efficiently…"
These are forbidden.

3. No repeating the same idea twice.
Avoid tautologies such as:
● "Inboxes are crowded. Response rates are low."
● "Hiring is tough. Most candidates are similar."
Only one cause per example.

4. Every term MUST be used accurately.
If referencing: CRM, analytics, demand gen, attribution, compliance, margins, downtime, CAC, outbound, SQL/Sales pipeline, etc.
→ You MUST demonstrate correct real-world understanding.
Never misuse terms.

5. "Underrated" may only be used when the thing is ACTUALLY underrated.
Cybersecurity, VAs, branding, and CRM are NOT underrated.
Examples you MUST respect:
● ✔ "VA placement is so valuable."
● ✔ "Cybersecurity is valuable."
● ❌ "VA placement is underrated."
● ❌ "Cybersecurity is underrated."

6. Every final line MUST connect to MONEY.

7. Use the Founder Voice. Read it as if you were DM'ing a sophisticated founder. Short, direct, conversational.

8. Everything must be TRUE. If the industry reality is not obvious, you must adjust the statement to something factual.

---

# LOCATION HOOK TEMPLATE (LINE 5)

Template (word-for-word, only replace [city/region]):
See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland

---

# TEMPLATE INTEGRITY LAW

Templates must be word-for-word.
Only `[placeholders]` may be swapped.
No rephrasing.

---

# OUTPUT FORMAT

Always output 5 lines (Greeting → Profile hook → Business Inquiry → Authority Statement → Location Hook).

Take a new paragraph (blank line) between each line.

Only output the line contents - NOT section labels like "Greeting:" or "Authority Building Hook:". The full message will be sent on LinkedIn as is.

DO NOT include long dashes (---) in the output.

Only return the message - the full reply will be sent on LinkedIn directly.

---

Lead Information:
- First Name: {first_name}
- Company: {company_name}
- Title: {title}
- Location: {location}

Generate the complete 5-line LinkedIn DM now. Return ONLY the message (no explanation, no labels, no formatting)."""

def test_personalization(lead):
    """Test the personalization for one lead"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in .env")
        return None

    client = OpenAI(api_key=api_key)

    # Fill in the prompt
    prompt = prompt_template.format(
        first_name=lead["first_name"],
        company_name=lead["company_name"],
        title=lead["title"],
        location=lead["location"]
    )

    try:
        print(f"\n{'='*80}")
        print(f"Testing: {lead['first_name']} - {lead['title']} at {lead['company_name']}")
        print(f"{'='*80}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )

        message = response.choices[0].message.content.strip()

        # Clean up any quotes or formatting
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        message = message.replace("```", "").strip()

        print("\nGENERATED MESSAGE:")
        print("-" * 80)
        print(message)
        print("-" * 80)

        return message

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print("\nTesting ChatGPT 5.2 LinkedIn Personalization")
    print("=" * 80)

    for lead in test_leads:
        result = test_personalization(lead)
        if not result:
            print("Test failed!")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)
