// ============================================
// CHAMP V3 — Hands CLI Entry Point
// Puppeteer stealth browser automation
// Protocol: node index.js <command> '<json_args>'
// Output: single JSON line to stdout, logs to stderr
// ============================================

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { createCursor } = require('ghost-cursor');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

// ---- Helpers ----

function log(msg) {
    process.stderr.write(`[HANDS] ${msg}\n`);
}

function success(data) {
    console.log(JSON.stringify({ ok: true, ...data }));
}

function fail(message) {
    console.log(JSON.stringify({ ok: false, error: message }));
}

function randomDelay(min, max) {
    return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}

async function humanType(page, selector, text) {
    await page.click(selector);
    for (const char of text) {
        await page.keyboard.type(char, { delay: 50 + Math.random() * 100 });
    }
}

async function launchBrowser() {
    return puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
}

async function newPage(browser) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    return page;
}

// ---- Command Handlers ----

async function browse(args) {
    log(`browse: ${args.url}`);
    const browser = await launchBrowser();
    try {
        const page = await newPage(browser);
        await page.goto(args.url, { waitUntil: 'networkidle2', timeout: 30000 });

        const title = await page.title();
        const url = page.url();
        const text = await page.evaluate(() => {
            return document.body.innerText.slice(0, 5000);
        });

        log(`browse done: "${title}" (${text.length} chars)`);
        success({ title, url, text });
    } finally {
        await browser.close();
    }
}

async function screenshot(args) {
    log(`screenshot: ${args.url}`);
    const browser = await launchBrowser();
    try {
        const page = await newPage(browser);
        await page.goto(args.url, { waitUntil: 'networkidle2', timeout: 30000 });

        const screenshotsDir = path.join(__dirname, 'screenshots');
        if (!fs.existsSync(screenshotsDir)) fs.mkdirSync(screenshotsDir);

        const filename = `shot_${Date.now()}.png`;
        const filepath = path.join(screenshotsDir, filename);
        await page.screenshot({ path: filepath, fullPage: false });

        const title = await page.title();
        log(`screenshot saved: ${filepath}`);
        success({ title, path: filepath, filename });
    } finally {
        await browser.close();
    }
}

async function fillForm(args) {
    log(`fill_form: ${args.url} (${args.fields.length} fields)`);
    const browser = await launchBrowser();
    try {
        const page = await newPage(browser);
        const cursor = createCursor(page);
        await page.goto(args.url, { waitUntil: 'networkidle2', timeout: 30000 });

        const results = [];
        for (const field of args.fields) {
            await randomDelay(500, 1000);
            try {
                await cursor.move(field.selector);
                await cursor.click(field.selector);
            } catch (e) {
                // Fallback to direct click if ghost-cursor can't find element
                await page.click(field.selector);
            }
            await randomDelay(200, 400);
            await humanType(page, field.selector, field.value);
            results.push({ selector: field.selector, filled: true });
        }

        if (args.submit_selector) {
            await randomDelay(500, 1000);
            try {
                await cursor.click(args.submit_selector);
            } catch (e) {
                await page.click(args.submit_selector);
            }
            await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
        }

        const title = await page.title();
        const url = page.url();
        log(`fill_form done: ${results.length} fields filled`);
        success({ title, url, fields_filled: results });
    } finally {
        await browser.close();
    }
}

// ---- Main Dispatcher ----

(async () => {
    const command = process.argv[2];
    const argsJson = process.argv[3] || '{}';

    if (!command) {
        fail('No command provided. Usage: node index.js <browse|screenshot|fill_form> \'<json>\'');
        process.exit(1);
    }

    let args;
    try {
        args = JSON.parse(argsJson);
    } catch (e) {
        fail(`Invalid JSON args: ${e.message}`);
        process.exit(1);
    }

    const handlers = { browse, screenshot, fill_form: fillForm };
    if (!handlers[command]) {
        fail(`Unknown command: ${command}. Available: ${Object.keys(handlers).join(', ')}`);
        process.exit(1);
    }

    await handlers[command](args);
})().catch(err => {
    fail(err.message);
    process.exit(1);
});
