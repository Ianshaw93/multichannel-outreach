# LinkedIn Intent Signal System

Gojiberry-style intent signal monitoring for finding warm leads with buying intent.

## Quick Start

### 1. Test Keyword Engagement Monitor

```bash
python execution/keyword_engagement_monitor.py --keywords "struggling with outbound" --dry_run
```

### 2. Test Competitor Monitor (Manual Post URLs Required)

```bash
# Get post URLs from competitor profile, then:
python execution/competitor_monitor.py \
  --competitor_name "Competitor CEO" \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run
```

### 3. Test Influencer Monitor (Manual Post URLs Required)

```bash
# Get post URLs from influencer profile, then:
python execution/influencer_monitor.py \
  --influencer_name "Alex Hormozi" \
  --post_urls "https://linkedin.com/posts/abc123" \
  --dry_run
```

### 4. Review & Upload

```bash
# 1. Review JSON output in .tmp/ directory
# 2. Edit JSON, set "approved": true for leads you want
# 3. Upload approved leads to HeyReach:

python execution/json_to_heyreach.py \
  --input .tmp/keyword_engagement_*.json \
  --list_id 480247
```

## What's New vs. Old System

**OLD System (`competitor_post_pipeline.py`):**
- ❌ Generic keyword search for "ceos"
- ❌ Not monitoring actual competitors
- ❌ Random people, no intent signals

**NEW System (3 Intent Signals):**
- ✅ **Keyword Monitor** - Pain points ("struggling with outbound")
- ✅ **Competitor Monitor** - Specific competitor accounts
- ✅ **Influencer Monitor** - Specific thought leaders
- ✅ TRUE intent signals = warm leads

## Files Created

```
config/
  - keyword_signals.json      # Pain point keywords config
  - competitors.json          # Competitor accounts to monitor
  - influencers.json          # Influencer accounts to monitor

execution/
  - keyword_engagement_monitor.py   # Signal #1: Keyword engagement
  - competitor_monitor.py           # Signal #2: Competitor monitoring
  - influencer_monitor.py           # Signal #3: Influencer monitoring
  - json_to_heyreach.py             # Manual review → upload tool

directives/
  - intent_signal_system.md         # Complete documentation
```

## Configuration

Edit config files to customize:

- `config/keyword_signals.json` - Add pain point keywords
- `config/competitors.json` - Add competitor LinkedIn URLs
- `config/influencers.json` - Add influencer LinkedIn URLs

## Full Documentation

See [`directives/intent_signal_system.md`](directives/intent_signal_system.md) for:
- Complete usage examples
- Configuration details
- Testing workflow
- Troubleshooting
- Cost estimates

## Next Steps

1. **Test each signal** with real data
2. **Tune ICP criteria** based on results
3. **Expand configs** with more competitors/influencers
4. **(Optional) Build autopilot** if manual testing successful
