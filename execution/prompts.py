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
  ● CRITICAL: If 
  headline/company        
  description are empty or   unavailable:
    - First check the     
  company name itself     
  (e.g., "Dean's Kid      
  Fashion" → "kid
  fashion")
    - Then check the      
  industry field if       
  available
    - Then use their job  
  title as the service    
  (e.g., "CFO" → "finance 
  leadership")
    - NEVER default to    
  "corporate comms" or    
  "communications
  strategy" - this is     
  almost always wrong     

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


LINKEDIN_BUYING_SIGNAL_DM_PROMPT = """You create LinkedIn DMs that reference a buying signal, then offer concrete value.

## TASK
Generate {line_count} lines:
1. **Greeting** → Hey [FirstName]
2. **Signal reference** → (see SIGNAL REFERENCE section below)
3. **Niche question** → You guys target [niche] right?
4. **Value offer** → (template, word-for-word — see below)
{location_task_line}

---

# SIGNAL REFERENCE (LINE 2)

{signal_instructions}

---

# NICHE QUESTION (LINE 3)

Template: You guys target [niche] right?

Rules:
● Infer [niche] from their headline, about section, company description, company name, industry, job title
● Use the headline + about section as PRIMARY signals — these describe what they actually do
● Company description tells you what the company sells and to whom
● [niche] = the TYPE OF CUSTOMER their company serves (not what the company does)
● Think: "Who is this company's ideal customer?"
● Keep it short — 1-4 words for the niche
● Casual tone

Examples:
● Company is an advertising agency → "You guys target ecom brands right?"
● Company does IT consulting → "You guys target mid-market SaaS right?"
● Company does executive search → "You guys target C-suite hires right?"
● Company does software development → "You guys target enterprise clients right?"
● Company does business consulting → "You guys target founders right?"
● Company does leadership coaching → "You guys target execs right?"

---

# VALUE OFFER (LINE 4)

Template (word-for-word, do NOT modify):
Actually spent 30mins looking up 10 prospects showing strong buying signals relevant to tht icp. Makes it WAAY easier speaking to a starving crowd. Lmk that's your icp and I'll send them across

{location_section}

---

# TEMPLATE INTEGRITY LAW

Line 4 is an EXACT template — word-for-word, including "tht" and "WAAY".
Only `[placeholders]` may be swapped.
No rephrasing. No "fixing" spelling. No adding punctuation.

---

# OUTPUT FORMAT

Always output EXACTLY {line_count} lines ({output_line_labels}).

Take a new paragraph (blank line) between each line.

Only output the line contents - NOT section labels like "Greeting:" or "Signal reference:". The full message will be sent on LinkedIn as is.

DO NOT include long dashes (---) in the output.
{no_location_reminder}

Only return the message - the full reply will be sent on LinkedIn directly.

---

Lead Information:
- First Name: {first_name}
- Company: {company_name}
- Title: {title}
- Industry: {industry}
- Location: {location}
{extra_lead_info}

Generate the complete {line_count}-line LinkedIn DM now. Return ONLY the message (no explanation, no labels, no formatting)."""


# --- Signal type: Post engagement ---

_POST_SIGNAL_INSTRUCTIONS = """Template: Saw you [liked/commented on] [Author]'s post on [topic summary] - this will be valuable for you

Rules:
● Alternate between "liked" and "commented on" — pick one naturally
● Use the post author's name as provided
● Summarise the post topic in a few natural words (not the full slug — make it human-readable)
● Use the intent keyword to understand what the post was about if the topic slug is unclear
● Always end with "- got something valuable for you"
● One line

Examples:
● "Saw you liked Naim Ahmed's post on LinkedIn outbound tips - got something valuable for you"
● "Saw you commented on SmartReach's post on measuring outreach activity - got something valuable for you"
● "Saw you liked Deepti Pahwa's post on cold email for decision makers - got something valuable for you"
● "Saw you commented on Alexandra Palau's post on cold outreach - got something valuable for you" """


# --- Signal type: Top 5% activity ---

_TOP5_SIGNAL_INSTRUCTIONS = """Template (word-for-word, do NOT modify):
My system's showing you as top 5% most active on here in terms of b2b founders/decision makers. Other signals like commenting relevant pain points or engaging in relevant posts would be ofc be stronger

Rules:
● This is an EXACT template — output it word-for-word including "ofc"
● Do NOT rephrase, shorten, or "improve" this line
● This replaces the post reference line when the signal is general activity, not a specific post"""


def get_linkedin_buying_signal_prompt(first_name, company_name, title, industry, location,
                                      post_author=None, post_topic=None, intent_keyword=None,
                                      signal_type="post", skip_location=False,
                                      headline=None, about=None, company_description=None):
    """
    Get the buying signal LinkedIn DM prompt with lead info filled in.

    signal_type: "post" for specific post engagement, "top5" for top 5% activity signal
    skip_location: if True, generates a 4-line message without the location hook
    headline/about/company_description: enriched profile data for better niche inference
    """
    # Build profile context lines
    profile_lines = []
    if headline:
        profile_lines.append(f"- Headline: {headline}")
    if about:
        profile_lines.append(f"- About: {about[:500]}")
    if company_description:
        profile_lines.append(f"- Company Description: {company_description[:500]}")

    if signal_type == "top5":
        signal_instructions = _TOP5_SIGNAL_INSTRUCTIONS
        extra_lead_info = "\n".join(profile_lines)
    else:
        signal_instructions = _POST_SIGNAL_INSTRUCTIONS
        post_lines = [
            f"- Post Author: {post_author or '(unknown author)'}",
            f"- Post Topic: {post_topic or '(unknown topic)'}",
            f"- Intent Keyword: {intent_keyword or '(not available)'}",
        ]
        extra_lead_info = "\n".join(post_lines + profile_lines)

    if skip_location:
        line_count = 4
        location_task_line = ""
        location_section = ""
        output_line_labels = "Greeting → Signal reference → Niche question → Value offer"
        no_location_reminder = "\nDo NOT include a location hook or any 5th line. End after the value offer."
    else:
        line_count = 5
        location_task_line = "5. **Location Hook** → (template, word-for-word — see below)"
        location_section = """---

# LOCATION HOOK TEMPLATE (LINE 5)

Template (word-for-word, only replace [city/region]):
See you're in [city/region]. Just been to Fort Lauderdale in the US - and I mean the airport lol Have so many connections now that I need to visit for real. I'm in Glasgow, Scotland"""
        output_line_labels = "Greeting → Signal reference → Niche question → Value offer → Location Hook"
        no_location_reminder = ""

    return LINKEDIN_BUYING_SIGNAL_DM_PROMPT.format(
        first_name=first_name,
        company_name=company_name,
        title=title,
        industry=industry or "(not available)",
        location=location,
        signal_instructions=signal_instructions,
        extra_lead_info=extra_lead_info,
        line_count=line_count,
        location_task_line=location_task_line,
        location_section=location_section,
        output_line_labels=output_line_labels,
        no_location_reminder=no_location_reminder,
    )


# =============================================================================
# GIFT LEADS LIST PROMPTS
# =============================================================================

PROSPECT_RESEARCH_PROMPT = """You are a B2B sales intelligence analyst. Analyze this LinkedIn profile to derive who their Ideal Customer Profile (ICP) would be, what pain points their prospects likely have, and what buying signals to look for.

## Profile Data
- Name: {name}
- Headline: {headline}
- About: {about}
- Company: {company}
- Industry: {industry}
- Experiences: {experiences}

## User-Provided Context (override if provided)
- ICP: {user_icp}
- Pain Points: {user_pain_points}

## Task
Analyze this person's business and output JSON with these fields:

{{
  "icp_description": "1-2 sentence description of who their ideal customers are",
  "target_titles": ["CEO", "Founder", ...],
  "target_industries": ["SaaS", "Agency", ...],
  "target_verticals": ["manufacturing", "HVAC", "construction", "industrial services"],
  "pain_points": ["scaling outbound", "lead generation", ...],
  "buying_signals": ["hiring SDRs", "discussing outbound challenges", ...],
  "buyer_intent_phrases": ["thinking about selling my business", "how to prepare for exit", "is now a good time to sell"],
  "search_angles": ["pain point discussions", "hiring signals", "industry trends"]
}}

Rules:
- If user provided ICP/pain points, use those as primary and supplement with profile analysis
- If no user context, derive everything from the profile
- Keep target_titles to 3-6 most relevant titles
- Keep pain_points to 3-5 specific, actionable pain points
- buying_signals should be things people would post or engage with on LinkedIn
- target_verticals: specific sub-industries or niches within their market (3-6). Think: what specific types of businesses does this person serve? E.g. an M&A advisor might serve manufacturing, HVAC, construction, industrial services.
- buyer_intent_phrases: natural-language phrases their ideal customers would post about or engage with on LinkedIn (3-5). Think: what is the prospect's client THINKING about? Not industry jargon — write from the buyer's perspective. E.g. "thinking about selling my business", "exit planning for business owners".
- Be specific to their industry, not generic

Respond ONLY with valid JSON."""


def get_prospect_research_prompt(name, headline, about, company, industry, experiences,
                                  user_icp=None, user_pain_points=None):
    """Get the prospect research prompt with profile data filled in."""
    return PROSPECT_RESEARCH_PROMPT.format(
        name=name or "Unknown",
        headline=headline or "(not available)",
        about=(about or "(not available)")[:500],
        company=company or "(not available)",
        industry=industry or "(not available)",
        experiences=experiences or "(not available)",
        user_icp=user_icp or "(not provided — derive from profile)",
        user_pain_points=user_pain_points or "(not provided — derive from profile)",
    )


GIFT_SEARCH_QUERY_PROMPT = """You are an expert at reverse-engineering LinkedIn post search queries for leadgen from any ICP profile.

Given a prospect's LinkedIn profile + their offer, generate **exactly 9 ultra-concise (2-3 word) search queries** across **3 angles** that will surface posts their ICP actually engages with.

## Prospect Profile
- Name: {prospect_name}
- Headline: {prospect_headline}
- Company: {prospect_company}
- ICP: {icp_description}

## Research Context
- Pain Points: {pain_points}
- Target Verticals: {target_verticals}
- Buying Signals: {buying_signals}

## Rules for queries
- 2-3 words ONLY. Never 4+ words. Shorter = better results.
- Use the ICP's insider terms/abbreviations (e.g. "ND" for naturopathic doctor, "M&A" for mergers & acquisitions)
- No complex booleans/quotes unless natural phrase
- Must return real LinkedIn results — think about what the ICP actually types/searches
- Focus where ICP comments/likes (pain, tools, authority)
- Do NOT include `site:linkedin.com/posts` or `after:` — those are added automatically

**Angle 1 — Founder Pain (1-3):**
Universal struggles their offer solves — use ICP niche + core pain word

**Angle 2 — Vertical-Specific (4-7):**
[ICP-NICHE] sub-types + their service hook — one vertical per query

**Angle 3 — Advisor/Thought-Leader Bait (8-9):**
Posts from [INDUSTRY] influencers/advisors that attract ICP

## Gold Standard Example 1

Prospect: Brody Zastrow — M&A advisor helping industrial business owners sell their companies.
ICP: Industrial business owners considering selling.

**Angle 1 — Founder Pain (1-3):**
1. `selling your business`
2. `exit planning business`
3. `prepare business sale`

**Angle 2 — Vertical-Specific (4-7):**
4. `sell manufacturing business`
5. `sell HVAC business`
6. `sell industrial company`
7. `sell construction company`

**Angle 3 — Advisor/Thought-Leader Bait (8-9):**
8. `M&A alive well`
9. `M&A mythbuster myths`

## Gold Standard Example 2

Prospect: Patrick Hennessy — Newsletter ghostwriter for naturopath founders.
ICP: Naturopath founders.

**Angle 1 — Founder Pain (1-3):**
1. `naturopath newsletter`
2. `ND patient retention`
3. `naturopath content`

**Angle 2 — Vertical-Specific (4-7):**
4. `functional medicine email`
5. `holistic health newsletter`
6. `naturopathic doctor content`
7. `integrative medicine patients`

**Angle 3 — Advisor/Thought-Leader Bait (8-9):**
8. `wellness authority naturopath`
9. `health practitioner newsletter`

Why these work: "naturopath newsletter" > "newsletter content struggle" because NDs search this exact phrase. "ND patient retention" > "time for marketing" because "ND" is their insider term and ties to the prospect's pitch. No 4-word phrases — LinkedIn search works best with 2-3 word combos the ICP actually uses.

## Output Format
Return valid JSON:
{{"queries": ["query one", "query two", ..., "query nine"]}}

Exactly 9 queries. 2-3 words each. No site: prefix. No after: suffix. Just the core search terms.

Respond ONLY with valid JSON."""


def get_gift_search_query_prompt(icp_description, pain_points, buying_signals,
                                  target_verticals=None, buyer_intent_phrases=None,
                                  days_back=14,
                                  prospect_name=None, prospect_headline=None,
                                  prospect_company=None):
    """Get the gift search query prompt with ICP data filled in."""
    if target_verticals and isinstance(target_verticals, list):
        verticals_str = ", ".join(target_verticals)
    else:
        verticals_str = target_verticals or "(derive from ICP)"

    return GIFT_SEARCH_QUERY_PROMPT.format(
        prospect_name=prospect_name or "Unknown",
        prospect_headline=prospect_headline or "(not available)",
        prospect_company=prospect_company or "(not available)",
        icp_description=icp_description,
        pain_points=", ".join(pain_points) if isinstance(pain_points, list) else pain_points,
        buying_signals=", ".join(buying_signals) if isinstance(buying_signals, list) else buying_signals,
        target_verticals=verticals_str,
    )


GIFT_SIGNAL_NOTE_PROMPT = """You generate concise signal notes explaining WHY a lead is relevant to a prospect's ICP.

## Prospect's ICP
{icp_description}

## Leads to Annotate
{leads_json}

## Task
For each lead, generate a 1-line signal note (max 100 characters) that explains:
- What engagement they showed (liked/commented on what topic)
- Why that makes them relevant to the prospect's ICP

## Output Format
Return a JSON array with one object per lead:
[
  {{"linkedin_url": "...", "signal_note": "Commented on post about scaling SDR teams — likely evaluating outbound tools"}},
  ...
]

Rules:
- Max 100 characters per signal_note
- Reference the engagement type and topic when available
- Connect to the prospect's ICP/pain points
- Use natural language, not marketing jargon
- Start with the engagement action: "Liked post about...", "Commented on...", "Engaged with..."

Respond ONLY with valid JSON."""


def get_gift_signal_note_prompt(icp_description, leads):
    """Get the signal note prompt with leads data filled in."""
    import json
    leads_summary = []
    for lead in leads:
        leads_summary.append({
            "linkedin_url": lead.get("linkedin_url") or lead.get("linkedinUrl", ""),
            "name": lead.get("name") or lead.get("fullName", "Unknown"),
            "title": lead.get("title") or lead.get("jobTitle", ""),
            "company": lead.get("company") or lead.get("companyName", ""),
            "engagement_type": lead.get("engagement_type", "LIKE"),
            "source_post_url": lead.get("source_post_url", ""),
        })
    return GIFT_SIGNAL_NOTE_PROMPT.format(
        icp_description=icp_description,
        leads_json=json.dumps(leads_summary, indent=2),
    )
