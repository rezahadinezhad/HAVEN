// Render original SVG artwork, not an application session or a fabricated UI.
import { chromium } from '../apps/web/node_modules/playwright-core/index.mjs';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(root, '.github/assets/haven-hero.svg'));
  await page.screenshot({ path: path.join(root, '.github/assets/haven-social.png') });
} finally { await browser.close(); }
