/**
 * helpers.js — Utility functions for Playwright browser automation
 *
 * Adapted from lackeyjb/playwright-skill with additions for
 * profile management and LinkedIn-specific patterns.
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const SKILL_DIR = path.join(__dirname, '..');
const PROFILES_DIR = path.join(SKILL_DIR, 'profiles');
const TMP_DIR = path.join(SKILL_DIR, '..', '..', '..', '.tmp');

// ─── Browser Lifecycle ───────────────────────────────────────

/**
 * Launch a Chromium browser instance.
 * Respects VISIBLE and SLOWMO env vars.
 */
async function launchBrowser(options = {}) {
  const headless = process.env.VISIBLE !== '1' && !options.visible;
  const slowMo = parseInt(process.env.SLOWMO || '0', 10) || options.slowMo || 0;

  return chromium.launch({
    headless,
    slowMo,
    ...options,
  });
}

/**
 * Create a browser context, optionally loading a named profile.
 */
async function createContext(browser, options = {}) {
  const profileName = process.env.PROFILE || options.profile;
  let storageState;

  if (profileName) {
    storageState = await loadProfile(profileName);
  }

  return browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    ...(storageState ? { storageState } : {}),
    ...options,
  });
}

/**
 * Create a new page with common defaults.
 */
async function createPage(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.setDefaultNavigationTimeout(30000);
  return page;
}

/**
 * Launch browser + context + page in one call.
 * Returns { browser, context, page }.
 */
async function launchWithProfile(profileName, options = {}) {
  const browser = await launchBrowser(options);
  const context = await createContext(browser, { profile: profileName, ...options });
  const page = await createPage(context);
  return { browser, context, page };
}

// ─── Profile Management ──────────────────────────────────────

/**
 * Load a named profile's storage state. Returns null if not found.
 */
async function loadProfile(name) {
  const profileDir = path.join(PROFILES_DIR, name);
  const statePath = path.join(profileDir, 'state.json');

  if (!fs.existsSync(statePath)) {
    return null;
  }

  return JSON.parse(fs.readFileSync(statePath, 'utf-8'));
}

/**
 * Save current context's storage state to a named profile.
 */
async function saveProfile(name, context) {
  const profileDir = path.join(PROFILES_DIR, name);
  fs.mkdirSync(profileDir, { recursive: true });

  const statePath = path.join(profileDir, 'state.json');
  const state = await context.storageState();
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));

  console.log(`Profile saved: ${statePath}`);
  return state;
}

// ─── Page Interaction ────────────────────────────────────────

/**
 * Wait for page to be fully loaded and idle.
 */
async function waitForPageReady(page, options = {}) {
  const { timeout = 30000 } = options;

  await page.waitForLoadState('domcontentloaded', { timeout });

  // Wait for network to quiet down
  try {
    await page.waitForLoadState('networkidle', { timeout: 10000 });
  } catch (e) {
    // networkidle can be flaky; don't fail on it
  }
}

/**
 * Click an element safely with retry logic.
 */
async function safeClick(page, selector, options = {}) {
  const { timeout = 10000, retries = 2 } = options;

  for (let i = 0; i <= retries; i++) {
    try {
      await page.waitForSelector(selector, { timeout, state: 'visible' });
      await page.click(selector);
      return true;
    } catch (err) {
      if (i === retries) {
        console.error(`safeClick failed for "${selector}": ${err.message}`);
        return false;
      }
      await page.waitForTimeout(500);
    }
  }
}

/**
 * Type into an element safely with optional clearing.
 */
async function safeType(page, selector, text, options = {}) {
  const { clear = true, delay = 50, timeout = 10000 } = options;

  await page.waitForSelector(selector, { timeout, state: 'visible' });

  if (clear) {
    await page.click(selector, { clickCount: 3 });
    await page.keyboard.press('Backspace');
  }

  await page.type(selector, text, { delay });
}

/**
 * Extract text content from all elements matching a selector.
 */
async function extractTexts(page, selector) {
  return page.$$eval(selector, els => els.map(el => el.textContent.trim()));
}

/**
 * Extract a table as an array of objects (headers → values).
 */
async function extractTableData(page, tableSelector) {
  return page.$eval(tableSelector, table => {
    const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
    const rows = Array.from(table.querySelectorAll('tbody tr'));

    return rows.map(row => {
      const cells = Array.from(row.querySelectorAll('td')).map(td => td.textContent.trim());
      const obj = {};
      headers.forEach((h, i) => { obj[h] = cells[i] || ''; });
      return obj;
    });
  });
}

// ─── Screenshots ─────────────────────────────────────────────

/**
 * Take a screenshot, saved to .tmp/ with a descriptive name.
 */
async function takeScreenshot(page, name, options = {}) {
  if (!fs.existsSync(TMP_DIR)) {
    fs.mkdirSync(TMP_DIR, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = `pw-${name}-${timestamp}.png`;
  const filepath = path.join(TMP_DIR, filename);

  await page.screenshot({
    path: filepath,
    fullPage: options.fullPage || false,
    ...options,
  });

  console.log(`Screenshot saved: ${filepath}`);
  return filepath;
}

// ─── Scrolling ───────────────────────────────────────────────

/**
 * Scroll the page by a given amount or to bottom.
 */
async function scrollPage(page, options = {}) {
  const { direction = 'down', amount = 500, toBottom = false } = options;

  if (toBottom) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  } else {
    const delta = direction === 'down' ? amount : -amount;
    await page.evaluate(d => window.scrollBy(0, d), delta);
  }

  await page.waitForTimeout(500); // Let content load
}

// ─── Retry Logic ─────────────────────────────────────────────

/**
 * Retry an async function with exponential backoff.
 */
async function retryWithBackoff(fn, options = {}) {
  const { maxRetries = 3, baseDelay = 1000, maxDelay = 10000 } = options;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxRetries) throw err;
      const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
      console.log(`Retry ${attempt + 1}/${maxRetries} after ${delay}ms: ${err.message}`);
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

// ─── LinkedIn Helpers ────────────────────────────────────────

/**
 * Add a human-like delay (1-3 seconds) to avoid LinkedIn rate limiting.
 */
async function linkedinDelay(page, options = {}) {
  const { min = 1000, max = 3000 } = options;
  const delay = Math.floor(Math.random() * (max - min + 1)) + min;
  await page.waitForTimeout(delay);
}

// ─── Path Helpers ────────────────────────────────────────────

/**
 * Get a path in the .tmp/ directory.
 */
function getTmpPath(filename) {
  if (!fs.existsSync(TMP_DIR)) {
    fs.mkdirSync(TMP_DIR, { recursive: true });
  }
  return path.join(TMP_DIR, filename);
}

// ─── Exports ─────────────────────────────────────────────────

module.exports = {
  // Browser lifecycle
  launchBrowser,
  createContext,
  createPage,
  launchWithProfile,

  // Profile management
  loadProfile,
  saveProfile,

  // Page interaction
  waitForPageReady,
  safeClick,
  safeType,
  extractTexts,
  extractTableData,

  // Screenshots
  takeScreenshot,

  // Scrolling
  scrollPage,

  // Retry
  retryWithBackoff,

  // LinkedIn
  linkedinDelay,

  // Paths
  getTmpPath,
  SKILL_DIR,
  PROFILES_DIR,
  TMP_DIR,
};
