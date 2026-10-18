# md2html

`md2html` turns Markdown notes into standalone HTML pages, a small static site, or Markdown for Jekyll to render. It's aimed at quick math notes, so on my personal computer I can do `md2html notes.md && upload notes.html` and have a shareable link to a beautiful standalone webpage ready. By default this is an offline standalone page with static CommonHTML and the relevant math fonts embedded, but you can configure it however. While I'm writing textbook notes, I'll have `md2html -erf sicp -o html --serve` running in the background, so I can watch the page update as I code and take notes.

It is heavily Jekyll inspired, so if you want to try rendering a Jekyll site you can with `--jekyll`. If you want to parse the little widgets and features and output Markdown to later be rendered by Jekyll, use `--jekyll-markdown`.

The reason for making Yet Another Static Website Generator is to add some creature comforts and the ability to execute code snippets if the `--execute` flag is enabled. This makes it manifestly unsafe but very useful for writing articles, notes, or solving textbook problems. Source code snippets are done through  `@src(file.cpp, collapsed)`  or `@src-begin(cpp, execute) ... @src-end`. Other directives include `@include(markdown.md)`, `@toc` for table of contents, and the Obsidian-style `![[foo.png]]` image embeds.

```bash
md2html -h                             # print all CLI options
md2html --readme                       # print this README
md2html --example-config -             # print starter JSON to stdout
md2html --example-config md2html.json  # save starter JSON as a file
md2html --example-template -  # print the default page template to stdout
md2html --example-css -       # print editable default CSS to stdout
```
## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" # install the checkout and test dependencies
make install # build and copy it to ~/.local/bin/md2html
```
Renderer dependencies:
- **Pygments syntax highlighting** (default): installed with md2html, including `pygments-mathematica` for Wolfram Language syntax and built-in symbols. Highlighting does not require Mathematica, Ruby, or Rouge.
- **Rouge syntax highlighting** (optional, `--highlighter rouge`): install Ruby, then `gem install --user-install rouge`.
- **MathJax**: `make install` bundles its npm packages, so the installed command works from any directory. The default static CommonHTML backend requires Node.js at build time. The browser MathJax backend renders TeX when the page is opened. For a Python-package installation, run `npm install mathjax@4.1.3 @mathjax/mathjax-tex-font@4.1.3 @mathjax/mathjax-newcm-font@4.1.3` in the notes project or a parent directory.

SVG, MathML, raw LaTeX, and CDN browser MathJax do not need the npm MathJax
packages. SVG and MathML use Python dependencies installed with md2html.
## CLI
Examples:

```bash
# Turn test.md into test.html, with the default template and inlined CSS.
md2html test.md
md2html test.md -o index.html
# Use the bundled barebones template.
md2html --template barebones.html test.md -o test-barebones.html
md2html --css styles/base.css test.md # set custom css
# Render all markdown files and copy all assets from src to html
md2html -r src -o html
md2html -erfF src -o html --serve # force rebuild & execute all code snippets
md2html --config md2html.json # set the configuration file
# use rendered svg images instead of chtml or mathjax or mathml:
md2html --math svg test.md -o test-svg.html
```

All options:

- `-o, --output PATH`: output file or directory. JSON: `"output"`.
- `-v, --verbose`: report additional diagnostics, including unavailable cached output for snippets explicitly marked `execute`.
- `-e, --execute`: run executable examples and show their program output below the source. JSON: `"execute": true`.
- `-r, --recursive`: include nested documents in `pages` mode. Site, Jekyll, and Jekyll Markdown modes are recursive by default. JSON: `"recursive": true`.
- `-f, --force`: render every page at startup and on watch-triggered builds, even when its inputs are unchanged. This flag does not rerun cached snippets. JSON: `"force": true`.
- `-F, --force-execution`: rerun executable examples even when their program output is already cached. Requires `--execute`; `-eF` reruns everything. JSON: `"force_execution": true`.
- `-s, --serve`: build, rebuild on change, and serve the generated pages. The default bind address is `127.0.0.1`.
- `-w, --watch`: rebuild on change without starting a server.
- `-p, --port N`: preview server port. The default is 8000.
- `--host ADDRESS`: preview server bind address. Use `--serve --host 0.0.0.0 --port 8000` for Docker previews. JSON: `"host"`.
- `--config PATH`: select a JSON configuration file explicitly.
- `--output-mode MODE`: `pages`, `site`, `jekyll`, or `jekyll-markdown`. You can also pass `--jekyll` and `--jekyll-markdown` directly. JSON: `"output_mode"`.
- `--templates DIR`: template search directory; repeat to add more. JSON: `"templates"`.
- `--template NAME`: standalone page template. The default is `page.html`. JSON: `"template"`.
- `--css FILE`: replace the template's base CSS; repeat to combine files. JSON: `"css"` (a path or list; `[]` means no base CSS).
- `--stylesheet HREF`: add a stylesheet link; repeat for more. JSON: `"stylesheets"`.
- `--assets MODE`: `shared`, `standalone`, or `cdn` renderer-asset placement. `--standalone` is an alias for `--assets standalone`. `pages` mode defaults to `standalone`, including multiple inputs and directories. Website modes default to `shared`; `--standalone` in a website build also uses shared local assets for an offline site. JSON: `"assets"`.
- `--no-css`: omit base and feature CSS. JSON: `"css": []` plus `"feature_css": false`.
- `--no-feature-css`: omit generated CSS for code, math, tables of contents, images, and warnings. JSON: `"feature_css": false`.
- `--no-minify-css`: leave generated CSS readable. JSON: `"minify_css": false`.
- `--no-liquid`: leave Liquid unchanged in source documents; templates and layouts still render. JSON: `"parse_liquid": false`.
- `--highlighter NAME`: `pygments` (default) or `rouge`. JSON: `"highlighter"`.
- `--highlighter-style NAME`, `--highlighter-dark-style NAME`: light and dark token styles from the active highlighter. Pygments defaults to `default` and `github-dark`; Rouge to `github.light` and `github.dark`. JSON: `"highlighter_style"`, `"highlighter_dark_style"`.
- `--math BACKEND`: `mathjax`, `mathjax-chtml` (default), `svg`, `mathml`, or `raw`. JSON: `"math": {"backend": ...}`.
- `--math-fonts MODE`: CommonHTML font placement: `auto`, `local`, `remote`, `all`, `inline`, or `none`. JSON: `"math": {"chtml_fonts": ...}`.
- `--timeout SECONDS`: time limit for each executed example. The default is 120. JSON: `"timeout"`.
- `--clean`: remove the output directory before building in `site` or `jekyll` mode. It does not apply to independent page builds. JSON: `"clean": true`.
- `--version`, `--help`.

The default Pygments palettes give Wolfram Language blocks black built-ins in light mode, light built-ins in dark mode, blue user symbols, and green patterns and local variables. The light palette derives from `pygments-mathematica`; both Wolfram palettes are defined in `src/md2html/highlight_styles.py`. Other languages keep their usual palette. The style options select a palette for all code blocks; they do not select a programming language.

Command-line settings override JSON settings. A running watch or serve command
keeps its configuration fixed; restart it after changing configuration. Builds
skip current pages using dependency records in the output's `.md2html-cache/build.json`.
These records contain paths, timestamps, and signatures, not partially rendered pages;
removing them causes a full rebuild. Includes, source snippets, styles, and execution
outputs are tracked, along with Liquid references to site collections. Adding,
editing, moving, or deleting posts updates dependent listings and pagination.
Static files are copied independently, even when no page references them.
Hidden/underscore paths, `md2html.json`, Gemfiles, `node_modules`, `vendor`,
and virtual environments are excluded by default. Jekyll `include` can opt
specific paths back in; explicit `exclude` rules still win.
Generated pages that disappear from the build plan are removed only if their
recorded timestamps still match; manually added output files are preserved.
Unused renderer assets and execution workspaces are retained until removed.
Use `--force` after changes outside the tracked inputs, such as a renderer dependency
upgrade or a time-dependent template. Compiler header dependencies still require
`--force-execution`. Successful program outputs remain usable without execution.
A single-file `--serve` command without `-o` uses `.md2html-preview/`.

Output rules: one Markdown file with no `-o` writes the page beside the source; several inputs with `-o public` keep their relative paths below `public`. Standalone pages embed local media, stylesheets, and files linked by `@src`; shared builds copy referenced files so their links still work. Set `"images": {"embed": false}` to keep media external in standalone pages. Remote URLs remain external. HTML/HTM/XML inputs get Liquid only — no Markdown, no directives — and keep their suffixes. Give HTML/HTM/XML inputs and single-file Jekyll Markdown exports a distinct `-o` destination.

## Configuration
With no arguments, `md2html` searches for `md2html.json` in the current directory and its parents. Use `--config` to select another file. Paths inside it are resolved relative to that file's directory.

A minimal site configuration:

```json
{
  "input": ".",
  "output": "html",
  "output_mode": "pages",
  "execute": true,
  "assets": "shared",
  "math": { "backend": "mathjax-chtml" }
}
```

`md2html --example-config -` prints a fuller starter to stdout. Example writers require `--force` to overwrite an existing file.

|Key|Meaning|
|---|---|
|`input`|Markdown file or source directory.|
|`exclude`|Skip matching source paths. Exact paths, directory prefixes, and patterns are accepted.|
|`frontmatter`|Default front matter for Jekyll Markdown output. Source front matter wins.|
|`paginate`|Site variable giving the visible posts per paginated index page (`index.html` or `index.md`, including nested indexes).|
|`paginate_path`|Site variable giving the later-page URL; must contain `:num`. Default `/page:num/`.|
|`images.embed`|Embed local media in standalone pages (default `true`); website assets stay shared.|
|`images.class`|Default class names for Obsidian images. Per-image classes are appended.|
|`images.width`|Default Obsidian image width. A per-image width wins.|
|`commands`|Add or replace execution commands by language name or extension.|
|`site`|Site variables for templates (`title`, `url`, `baseurl`, `permalink`, ...).|
## Writing Pages

Markdown is rendered with Mistune and python-liquid. YAML frontmatter is optional, but useful keys are `title`, `template`, `css`, `stylesheets`, `layout`, `permalink`, `date`, and `tags`. You'll probably want to use things like `{{ page.title }}` in your templates, and use the frontmatter `render_with_liquid: false` or the command line `--no-liquid` to turn this off.

`@` directives go on their own lines and may have a trailing `#` annotation. They are expanded as preprocessing, including inside Markdown fences and included documents. Source-block bodies are preserved as code: `#include`, comments, and other source text are passed intact to the compiler or interpreter.
```markdown
@toc # Table of contents
@include(_partials/header.md)
@src(code/ex2-77.rkt, collapsed, noexecute) # Source file not meant to be run
![[img/fig.svg|width=70%|alt=A figure|class=centered]]

@src-begin(cpp, execute) # runs under --execute
#include <iostream>
int main() { std::cout << "Hello, world!\n"; }
@src-end
```

