import readline from 'node:readline';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

try {
  const require = createRequire(pathToFileURL(path.join(process.argv[2], 'package.json')));
  const MathJax = (await import(pathToFileURL(require.resolve('mathjax')).href)).default;
  await MathJax.init({
    loader: {load: ['input/tex', 'output/chtml', '[mathjax-tex]/chtml'],
             paths: {'mathjax-tex': '@mathjax/mathjax-tex-font'}},
    chtml: {fontURL: 'mathjax/woff2', linebreaks: {inline: false}, scale: 1.195}
  });
  const adaptor = MathJax.startup.adaptor;
  console.log(JSON.stringify({ready: true}));
  for await (const line of readline.createInterface({input: process.stdin})) {
    try {
      const {tex, display, stylesheet} = JSON.parse(line);
      if (stylesheet) {
        console.log(JSON.stringify({css: adaptor.outerHTML(MathJax.chtmlStylesheet())}));
        continue;
      }
      const node = MathJax.tex2chtml(tex, {display});
      // Preserve MathJax's incremental rule order without serializing CSS for every equation.
      MathJax.chtmlStylesheet();
      console.log(JSON.stringify({html: adaptor.outerHTML(node).replace(/\sdata-latex="[^"]*"/g, '')}));
    } catch (error) {
      console.log(JSON.stringify({error: String(error)}));
    }
  }
} catch (error) {
  console.log(JSON.stringify({error: String(error)}));
  process.exitCode = 1;
}
