// node tests/highlight_browser.cjs OUTPUT_DIRECTORY [MD2HTML_EXECUTABLE]
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium, firefox} = require('playwright');

const output = path.resolve(process.argv[2] || 'browser-artifacts/highlight');
const command = process.argv[3] || path.resolve(__dirname, '../.venv/bin/md2html');
fs.mkdirSync(output, {recursive:true});
const source = path.join(output, 'mixed.md');
fs.writeFileSync(source, '```wl\n(* comment *)\nf[x_] := AbsoluteTiming[Module[{local}, local + x + 42]]; "text"\n```\n\n```cpp\n// comment\nint main() { return 0; }\n```\n');
const cases = [
  {name:'default', flags:[]},
  {name:'custom-light', flags:['--highlighter-style','monokai']},
  {name:'custom-dark', flags:['--highlighter-dark-style','monokai']},
];
for (const fixture of cases) {
  const html = path.join(output, `${fixture.name}.html`);
  execFileSync(command, [source, '--math','raw','-o',html,...fixture.flags]);
  fixture.url = pathToFileURL(html).href;
}

(async () => {
  const results = [];
  for (const [engine, browserType] of [['chromium',chromium],['firefox',firefox]]) {
    const browser = await browserType.launch();
    for (const fixture of cases) {
      const page = await browser.newPage({viewport:{width:1100,height:900}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(fixture.url);
      await page.evaluate(() => document.fonts.ready);
      if (fixture.name === 'default') {
        await page.addStyleTag({content:'.codehilite[data-language="wl"] { background-color: rgb(42, 53, 64); }'});
      }
      for (const theme of ['light','dark']) {
        let baseline;
        for (const [os, explicit] of [[theme,false],[theme,true],[theme==='light'?'dark':'light',true]]) {
          await page.emulateMedia({colorScheme:os});
          await page.evaluate(({theme,explicit}) => {
            if (explicit) document.documentElement.dataset.theme = theme;
            else document.documentElement.removeAttribute('data-theme');
          }, {theme,explicit});
          const state = await page.evaluate(() => {
            const color = selector => {
              const element = document.querySelector(selector);
              return element && getComputedStyle(element).color;
            };
            const block = document.querySelector('[data-language="wl"]');
            return {
              background:getComputedStyle(block).backgroundColor,
              builtin:color('[data-language="wl"] .nb'),
              variable:color('[data-language="wl"] .nv'),
              punctuation:color('[data-language="wl"] .p'),
              tokens:[...document.querySelectorAll('.codehilite span')].map(element => {
                const style = getComputedStyle(element);
                return [element.textContent,style.color,style.fontWeight,style.fontStyle];
              }),
              errors:document.querySelectorAll('.codehilite .err').length,
            };
          });
          assert.equal(state.errors, 0);
          if (fixture.name === 'default') assert.equal(state.background, 'rgb(42, 53, 64)');
          if (!baseline) baseline = state;
          else assert.deepEqual(state, baseline, `${engine}/${fixture.name}/${theme} changed with OS theme`);
          if (fixture.name === 'default') {
            assert.equal(state.builtin, theme==='light'?'rgb(0, 0, 0)':'rgb(230, 237, 243)');
            assert.equal(state.variable, theme==='light'?'rgb(75, 120, 177)':'rgb(121, 192, 255)');
            assert.equal(state.punctuation, theme==='light'?'rgb(85, 85, 85)':'rgb(201, 209, 217)');
          }
          results.push({engine,fixture:fixture.name,theme,os,explicit,...state});
        }
        if (engine === 'chromium' && fixture.name === 'default') {
          await page.locator('[data-language="wl"]').first().screenshot({path:path.join(output,`${theme}.png`)});
        }
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    await browser.close();
  }
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2)+'\n');
  console.log(`${results.length} highlighting checks passed`);
})().catch(error=>{console.error(error);process.exit(1);});