`@src` and `@src-begin` accept `collapsible`, `expanded`, `collapsed`, and `noexecute`. Bad TeX, missing includes, and failed runs warn and otherwise leave the page buildable; invalid front matter and mismatched `@src-begin`/`@src-end` markers stop the build. Missing layouts and layout cycles warn and leave the available content; conflicting outputs warn and skip the conflicting file. Invalid configuration and paths escaping the destination stop the build.

## Executable Snippets
The best and least safe part about md2html is its ability to execute snippets when the `-e` or `--execute` flag is enabled. There are defaults for python, shell, JavaScript, Racket, Wolfram Language, C, and C++, but you can add custom commands in `md2html.json`. eg:

```json
{
  "timeout": 30,
  "commands": {
    "julia": "julia {source}",
    "cpp": "g++ {source} -o {executable} && {executable} > {output}"
  }
}
```

Commands run through `sh` in the page's directory. For `@src(src.cpp)` in
`file.md`, `{source}` is `src.cpp`, `{slug}` is `src`, `{builddir}` is
`.md2html-cache/file/cpp-src-HASH`, `{executable}` is
`.md2html-cache/file/cpp-src-HASH/src.md2html-out`, and `{output}` is
`.md2html-cache/file/cpp-src-HASH/output.txt`.

`{python}` selects the current Python interpreter, or `python3`/`python` on
PATH for the packaged executable. `{filename}` aliases `{source}`, and
`{sourcedir}` is the source file's directory. Placeholder values are shell
quoted. Commands require a POSIX shell and the selected language's toolchain.
On timeout, the command and its descendants are stopped; incomplete runs are
not cached. Saved successful output can also be displayed without `--execute`;
`noexecute` suppresses both running and displaying cached output.

