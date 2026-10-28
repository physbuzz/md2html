// node tests/markdown_browser.cjs OUTPUT_DIRECTORY [MD2HTML_EXECUTABLE]
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium, firefox} = require('playwright');

const output = path.resolve(process.argv[2] || 'browser-artifacts/markdown');
const command = process.argv[3] || path.resolve(__dirname, '../.venv/bin/md2html');
fs.mkdirSync(output, {recursive: true});
const source = path.join(output, 'notes.md');
fs.writeFileSync(source, fs.readFileSync(path.resolve(__dirname, '../examples/markdown.md'), 'utf8') +
  '\nA special label[^100%] and a long note[^long].\n\n[^100%]: A percentage label.\n\n[^long]: ' +
  'A longer explanation that should fit within the viewport. '.repeat(120) + '\n');
const cases = [
  {name: 'standalone', flags: []},
  {name: 'shared', flags: ['--assets', 'shared']},
  {name: 'barebones', flags: ['--template', 'barebones.html']},
];
for (const fixture of cases) {
  const html = path.join(output, `${fixture.name}.html`);
  execFileSync(command, [source, '--math', 'raw', '-o', html, ...fixture.flags]);
  fixture.url = pathToFileURL(html).href;
}

(async () => {
  let checks = 0;
  for (const [engine, browserType] of [['chromium', chromium], ['firefox', firefox]]) {
    const browser = await browserType.launch();
    try {
      for (const fixture of cases) {
        for (const width of [1200, 390]) {
          const page = await browser.newPage({viewport: {width, height: 800}});
          const errors = [];
          page.on('pageerror', error => errors.push(error.message));
          await page.goto(fixture.url);
          const ref = page.locator('.footnote-ref').first();
          const tooltip = page.locator('.footnote-tooltip');
          await ref.hover();
          await tooltip.waitFor({state: 'visible'});
          assert.match(await tooltip.textContent(), /formatted text and inline code/);
          assert.match(await tooltip.textContent(), /second paragraph/);
          assert.doesNotMatch(await tooltip.textContent(), /↩/);
          assert.equal(await tooltip.getAttribute('href'), await ref.getAttribute('href'));
          await tooltip.hover();
          await page.waitForTimeout(250);
          assert.equal(await tooltip.isVisible(), true, 'preview stays open under the pointer');
          if (fixture.name === 'standalone') {
            await page.screenshot({path: path.join(output, `${engine}-${width}-light.png`)});
          }
          const href = await ref.getAttribute('href');
          await tooltip.click();
          await page.waitForFunction(hash => decodeURIComponent(location.hash) === hash, href);
          assert.equal(await tooltip.isVisible(), false);
          await page.locator('.footnote-backref').first().click();
          await page.mouse.move(0, 0);
          await ref.focus();
          await tooltip.waitFor({state: 'visible'});
          assert.equal(await ref.getAttribute('aria-describedby'), await tooltip.getAttribute('id'));
          await page.keyboard.press('Escape');
          assert.equal(await tooltip.isVisible(), false);
          await page.keyboard.press('Enter');
          await page.waitForFunction(hash => decodeURIComponent(location.hash) === hash, href);
          await page.locator('.footnote-ref').last().hover();
          await tooltip.waitFor({state: 'visible'});
          const bounds = await tooltip.boundingBox();
          assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1);
          assert.ok(bounds.y >= 0 && bounds.y + bounds.height <= 801);
          await page.mouse.move(0, 0);
          await page.locator('.footnote-ref').last().evaluate(node => node.blur());
          await tooltip.waitFor({state: 'hidden'});
          assert.equal(await page.locator('.markdown-alert').count(), 5);
          const colors = await page.locator('.markdown-alert-title').evaluateAll(nodes =>
            nodes.map(node => getComputedStyle(node).color));
          assert.equal(new Set(colors).size, 5);
          await page.emulateMedia({colorScheme: 'dark'});
          await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
          await ref.hover();
          await tooltip.waitFor({state: 'visible'});
          if (fixture.name === 'standalone') {
            await page.screenshot({path: path.join(output, `${engine}-${width}-dark.png`)});
          }
          const ids = await page.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id));
          assert.equal(new Set(ids).size, ids.length, 'previews must not duplicate footnote IDs');
          assert.deepEqual(errors, []);
          await page.close();
          checks++;
        }
      }
      const page = await browser.newPage({javaScriptEnabled: false});
      await page.goto(cases[0].url);
      await page.locator('.footnote-ref').first().click();
      assert.match(decodeURIComponent(page.url()), /#fn:detail$/);
      await page.close();
    } finally {
      await browser.close();
    }
  }
  console.log(`${checks} Markdown browser cases passed, plus navigation without JavaScript`);
})().catch(error => {console.error(error); process.exit(1);});
