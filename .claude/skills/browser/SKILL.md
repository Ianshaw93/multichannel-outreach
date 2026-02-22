# /browser — Playwright Browser Automation

Headless browser automation with persistent login profiles. Use for scripted, repeatable workflows.

## Quick Start

```bash
# Write a script, then execute it
node .claude/skills/browser/run.js .tmp/pw-my-script.js

# Or pass inline code
node .claude/skills/browser/run.js "
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('https://example.com');
console.log(await page.title());
await browser.close();
"

# Self-test
node .claude/skills/browser/run.js test
```

## How It Works

1. **Write a script** to `.tmp/pw-<name>.js` using Playwright API
2. **Execute** via `node run.js <path>` — auto-wraps with Playwright imports
3. **Available globals**: `chromium`, `firefox`, `webkit`, `helpers`, `SKILL_DIR`, `TMP_DIR`

## Environment Variables

| Var | Effect |
|-----|--------|
| `VISIBLE=1` | Launch in headed mode (watch the browser) |
| `PROFILE=<name>` | Load named profile (e.g., `PROFILE=linkedin`) |
| `SLOWMO=<ms>` | Slow down every action by N ms |

## Helpers API

All helpers are available via `const helpers = require('./lib/helpers')` (auto-loaded as `helpers`).

### Browser Lifecycle
- `launchBrowser(options?)` — Launch Chromium (respects VISIBLE, SLOWMO)
- `createContext(browser, options?)` — Create context with viewport, UA, optional profile
- `createPage(context)` — New page with default timeouts
- `launchWithProfile(profileName, options?)` — All-in-one: returns `{ browser, context, page }`

### Profile Management
- `loadProfile(name)` — Load stored cookies/state, returns null if missing
- `saveProfile(name, context)` — Persist current session to `profiles/<name>/state.json`

### Page Interaction
- `waitForPageReady(page)` — Wait for DOM + network idle
- `safeClick(page, selector, options?)` — Click with retries
- `safeType(page, selector, text, options?)` — Type with optional clear
- `extractTexts(page, selector)` — Get text from all matching elements
- `extractTableData(page, tableSelector)` — Table → array of objects

### Screenshots
- `takeScreenshot(page, name, options?)` — Save to `.tmp/pw-<name>-<timestamp>.png`

### Scrolling
- `scrollPage(page, options?)` — Scroll down/up by amount, or `{ toBottom: true }`

### Retry
- `retryWithBackoff(fn, options?)` — Retry with exponential backoff

### LinkedIn
- `linkedinDelay(page, options?)` — Random 1-3s delay for rate limiting

### Paths
- `getTmpPath(filename)` — Get full path in `.tmp/`
- `SKILL_DIR`, `PROFILES_DIR`, `TMP_DIR` — Directory constants

## Patterns

### Login profile workflow
```js
// First time: login manually with VISIBLE=1, then save
// VISIBLE=1 PROFILE=linkedin node run.js .tmp/pw-login.js
const { browser, context, page } = await helpers.launchWithProfile('linkedin');
// ... navigate to login, enter credentials ...
await helpers.saveProfile('linkedin', context);
await browser.close();

// Later: reuse saved session
const { browser, context, page } = await helpers.launchWithProfile('linkedin');
await page.goto('https://www.linkedin.com/feed');
// Already logged in!
```

### Scrape with retry
```js
const data = await helpers.retryWithBackoff(async () => {
  const browser = await helpers.launchBrowser();
  const ctx = await helpers.createContext(browser);
  const page = await helpers.createPage(ctx);
  await page.goto('https://example.com/api');
  const text = await page.textContent('body');
  await browser.close();
  return JSON.parse(text);
});
```

### Screenshot pipeline
```js
const browser = await helpers.launchBrowser();
const ctx = await helpers.createContext(browser);
const page = await helpers.createPage(ctx);

const urls = ['https://example.com', 'https://example.org'];
for (const url of urls) {
  await page.goto(url);
  await helpers.waitForPageReady(page);
  await helpers.takeScreenshot(page, new URL(url).hostname);
}
await browser.close();
```

## When to use /browser vs /chrome

| Use `/browser` when... | Use `/chrome` when... |
|------------------------|----------------------|
| Headless automation at scale | Need real login state |
| Repeatable scripted workflows | Exploring interactively |
| Batch scraping with retries | One-off data extraction |
| CI/CD pipelines | Debugging page behavior |
| Screenshot pipelines | Testing with real cookies |

## File Output

Save all output to `.tmp/`:
```
.tmp/pw-script.js          # Your scripts
.tmp/pw-screenshot-*.png   # Screenshots
.tmp/pw-data-*.json        # Extracted data
```
