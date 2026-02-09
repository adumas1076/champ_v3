// ============================================
// CHAMP V3 — Hands Full Test (5 Tests)
// Tests: Navigate, Screenshot, Scrape, Click, Form Fill
// Run: node test-hands.js
// ============================================

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

let passed = 0;
let failed = 0;

async function test(name, fn) {
    process.stdout.write(`\n  [TEST] ${name}... `);
    try {
        await fn();
        passed++;
        console.log('PASSED');
    } catch (err) {
        failed++;
        console.log(`FAILED: ${err.message}`);
    }
}

(async () => {
    console.log('='.repeat(55));
    console.log('CHAMP V3 — HANDS FULL TEST (5 Tests)');
    console.log('='.repeat(55));

    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    // ---- TEST 1: Navigate + Read Title ----
    await test('1/5 Navigate to Wikipedia and read title', async () => {
        await page.goto('https://en.wikipedia.org/wiki/Puppeteer', {
            waitUntil: 'networkidle2',
            timeout: 30000,
        });
        const title = await page.title();
        console.log(`\n    Title: "${title}"`);
        if (!title.includes('Puppeteer')) throw new Error('Title mismatch');
    });

    // ---- TEST 2: Screenshot ----
    await test('2/5 Take full page screenshot', async () => {
        const shotPath = path.join(__dirname, 'test-wikipedia.png');
        await page.screenshot({ path: shotPath, fullPage: false });
        const exists = fs.existsSync(shotPath);
        const size = fs.statSync(shotPath).size;
        console.log(`\n    File: ${shotPath} (${(size / 1024).toFixed(0)} KB)`);
        if (!exists || size < 1000) throw new Error('Screenshot too small or missing');
    });

    // ---- TEST 3: Scrape Text Content ----
    await test('3/5 Scrape first paragraph from page', async () => {
        const firstParagraph = await page.$eval(
            '#mw-content-text p:not(.mw-empty-elt)',
            el => el.textContent.trim()
        );
        const preview = firstParagraph.slice(0, 150);
        console.log(`\n    Content (first 150 chars): "${preview}..."`);
        if (firstParagraph.length < 20) throw new Error('Content too short');
    });

    // ---- TEST 4: Click a Link ----
    await test('4/5 Click a link and navigate', async () => {
        // Use Wikipedia — click first link in the article
        await page.goto('https://en.wikipedia.org/wiki/Puppeteer', { waitUntil: 'networkidle2' });
        const beforeUrl = page.url();

        // Click the first content link in the article body
        const link = await page.$('#mw-content-text p a[href^="/wiki/"]');
        if (!link) throw new Error('No wiki link found');

        await link.click();
        await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 15000 });

        const afterUrl = page.url();
        console.log(`\n    Before: ${beforeUrl}`);
        console.log(`    After:  ${afterUrl}`);
        if (beforeUrl === afterUrl) throw new Error('URL did not change after click');
    });

    // ---- TEST 5: Fill a Search Form ----
    await test('5/5 Fill search form on Wikipedia', async () => {
        await page.goto('https://en.wikipedia.org', { waitUntil: 'networkidle2' });

        // Type into search box
        const searchSelector = 'input[name="search"]';
        await page.waitForSelector(searchSelector);
        await page.click(searchSelector);
        await page.type(searchSelector, 'Artificial intelligence', { delay: 50 });

        // Read back what was typed
        const value = await page.$eval(searchSelector, el => el.value);
        console.log(`\n    Typed: "${value}"`);
        if (value !== 'Artificial intelligence') throw new Error('Input value mismatch');

        // Submit the form
        await page.keyboard.press('Enter');
        await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 });

        const resultTitle = await page.title();
        console.log(`    Result page: "${resultTitle}"`);
        if (!resultTitle.toLowerCase().includes('artificial intelligence')) {
            throw new Error('Did not navigate to AI article');
        }
    });

    await browser.close();

    // ---- SUMMARY ----
    console.log('\n' + '='.repeat(55));
    console.log(`HANDS TEST RESULTS: ${passed}/5 passed, ${failed}/5 failed`);

    if (failed === 0) {
        console.log('\nHANDS GATE: PASSED');
        console.log('Navigate, screenshot, scrape, click, form fill — all working.');
    } else {
        console.log('\nHANDS GATE: NEEDS WORK');
    }
    console.log('='.repeat(55));

    process.exit(failed > 0 ? 1 : 0);
})().catch(err => {
    console.error('\nFATAL:', err.message);
    process.exit(1);
});
