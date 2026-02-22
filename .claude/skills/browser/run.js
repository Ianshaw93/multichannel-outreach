#!/usr/bin/env node
/**
 * run.js — Universal Playwright script executor
 *
 * Usage:
 *   node run.js <script-path>        Execute a .js file
 *   node run.js "<inline-code>"      Execute inline code (quoted string)
 *   node run.js test                 Run a quick self-test
 *
 * The script/code is wrapped with Playwright imports so you can use
 * `chromium`, `firefox`, `webkit` directly. The `helpers` module is
 * also available via require('./lib/helpers').
 *
 * Flags (via env vars):
 *   VISIBLE=1          Launch browser in headed mode
 *   PROFILE=<name>     Load/save named profile (e.g. PROFILE=linkedin)
 *   SLOWMO=<ms>        Slow down actions by N ms
 */

const fs = require('fs');
const path = require('path');
const { chromium, firefox, webkit } = require('playwright');

const SKILL_DIR = __dirname;
const TMP_DIR = path.join(SKILL_DIR, '..', '..', '..', '.tmp');

async function main() {
  const arg = process.argv[2];

  if (!arg) {
    console.error('Usage: node run.js <script.js | "inline code" | test>');
    process.exit(1);
  }

  // Self-test mode
  if (arg === 'test') {
    return runSelfTest();
  }

  // Determine if arg is a file path or inline code
  let code;
  if (fs.existsSync(arg)) {
    code = fs.readFileSync(arg, 'utf-8');
  } else if (arg.includes('\n') || arg.includes('await') || arg.includes('const ') || arg.includes('require(')) {
    code = arg;
  } else {
    // Try as file path relative to CWD and .tmp
    const candidates = [
      path.resolve(arg),
      path.join(TMP_DIR, arg),
      path.join(TMP_DIR, `pw-${arg}.js`),
    ];
    const found = candidates.find(f => fs.existsSync(f));
    if (found) {
      code = fs.readFileSync(found, 'utf-8');
    } else {
      console.error(`Cannot find script: ${arg}`);
      console.error('Tried:', candidates.join(', '));
      process.exit(1);
    }
  }

  await executeCode(code);
}

async function executeCode(code) {
  // Wrap user code in an async IIFE with Playwright globals available
  const wrappedCode = `
    const { chromium, firefox, webkit } = require('playwright');
    const path = require('path');
    const fs = require('fs');

    // Make helpers available
    const helpersPath = path.join(${JSON.stringify(SKILL_DIR)}, 'lib', 'helpers.js');
    let helpers;
    try { helpers = require(helpersPath); } catch(e) { helpers = null; }

    const SKILL_DIR = ${JSON.stringify(SKILL_DIR)};
    const TMP_DIR = ${JSON.stringify(TMP_DIR)};

    (async () => {
      try {
        ${code}
      } catch (err) {
        console.error('Script error:', err.message);
        console.error(err.stack);
        process.exit(1);
      }
    })();
  `;

  // Write temp file in skill dir root so:
  // 1. require('./lib/helpers') resolves correctly (same level as lib/)
  // 2. Inherits skill's package.json (CommonJS, not project root's ESM)
  const tmpFile = path.join(SKILL_DIR, `.pw-exec-${Date.now()}.js`);
  fs.writeFileSync(tmpFile, wrappedCode);

  try {
    // Use child_process to run the temp file so it gets a clean require context
    const { execSync } = require('child_process');
    const result = execSync(`node "${tmpFile}"`, {
      cwd: SKILL_DIR,
      stdio: 'inherit',
      env: { ...process.env, NODE_PATH: path.join(SKILL_DIR, 'node_modules') },
      timeout: 120000, // 2 minute timeout
    });
  } finally {
    // Clean up temp file
    try { fs.unlinkSync(tmpFile); } catch(e) {}
  }
}

async function runSelfTest() {
  console.log('Running self-test...');

  // Test 1: Playwright loads
  console.log('  [1/3] Playwright import... OK');

  // Test 2: Can launch browser
  const browser = await chromium.launch({ headless: true });
  console.log('  [2/3] Browser launch... OK');

  // Test 3: Can load a page
  const page = await browser.newPage();
  await page.goto('https://example.com');
  const title = await page.title();
  await browser.close();
  console.log(`  [3/3] Page load (title: "${title}")... OK`);

  console.log('All tests passed!');
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