Note: some effort is taken to automatically invalidate the cache when the source code changes. However if you have `#include "header.h"` and change the header, this won't be detected, nor if you change a compilation command! In this case, force recompilation using the flag `-F`.

## Math
There are a few different math backends (choose with `--math`):
- `mathjax` leaves the TeX in the page and runs MathJax in the browser. With `cdn` it links the JavaScript and fonts from jsDelivr, so the HTML is small but needs a network connection when it is opened. With `shared`, md2html copies the JavaScript and fonts once to `assets/`; pages remain small and the complete site works offline.
- `mathjax-chtml` runs MathJax under Node while building and puts static CommonHTML in the page. The finished page runs no MathJax JavaScript. This is the default and my preference for offline pages. A standalone math-heavy page can be 500 KB or larger because its required fonts are embedded.
- `mathml` has the smallest standalone file size, but I wouldn't wish reading mathml on my worst enemies.
- `svg` is decent, but large file sizes for math heavy documents.

With the `--assets` flag we can decide where math assets (fonts, js) live.
- `standalone` is the default in `pages` mode and embeds local media and renderer assets in each page. With browser MathJax, `--math mathjax --assets standalone` warns and uses the CDN instead.
- `shared` writes them to `assets/` and is the default for multi-page sites.
- `cdn` links versioned jsDelivr URLs.

