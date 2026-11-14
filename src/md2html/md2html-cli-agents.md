# md2html for agents

AI agent guide to md2html.

`md2html` turns Markdown notes into standalone HTML pages, a small static site, or Markdown for Jekyll to render. It's aimed at quick math notes. 

## Single page standalone report

By default, 

```bash
md2html report.md
```

will render to a standalone `report.html` file, with static CHTML math and math fonts embedded. It can be configured to 
other rendering methods, but chtml gives the best results.

The default template and style has a light mode and dark mode, a javascript reader widget (javascript optional), and all
appropriate styling choices made for showing the filename, handling mobile and overflow, and so on. It is greatly preferred
if you just write in regular markdown without html style tags.

md2html can be configured solely with command line arguments. It also looks towards a file `md2html.json` by 
default to accept settings from. You probably don't need or want to mess with an md2html.json for a single page.

md2html also has serve and watch functionality, serve implies watch, so `-s` or `--serve` is ok.

## Why the defaults are the answer

The option list is long because md2html also builds blogs, Jekyll sites, and pages for people who maintain their own templates. 
Those options serve those projects. For a report, the default page is the product: its template, colours, typography, and math 
rendering were designed and tested together, and the people who read md2html pages expect each one to look and behave the same way. 
Your contribution to how the report looks is its content and structure. In most cases, the styling is already done.

Three parts of the default page are easy to break without noticing, because the damage shows up only in a browser state you are probably not looking at:

- **Reader controls.** The "Aa" menu in the page header lets the reader choose a light, dark, or system theme, the text width, a serif or sans typeface, and the text size, and remembers the choice across pages. It lives in the default template and works through CSS variables in the default stylesheet. A different template or replacement CSS removes the menu or leaves it with controls that do nothing.
- **Light and dark themes.** Every colour on the page is defined once per theme. A colour you hard-code, whether in a stylesheet, a `style` attribute, or raw HTML, exists in one theme only, and in the other it usually ends up as dark text on a dark background or light on light.
- **Math.** The default backend typesets math at build time and embeds the fonts. The page needs no JavaScript and no network connection, and the math follows the reader's text colour and size like the surrounding prose. The other `--math` backends each give up one of these properties in exchange for something a report does not need. `--math svg` in particular is finicky: each formula becomes an image whose size and baseline have to be matched to the surrounding text, and any CSS that touches `svg` elements throws that off.

## What Markdown gives you

A report earns its polish from structure, and md2html renders all of these in the default theme:

- A `title:` in YAML front matter sets the browser tab title. The page header shows the source filename, so give the file a meaningful name.
- `@toc` on its own line inserts a table of contents built from the headings.
- `> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, and `[!CAUTION]` blockquotes render as coloured callouts.
- Tables, footnotes (`[^1]`), task lists, and fenced code blocks with syntax highlighting all work.
- `$...$` is inline math and `$$...$$` is display math; `align`, `gather`, and `equation` environments work as written.
- `@src(file.py)` shows a source file with highlighting, and `collapsed` folds it away for long listings.
- source execution, `@src(file.py)` with the `-e` or `--execute` flag the file will be ran and its standard output displayed at the bottom.
This also has custom source block styling, so it takes care to design a template that takes that into account.

## Figures

Save each figure as a file and reference it: `![Caption](fig.svg)`, or `![[fig.png|width=70%|alt=Caption]]` to set a width. The build embeds the file in the page.

An embedded figure looks the same in both themes, so make it legible on its own: give plots an opaque background.

## Multi-page reports and websites

For multi-page reports, it may be appropriate to read more details in the readme and help commands. Generically, simple commands like:

```bash
md2html -ers src -o html
```
are preferred and are totally capable. This will recursively build and watch the directory `src`, 
running any embedded scripts inside src (or compiling/running C++), and serve from the html directory.
Such a command can also load details automatically from md2html.json, which for example could specify
the template directory to use.


