// ============================================
// CHAMP V3 — Hands Smoke Test
// Tests: Puppeteer launch, stealth, navigate, screenshot
// Run: node smoke-test.js
// ============================================

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');

puppeteer.use(StealthPlugin());

(async () => {
    console.log('='.repeat(50));
    console.log('CHAMP V3 — HANDS SMOKE TEST');
    console.log('='.repeat(50));

    // Test 1: Launch browser
    console.log('\n[1/4] Launching Chrome (stealth mode)...');
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    console.log('  OK: Browser launched');

    // Test 2: Navigate to a page
    console.log('\n[2/4] Navigating to example.com...');
    const page = await browser.newPage();
    await page.goto('https://example.com', { waitUntil: 'networkidle2' });
    const title = await page.title();
    console.log(`  OK: Page title = "${title}"`);

    // Test 3: Check stealth (webdriver flag)
    console.log('\n[3/4] Checking stealth...');
    const webdriver = await page.evaluate(() => navigator.webdriver);
    console.log(`  navigator.webdriver = ${webdriver} (should be false or undefined)`);
    if (!webdriver) {
        console.log('  OK: Stealth plugin working');
    } else {
        console.log('  WARN: Stealth plugin may not be active');
    }

    // Test 4: Screenshot
    console.log('\n[4/4] Taking screenshot...');
    const screenshotPath = path.join(__dirname, 'test-screenshot.png');
    await page.screenshot({ path: screenshotPath });
    console.log(`  OK: Screenshot saved to ${screenshotPath}`);

    await browser.close();

    console.log('\n' + '='.repeat(50));
    console.log('HANDS SMOKE TEST: PASSED');
    console.log('Puppeteer + Stealth stack is operational.');
    console.log('='.repeat(50));
})().catch(err => {
    console.error('SMOKE TEST FAILED:', err.message);
    process.exit(1);
});