`--math-fonts` controls static CommonHTML font delivery. `auto` follows the
asset policy: embedded fonts for `standalone`, copied fonts for `shared`, and
CDN fonts for `cdn`. `inline`, `local`, and `remote` explicitly choose one of
those deliveries; `all` includes every font using the asset policy's delivery,
and `none` omits font-face declarations. Shared CommonHTML uses a common stylesheet and font set, with dynamic glyph rules in each page, so rendering a page never removes styles needed by another page. Only required fonts are preloaded.

The following measurements use `examples/notes.md` with execution enabled
(eight equations). Sizes are rounded KiB; CDN assets are not included in the
HTML size. This example has no authored figures.

|Renderer|Asset policy|HTML|Gzipped HTML|
|---|---|--:|--:|
|Browser MathJax|CDN|64 KiB|8 KiB|
|Static CommonHTML|standalone|320 KiB|191 KiB|
|Native MathML|standalone|68 KiB|9 KiB|
|Inline SVG|standalone|128 KiB|22 KiB|

## Liquid Processor

Markdown documents may use Liquid before Markdown rendering; HTML, HTM, and
XML use Liquid without Markdown or directives. Native `site` mode provides
pages, posts, layouts, includes, tags, pagination, and feeds. `--jekyll` reads
an existing `_config.yml` and layouts but skips plugins, themes, `_data`, and
Sass; `--jekyll-markdown` expands md2html directives and leaves the remaining
Markdown and Liquid for Jekyll. Markdown pages without a `layout` use the
selected page template in every HTML output mode. Static math backends also
render in `jekyll` mode; custom layouts supply the required styles and scripts
through the relevant `md2html` asset fields, as shown by `--example-template -`,
or equivalent author assets. Use `--math raw` (or `"math": {"backend": "raw"}`) to preserve TeX for your own browser renderer. CommonHTML builds warn when a custom layout does
not reference its generated math styles; author CSS may provide those rules.

