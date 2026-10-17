const {chromium, firefox} = require('playwright');
const fs = require('fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:8000/';
const output = process.argv[3] || 'browser-artifacts';
fs.mkdirSync(output, {recursive:true});
(async () => {
  const results = [];
  for (const [name, engine] of [['chromium',chromium],['firefox',firefox]]) {
    const browser = await engine.launch({headless:true});
    for (const width of [1200,390]) {
      for (const backend of ['mathjax-chtml','mathjax','svg','mathml']) {
        const page = await browser.newPage({viewport:{width,height:900}});
        const errors=[];
        page.on('pageerror', e=>errors.push(e.message));
        page.on('requestfailed', r=>errors.push(r.url()+': '+r.failure().errorText));
        page.on('response', r=>{if(r.status()>=400) errors.push(r.status()+' '+r.url());});
        await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
        await page.goto(base+backend+'.html');
        if (backend==='mathjax') { await page.waitForFunction(()=>window.MathJax?.startup?.promise); await page.evaluate(()=>window.MathJax.startup.promise); }
        await page.evaluate(()=>document.fonts.ready);
        await page.waitForTimeout(400);
        const metrics=await page.evaluate(()=>({
          overflow:document.documentElement.scrollWidth>innerWidth+1,
          math:document.querySelectorAll('.math').length,
          fonts:[...document.fonts].filter(f=>f.status==='loaded').length,
          equations:[...document.querySelectorAll('.math-rendered,mjx-container')].map(n=>({width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height})),
          inlineDisplay:[...document.querySelectorAll('.inline-math .math-rendered')].map(n=>getComputedStyle(n).display),
          output:document.querySelector('.code-output')?.textContent,
          warnings:[...document.querySelectorAll('.warning')].map(n=>n.textContent)
        }));
        await page.screenshot({path:path.join(output, `${name}-${backend}-${width}.png`), fullPage:true});
        results.push({browser:name,width,backend,errors,...metrics});
        assert.deepEqual(errors, [], `${name} ${backend} failed offline`);
        assert.equal(metrics.overflow, false, `${name} ${backend} overflows at ${width}`);
        assert.equal(metrics.math, 8);
        assert.equal(metrics.warnings.length, 0);
        assert.ok(metrics.output.includes('140'));
        assert.ok(metrics.inlineDisplay.every(display=>display==='inline'||display==='inline-block'));
        if (backend.startsWith('mathjax')) assert.ok(metrics.fonts > 0);
        await page.evaluate(()=>document.documentElement.dataset.theme='dark');
        await page.waitForTimeout(200);
        await page.screenshot({path:path.join(output, `${name}-${backend}-${width}-dark.png`), fullPage:true});
        await page.close();
      }
    }
    await browser.close();
  }
  fs.writeFileSync(path.join(output, 'browser-results.json'),JSON.stringify(results,null,2));
  console.log(JSON.stringify(results.map(({equations,...rest})=>rest),null,2));
})().catch(error=>{console.error(error);process.exit(1);});
