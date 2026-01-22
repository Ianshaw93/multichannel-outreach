#!/usr/bin/env python3
"""
Central source of truth for all AI prompts used in the pipeline.
All scripts should import from here to ensure consistency.
"""

LINKEDIN_5_LINE_DM_PROMPT = """You create **5-line LinkedIn DMs** that feel personal and conversational — balancing business relevance with personal connection and strict template wording.

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
● Note: Unless their company name is one word shorten it (remove commas, LTD, Inc, Corp, etc):

Examples:
● "Immersion Data Solutions, LTD" → "IDS looks interesting"
● "The NS Marketing Agency" → "NS Marketing looks interesting"
● "Coca Cola LTD" → "Coca Cola looks interesting"
● "Megafluence, Inc." → "MF looks interesting"

---

# BUSINESS INQUIRY TEMPLATE (LINE 3)

Template: You guys do [service] right? Do that w [method]? Or what

Rules:
● Infer [service] from their headline and company description (NOT just title/company name)
● The headline tells you what they do professionally
● The company description tells you what service their company sells
● Infer [method] based on common methods for that service
● Keep it casual and conversational
● Use "w" instead of "with"

Examples:
● You guys do paid ads right? Do that w Google + Meta? Or what
● You guys do outbound right? Do that w LinkedIn + email? Or what
● You guys do branding right? Do that w design + positioning? Or what
● You guys do executive search right? Do that w retained + contingency? Or what
● You guys do lead gen right? Do that w LinkedIn + cold email? Or what
● You guys do HR consulting right? Do that w culture audits + talent strategy? Or what

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
A simple, universally true industry insight. Examples:
● "Ecom is a tough nut to crack."
● "Strong branding is so powerful."
● "Compliance is a must."
● "Outbound is a tough nut to crack."
● "A streamlined CRM is so valuable."
● "Podcasting is powerful."
● "Analytics is valuable."
● "VA placement is so valuable."
● "Leadership development is so powerful."
● "Executive search is so powerful."


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

6. Every final line MUST connect to Business Outcomes (money / revenue / scaling / clients).
Tie the idea directly to something founders actually care about. Examples (do NOT alter these):
Examples you MUST use as models:
● “So downtime saved alone makes it a no-brainer.”
● “Often comes down to having a brand/offer that’s truly different.”
● “Without proper tracking you’re literally leaving revenue on the table.”
● “Great way to build trust at scale with your ideal audience.”
● “Higher margins and faster scaling for companies that use them right.”
● “Nice way to see revenue leaks and double down on what works.”
● “Really comes down to precise targeting + personalisation to book clients at a high
level.”
● "Such a strong lever to pull."

7. Use the Founder Voice. Read it as if you were DM'ing a sophisticated founder. Short, direct, conversational.

8. Everything must be TRUE. If the industry reality is not obvious, you must adjust the statement to something factual.

EXACT EXEMPLARS (DO NOT MODIFY
THESE)
Use these as your reference for tone, length, structure, and sharpness.
Podcasting
“Podcasting is powerful
Great way to build trust at scale with your ideal audience.”
Ecom
“Ecom is a tough nut to crack
Often comes down to having a brand/offer that’s truly different.”
CRM
“A streamlined CRM is so valuable
Without proper tracking you’re leaving revenue on the table.”
Outbound
“Outbound is a tough nut to crack
Really comes down to precise targeting/personalisation to book clients at a high level.”
Analytics
“Analytics are so valuable
Gotta act on revenue leaks and double down on what works.”
VA Placement
“VA placement is so valuable
Higher margins and faster scaling for companies that use them right”

� BEFORE → AFTER EXAMPLES
(EXACT TEXT—DO NOT MODIFY)
Use these to understand how to transform bad/fluffy statements into good ones.
❌ BEFORE
“Podcasting is powerful.
Attention is hard to get. Clean production keeps listeners coming back.”
✔ AFTER
“Podcasting is powerful.
Great way to build trust at scale with your ideal audience.”
❌ BEFORE
“CRM is so powerful.
Helps you manage your leads efficiently so you don’t miss out on potential sales.”
✔ AFTER
“A streamlined CRM is so valuable.
Without proper tracking you’re leaving revenue on the table.”
❌ BEFORE
“Outbound is a tough nut to crack.
Response rates are low, making it hard to reach decision-makers.”
✔ AFTER
“Outbound is a tough nut to crack.
Really comes down to precise targeting and personalized messaging to book clients at a high
level.”
❌ BEFORE
“VA placement is underrated.
It connects businesses with skilled remote assistants.”
✔ AFTER
“VA placement is so valuable.
Higher margins and faster scaling for companies that use them right.”

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
- Headline: {headline}
- Company Description: {company_description}
- Location: {location}

Generate the complete 5-line LinkedIn DM now. Return ONLY the message (no explanation, no labels, no formatting)."""


def get_linkedin_5_line_prompt(first_name, company_name, title, headline, company_description, location):
    """
    Get the LinkedIn 5-line DM prompt with lead info filled in.

    Args:
        first_name: Lead's first name
        company_name: Lead's company name
        title: Lead's job title
        headline: Lead's LinkedIn headline (key for understanding what they do)
        company_description: Company's LinkedIn description (key for understanding their service)
        location: Lead's location/city

    Returns:
        Formatted prompt string ready for LLM
    """
    return LINKEDIN_5_LINE_DM_PROMPT.format(
        first_name=first_name,
        company_name=company_name,
        title=title,
        headline=headline or "(not available)",
        company_description=company_description or "(not available)",
        location=location
    )
