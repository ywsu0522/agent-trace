/* Headless checks of offline, generic run reports. No personal browser state. */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('url');
const {chromium} = require(path.join(process.argv[2], 'playwright'));
const root = path.resolve(__dirname, '..');
const qa = path.join(root, 'validation/tracing/ui');
fs.mkdirSync(qa, {recursive: true});
const study = path.join(root, 'studies/d06/record');
const baseline = path.join(root, 'studies/baseline-20/record');
const checks = [];
const ok = name => checks.push({name, passed: true});

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage({viewport: {width: 1360, height: 980}});
  const errors = [], requests = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => {if (/^https?:/.test(request.url())) requests.push(request.url());});
  try {
    await page.goto(pathToFileURL(path.join(study, 'index.html')).href);
    assert.equal(await page.locator('tbody tr').count(), 17);
    await page.getByRole('link', {name: '詳細研究比較與環境 diff'}).waitFor();
    await page.screenshot({path: path.join(qa, 'd06-compact.png'), fullPage: true});
    ok('d06 compact landing lists all 17 records and keeps a separate research link');

    await page.goto(pathToFileURL(path.join(baseline, 'index.html')).href);
    assert.equal(await page.locator('tbody tr').count(), 20);
    await page.getByRole('link', {name: 'd09', exact: true}).click();
    assert.equal(await page.locator('tbody tr').count(), 5);
    assert.equal(await page.locator('details[open]').count(), 0);
    assert.match(await page.locator('tbody').innerText(), /接續前一次視窗/);
    await page.screenshot({path: path.join(qa, 'd09-desktop.png'), fullPage: true});
    ok('20-case overview opens a five-turn d09 with full evidence initially collapsed');

    const trace = JSON.parse(fs.readFileSync(path.join(baseline, 'd09/trace.json'), 'utf8'));
    const turn = page.locator('#turn-4');
    await turn.locator('details.turn-evidence > summary').click();
    await turn.locator('details.request > summary').click();
    const displayed = await turn.locator('.message-content').allTextContents();
    assert.deepEqual(displayed, trace.turns[3].messages.map(m => m.content));
    await turn.getByText('完整 completion', {exact: true}).click();
    assert.equal(await turn.locator('.completion').textContent(), trace.turns[3].completion);
    const tool = turn.locator('details').filter({has: page.locator('summary', {hasText: 'read_doc · ok · 完整工具結果'})}).last();
    await tool.locator(':scope > summary').click();
    assert.equal(await turn.locator('.tool-content').textContent(), trace.turns[3].tools[0].content);
    ok('Expanded request, completion and document result exactly match saved evidence');

    await page.goto(pathToFileURL(path.join(baseline, 'd01/trace.html')).href);
    assert.match(await page.locator('.meta').innerText(), /3 主 requests \/ 4 aux/);
    assert.equal(await page.locator('#turn-1 .aux-completion').count(), 4);
    ok('Four auxiliary requests stay under the first main turn');

    await page.goto(pathToFileURL(path.join(baseline, 'd07/trace.html')).href);
    assert.match(await page.locator('tbody').innerText(), /重複讀取相同文件視窗/);
    assert.match(await page.locator('body').innerText(), /6790.*6000/);
    ok('Repeated windows and document-budget warning are visible');

    await page.goto(pathToFileURL(path.join(baseline, 'd17/trace.html')).href);
    assert.match(await page.locator('.meta').innerText(), /malformed/);
    assert.equal(await page.locator('tbody tr').count(), 3);
    assert.match(await page.locator('tbody').innerText(), /工具格式解析失敗/);
    ok('Malformed tool intent is displayed separately from execution');

    await page.setViewportSize({width: 390, height: 844});
    await page.goto(pathToFileURL(path.join(baseline, 'd09/trace.html')).href);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#turn-1 .turn-evidence > summary').click();
    await page.locator('#turn-1 .request > summary').click();
    await page.locator('#turn-1 .request details > summary').first().click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(qa, 'd09-mobile.png'), fullPage: true});
    ok('390px mobile layout has no page overflow, including expanded long messages');

    const hostile = path.join(root, 'validation/tracing/hostile/trace.html');
    if (fs.existsSync(hostile)) {
      await page.goto(pathToFileURL(hostile).href);
      assert.equal(await page.locator('script,img,iframe').count(), 0);
      assert.equal(await page.evaluate(() => globalThis.pwned), undefined);
      ok('Hostile retrieved HTML is inert text');
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    ok('Offline reports have no JavaScript errors or external network requests');
    fs.writeFileSync(path.join(qa, 'checks.json'), JSON.stringify({checks, errors, requests}, null, 2) + '\n');
    process.stdout.write(JSON.stringify({passed: checks.length, checks}, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => {process.stderr.write(String(error.stack) + '\n'); process.exitCode = 1;});
