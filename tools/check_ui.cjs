/* Local UI verification. Usage: node scripts/check_research_ui.cjs NODE_MODULES */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('url');
const {chromium} = require(path.join(process.argv[2], 'playwright'));
const root = path.resolve(__dirname, '..');
const folder = path.join(root, 'studies/d06/record');
const qa = path.join(root, 'validation/ui');
fs.mkdirSync(qa, {recursive: true});
const corpus = JSON.parse(fs.readFileSync(path.join(folder, 'records.json'), 'utf8'));
const url = pathToFileURL(path.join(folder, 'research.html')).href;

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage({viewport: {width: 1360, height: 1000}});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const checks = [];
  const ok = name => checks.push({name, passed: true});
  await page.goto(url);
  await page.getByRole('heading', {name: 'd06：從 Prompt 修改追蹤 Agent 失敗路徑'}).waitFor();
  assert.equal(await page.locator('.phase').count(), 5);
  ok('Timeline contains all five research stages');
  await page.screenshot({path: path.join(qa, 'desktop-timeline.png'), fullPage: true});

  await page.getByRole('button', {name: '將摘要推成全文 → T2', exact: true}).click();
  await page.getByRole('heading', {name: 'Turn 2 · search_docs', exact: true}).waitFor();
  assert.equal(new URL(page.url()).hash.includes('turn=2'), true);
  await page.reload();
  await page.getByRole('heading', {name: 'Turn 2 · search_docs', exact: true}).waitFor();
  ok('Pinned turn link and reload preserve the requested turn');

  await page.getByRole('tab', {name: '完整 request', exact: true}).click();
  const displayed = await page.locator('#turn-evidence').evaluate(host =>
    [...host.children].filter(n => n.tagName === 'DETAILS' && n.firstElementChild.textContent.startsWith('Message '))
      .map(n => n.querySelector('pre').textContent));
  const expected = corpus.runs.find(r => r.id === 'paging-after').turns[1].messages.map(m => m.content);
  assert.deepEqual(displayed, expected);
  ok('All displayed message contents exactly match saved request messages');
  await page.getByRole('button', {name: '只看本輪新增', exact: true}).click();
  assert.equal(await page.locator('#turn-evidence').evaluate(host =>
    [...host.children].filter(n => n.tagName === 'DETAILS' && n.firstElementChild.textContent.startsWith('Message ')).length), 2);
  assert.match(await page.locator('#turn-evidence').innerText(), /目前隱藏 2 個/);
  await page.getByRole('button', {name: '全部 messages', exact: true}).click();
  ok('Reduced-history view explicitly identifies hidden but submitted messages');

  await page.getByRole('tab', {name: 'Tool calling', exact: true}).click();
  assert.match(await page.locator('#turn-evidence').innerText(), /回傳 5 筆結果/);
  await page.locator('#turn-evidence summary').filter({hasText: 'gridlens-api-spec'}).click();
  assert.match(await page.locator('#turn-evidence').innerText(), /Version: 2.1/);
  await page.screenshot({path: path.join(qa, 'desktop-turn.png'), fullPage: true});
  ok('Document result count, status and exact snippet can be inspected');

  await page.selectOption('#run-select', 'a-full');
  assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('run'), 'a-full');
  await page.getByRole('tab', {name: 'Aux (4)', exact: true}).click();
  assert.equal(await page.locator('#turn-evidence > details').count(), 4);
  await page.locator('#turn-evidence > details > summary').first().click();
  assert.match(await page.locator('#turn-evidence').innerText(), /Completion/);
  ok('Aux requests remain attached to main turn 1 and are fully expandable');

  await page.selectOption('#run-select', 'c-probe1');
  await page.getByRole('tab', {name: 'Tool calling', exact: true}).click();
  assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('view'), 'tools');
  assert.match(await page.locator('#turn-evidence').innerText(), /格式不合法，未執行工具/);
  await page.selectOption('#run-select', 'replay-old-old');
  await page.getByRole('tab', {name: 'Tool calling', exact: true}).click();
  assert.match(await page.locator('#turn-evidence').innerText(), /工具未執行/);
  ok('Malformed probes and valid but unexecuted replay calls are distinguished');

  await page.getByRole('tab', {name: '環境與差異', exact: true}).click();
  await page.selectOption('#env-before', 'E3');
  await page.selectOption('#env-after', 'E4');
  assert.equal(await page.locator('.diff-remove').count(), 1);
  assert.equal(await page.locator('.diff-add').count(), 1);
  assert.match(await page.locator('.diff-add').innerText(), /end_line < total_lines/);
  assert.match(await page.locator('#env-comparison').innerText(), /行相同內容未展開/);
  await page.getByRole('button', {name: '顯示完整上下文', exact: true}).click();
  assert.doesNotMatch(await page.locator('#env-comparison > pre').innerText(), /行相同內容未展開/);
  await page.getByRole('button', {name: '只看變更附近', exact: true}).click();
  ok('Condensed diff can expand to complete unmodified context');
  await page.screenshot({path: path.join(qa, 'desktop-diff.png'), fullPage: true});
  ok('E3 to E4 comparison shows exactly one removed and one added line');

  await page.setViewportSize({width: 390, height: 844});
  await page.getByRole('tab', {name: '實驗時間線', exact: true}).click();
  await page.screenshot({path: path.join(qa, 'mobile-timeline.png'), fullPage: true});
  for (const tab of ['實驗時間線', '逐 turn 瀏覽', '環境與差異', '名詞與證據界線']) {
    await page.getByRole('tab', {name: tab, exact: true}).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, tab+' horizontal overflow');
  }
  ok('All four pages fit a 390px viewport without document horizontal overflow');
  await page.getByRole('tab', {name: '逐 turn 瀏覽', exact: true}).click();
  await page.selectOption('#stage-filter', 'paging');
  assert.equal(await page.locator('#run-select option').count(), 1);
  await page.getByRole('tab', {name: '完整 request', exact: true}).click();
  await page.screenshot({path: path.join(qa, 'mobile-request.png'), fullPage: true});
  ok('Stage filtering and mobile request inspection work');
  assert.deepEqual(errors, []);
  ok('No JavaScript page errors');
  fs.writeFileSync(path.join(qa, 'browser-checks.json'), JSON.stringify({browser: 'Microsoft Edge / Playwright', viewports: [1360, 390], checks, page_errors: errors}, null, 2));
  await browser.close();
  console.log(JSON.stringify({passed: checks.length, screenshot_folder: qa}, null, 2));
})().catch(e => {console.error(e); process.exit(1);});
