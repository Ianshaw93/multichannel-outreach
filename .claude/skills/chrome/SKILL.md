# /chrome — Real Chrome Browser Control

Use your built-in Chrome integration (`--chrome` flag) to browse as a human with real login sessions.

## When to use /chrome vs /browser

| Use `/chrome` when... | Use `/browser` when... |
|----------------------|----------------------|
| Need real login state (LinkedIn, Google) | Headless automation at scale |
| Exploring/debugging a page interactively | Repeatable scripted workflows |
| One-off data extraction | Batch scraping with retries |
| Testing what a page looks like | Screenshot pipelines |

## Prerequisites

Claude Code must be launched with `--chrome` flag:
```bash
claude --chrome
```

## Workflow

### 1. Verify connection
Check that `browser_*` tools are available. If not, tell the user to restart with `--chrome`.

### 2. Set viewport (do this first every time)
```
browser_evaluate: window.innerWidth + 'x' + window.innerHeight
```
If not 1280x800, resize:
```
browser_evaluate: document.documentElement.style.zoom = '1'
```

### 3. Navigate
```
browser_navigate: https://linkedin.com/feed
```

### 4. Interact
```
browser_click: selector="#global-nav-search button"
browser_type: selector="input[role=combobox]" text="VP Sales healthcare"
browser_screenshot
```

### 5. Extract data
```
browser_evaluate: JSON.stringify(Array.from(document.querySelectorAll('.entity-result__title-text a')).map(a => ({name: a.textContent.trim(), url: a.href})))
```

## LinkedIn-Specific Patterns

### Search
1. Navigate to `https://www.linkedin.com/search/results/people/`
2. Use the search bar or URL params: `?keywords=VP+Sales&origin=GLOBAL_SEARCH_HEADER`
3. Extract results with `browser_evaluate`

### Profile scraping
1. Navigate to profile URL
2. Screenshot for visual context
3. Use `browser_evaluate` to extract structured data from DOM

### Connection requests
1. Navigate to profile
2. Click "Connect" button
3. If "Add a note" appears, type personalized message
4. Click "Send"

## Anti-detection notes

- This IS a real Chrome browser with real cookies — no detection risk
- Still add human-like delays between actions (1-3 seconds)
- Don't rapid-fire hundreds of actions — LinkedIn tracks velocity
- If you hit "security verification", stop and tell the user

## Output

Save extracted data to `.tmp/` as JSON or CSV. Use descriptive filenames:
```
.tmp/chrome_linkedin_search_vp_sales_20260222.json
```