Like Jekyll, dated posts live in `_posts/YYYY-MM-DD-title.md`. `--jekyll` defaults
to category-prefixed dated post URLs unless `permalink` specifies another pattern. Documents
elsewhere still build normally and are available through `site.pages`. Native site URLs can be configured with `"site": {"permalink": "/:year/:month/:day/:title.html"}`; both modes accept `:year`, `:month`, `:day`, `:title`, `:slug`, and `:categories`, plus per-page `permalink`. Posts marked `hidden: true` retain their pages but are omitted from pagination.
`site.posts`, `site.tags`, and `site.categories` index `_posts`; in native site
mode `site.pages` contains every discovered page, while `--jekyll` excludes
posts from `site.pages` as Jekyll does. Native pages do not require
frontmatter; `--jekyll` follows Jekyll and copies an ordinary frontmatter-free
document unchanged instead of rendering it as a page.

Templates and layouts search configured `templates` directories in order, then the
configuration root's `_templates`, the source root's `_includes` and `_layouts`,
and the bundled templates. Layout names may omit `.html`. Relative front-matter
CSS paths search the configuration/project root, the page directory, and then
those template directories. Configured CSS paths resolve beside the configuration
file; command-line CSS paths resolve from the working directory. Page `css` and
`stylesheets` append to the configured lists; page `feature_css` overrides the
global setting. Shared styles use descriptive files directly in `assets/`, such
as `base.css`, `code.css`, `highlight.css`, and `image.css`.

`site.title` defaults to the source directory's name, and posts receive an `id`
from their URL. The generated Atom feed contains the newest twenty posts,
uses `/feed.xml` for its identity and self-link, and dates itself from the newest
post. Configure `site.author` as a name or an object with `name`, `email`, and
`url` (or `uri`); otherwise the site title supplies the author name.

Common variables are:

|Variable|Useful values|
|---|---|
|`page`|Frontmatter plus `title`, `name`, `path`, `url`, `tags`, `categories`, and `excerpt`.|
|`site`|Configured values such as `title`, `url`, and `baseurl`, plus `time`, `pages`, `posts`, `tags`, `categories`, `tag_list`, and `category_list`.|
|`paginator`|`posts`, `page`, `total_pages`, `previous_page_path`, and `next_page_path` on a paginated index.|
|`content`|The rendered page body inside a template or layout.|
|`md2html`|Asset values and feature booleans such as `stylesheets`, `css`, `uses_mathjax_chtml`, `has_code`, and `has_toc`.|

For example:

```liquid
<title>{{ page.title }} · {{ site.title }}</title>
{% for post in site.posts %}
  <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
{% endfor %}
```

To list posts with a particular tag:

```liquid
{% assign math_posts = site.tags["math"] %}
{% for post in math_posts %}
  <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
{% endfor %}
```

Ordinary pages can use any frontmatter field. For example, give articles
`kind: article`, then select them with `where` and optionally test their tags:

```markdown
---
title: Gaussian Integral
kind: article
tags: [math, calculus]
---
```

```liquid
{% assign articles = site.pages | where: "kind", "article" %}
{% for article in articles %}
  {% if article.tags contains "math" %}
    <a href="{{ article.url | relative_url }}">{{ article.title }}</a>
  {% endif %}
{% endfor %}
```

Liquid's usual `if`, `unless`, `for`, `assign`, and `include` tags are
available, along with filters such as `default`, `date`, `where`, `sort`,
`map`, `join`, `escape`, `relative_url`, and `absolute_url`. Set
`render_with_liquid: false` in frontmatter or pass `--no-liquid` to leave
Liquid in the source document unchanged; templates and layouts still render.
