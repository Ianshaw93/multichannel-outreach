# Changelog - Personalization Funnel

## 2026-01-25: Message Accuracy Validation

### Issue Identified
Received reply from prospect (Bea Sonnendecker, SuiteC) indicating personalized message mischaracterized her business:
- **Message claimed**: "executive search or advisory"
- **Actual business**: "private, invite-only peer network for senior operators"

### Root Cause Analysis
The `LINKEDIN_5_LINE_DM_PROMPT` in `execution/prompts.py` instructs:
> "Infer [service] from their headline and company description"

The LLM latches onto keywords (e.g., "executive", "senior", "leadership") and maps to common service categories, but fails on nuanced business models:
- Peer networks → mischaracterized as "executive search" or "advisory"
- Membership communities → mischaracterized as "consulting"
- Platform businesses → mischaracterized as "services"

### Actions Taken

1. **Created validation script** (`execution/validate_personalization.py`)
   - LLM-as-judge to score message accuracy against profile data
   - Scores: service accuracy, method accuracy, authority relevance
   - Flags: PASS (>=4.0), REVIEW (2.5-4.0), FAIL (<2.5)
   - Note: Currently requires ANTHROPIC_API_KEY in .env to run

2. **Created manual review export** (`execution/export_validation_review.py`)
   - Exports CSV with side-by-side comparison columns
   - Extracts inferred service/method from message
   - Includes headline + company description for quick comparison
   - Run: `python execution/export_validation_review.py .tmp/<file>.json --sample 30`

3. **Generated review file**
   - `.tmp/vayne_prospects_200_personalized_review.csv`
   - 30 samples for manual accuracy scoring

### Proposed Prompt Fix (requires user approval)

Add to `LINKEDIN_5_LINE_DM_PROMPT` Line 3 rules:

```
ACCURACY GUARD RAILS:
- DO NOT assume "executive" in headline = "executive search"
- DO NOT assume "network" or "community" = "consulting" or "advisory"
- Peer networks, membership communities, and platforms are NOT service businesses
- When business model is unclear, ask about their PRIMARY offering (not inferred category)
- If company description mentions "peer network", "membership", "community", "platform" - describe it that way, not as a service

MISCHARACTERIZATION EXAMPLES TO AVOID:
- "peer network for executives" ≠ "executive search"
- "leadership community" ≠ "leadership consulting"
- "invite-only network" ≠ "advisory services"
```

### Next Steps

1. [ ] Review `.tmp/vayne_prospects_200_personalized_review.csv` - score 10-20 manually
2. [ ] Identify patterns in FAIL cases (which service categories get mischaracterized?)
3. [ ] Get approval to update `prompts.py` with guard rails
4. [ ] Re-run personalization on a test batch to verify improvement
5. [ ] Set up ongoing validation (run on 10% sample before sending)

### Files Changed
- `execution/validate_personalization.py` (new)
- `execution/export_validation_review.py` (new)
- `.tmp/vayne_prospects_200_personalized_review.csv` (new)
