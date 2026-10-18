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

Building from a checkout requires uv 0.13.1 and Node.js 22.23.3.

```bash
make install # build and copy it to ~/.local/bin/md2html

# System-wide installation: build as yourself, then copy as administrator.
make pyinstaller
sudo make install-global # copy the existing executable to /usr/local/bin/md2html
```

Add `~/.local/bin` to your `PATH` if needed.

Prebuilt releases support Linux x86-64 with glibc 2.35 or newer.
Download the executable from [GitHub Releases](https://github.com/physbuzz/md2html/releases)
and install it (replace `3.0.0` with the downloaded version):

```bash
install -Dm755 md2html-3.0.0-linux-x86_64 ~/.local/bin/md2html
md2html --update # or -U; update the packaged executable and exit
```

Renderer dependencies:
- **Pygments syntax highlighting** (default): installed with md2html, including `pygments-mathematica` for Wolfram Language.
- **Rouge syntax highlighting** (optional, `--highlighter rouge`): install Ruby, then `gem install --user-install rouge`.
- **MathJax**: `make install` bundles its npm packages. Static CommonHTML also requires Node.js. For a Python-package installation, run `npm install mathjax@4.1.3 @mathjax/mathjax-tex-font@4.1.3 @mathjax/mathjax-newcm-font@4.1.3` in the notes project or a parent directory.

SVG, MathML, raw LaTeX, and CDN browser MathJax do not need the npm MathJax
packages. SVG and MathML use Python dependencies installed with md2html.
## CLI
Examples:

```bash
# Turn test.md into test.html, with the default template and inlined CSS.
md2html test.md
md2html test.md -o index.html
md2html note1.md note2.md -o html # two standalone pages
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
- `--no-execute`: disable snippet execution even when `md2html.json` enables it; saved successful outputs still render.
- `-r, --recursive`: include nested documents in `pages` mode. Site, Jekyll, and Jekyll Markdown modes are recursive by default. JSON: `"recursive": true`.
- `-f, --force`: rebuild pages that would otherwise be skipped, without rerunning cached snippets. JSON: `"force": true`.
- `-F, --force-execution`: rerun executable examples even when their program output is already cached. Requires `--execute`; `-eF` reruns everything. JSON: `"force_execution": true`.
- `-s, --serve`: build, rebuild on change, and serve the generated pages. The default bind address is `127.0.0.1`.
- `-w, --watch`: rebuild on change without starting a server.
- `-p, --port N`: preview server port. The default is 8000.
- `--host ADDRESS`: preview server bind address (default `127.0.0.1`). JSON: `"host"`.
- `--config PATH`: select a JSON configuration file explicitly.
- `--output-mode MODE`: `pages`, `site`, `jekyll`, or `jekyll-markdown`. Defaults to `site` for directory inputs, otherwise `pages`. JSON: `"output_mode"`.
- `--jekyll`: Shortcut for `--output-mode jekyll`.
- `--jekyll-markdown`: Shortcut for `--output-mode jekyll-markdown`.
- `--template-dir DIR`: template search directory; repeat to add more, in lookup order. JSON: `"templates"`.
- `--template NAME`: standalone page template. The default is `page.html`. JSON: `"template"`.
- `--css FILE`: replace the template's base CSS; repeat to combine files. JSON: `"css"` (a path or list; `[]` means no base CSS).
- `--stylesheet FILE_OR_URL`: add an authored stylesheet alongside the base CSS; repeat for more. JSON: `"stylesheets"`.
- `--assets MODE`: `shared`, `standalone`, or `cdn` asset placement (see Math below). `--standalone` is a shortcut for `--assets standalone`. JSON: `"assets"`.
- `--no-default-css`: omit base and feature CSS; keep authored stylesheets and required math-renderer styles. JSON: `"css": []` plus `"feature_css": false`.
- `--no-feature-css`: omit generated CSS for code, math, tables of contents, images, and warnings. JSON: `"feature_css": false`.
- `--no-minify-css`: leave generated CSS readable. JSON: `"minify_css": false`.
- `--no-liquid`: leave Liquid unchanged in source documents; templates and layouts still render. JSON: `"parse_liquid": false`.
- `--highlighter NAME`: `pygments` (default) or `rouge`. JSON: `"highlighter"`.
- `--highlighter-style NAME`, `--highlighter-dark-style NAME`: light and dark token styles from the active highlighter. Pygments defaults to `default` and `github-dark`; Rouge to `github.light` and `github.dark`. JSON: `"highlighter_style"`, `"highlighter_dark_style"`.
- `--math BACKEND`: `mathjax`, `mathjax-chtml` (default), `svg`, `mathml`, or `raw`. JSON: `"math": {"backend": ...}`.
- `--math-fonts MODE`: CommonHTML font delivery: `auto`, `inline`, `local`, `remote`, or `none`. JSON: `"math": {"chtml_fonts": ...}`.
- `--timeout SECONDS`: time limit for each executed example. The default is 120. JSON: `"timeout"`.
- `--clean`: remove the output directory before building in `site` or `jekyll` mode. It does not apply to independent page builds. JSON: `"clean": true`.
- `--version`, `--help`.
- `-U, --update`: update a packaged Linux x86-64 executable from the latest stable release and exit; other build options are ignored.

Command-line settings override JSON settings. Restart watch/serve after changing
configuration. Builds skip unchanged pages, tracking includes, snippets, styles,
and site listings. Use `--force` for changes outside those dependencies, such as
time-dependent templates. A single-file `--serve` command without `-o` uses
`.md2html-preview/`.

Static files are copied even when no page references them.
Native builds exclude dotfiles/directories, underscore directories (except `_posts`),
and `md2html.json` at the input root. Jekyll mode applies
[Jekyll's default exclusions](https://jekyllrb.com/docs/configuration/default/).
Jekyll `include` can opt paths back in; explicit `exclude` rules still win.
The output directory is excluded from inputs and watching.

Output rules: one Markdown file with no `-o` writes the page beside the source; several inputs with `-o public` keep their relative paths below `public`. Standalone pages embed local media, stylesheets, and files linked by `@src`; shared builds copy referenced files so their links still work. Set `"images": {"embed": false}` to keep media external in standalone pages. Remote URLs remain external. HTML/HTM/XML inputs get Liquid only — no Markdown, no directives — and keep their suffixes. Give HTML/HTM/XML inputs and single-file Jekyll Markdown exports a distinct `-o` destination.
For directory or multiple-file inputs without a configured output, the destination
is `_site/` in site/Jekyll mode, `html/` in pages mode, or `markdown/` in Jekyll
Markdown mode, relative to the configuration directory or current directory.

## Configuration
`md2html` searches for `md2html.json` in the current directory and its parents. Use `--config` to select another file. Paths inside it are resolved relative to that file's directory. With no inputs, it builds the configuration directory or current directory. Execution is disabled by default.

A minimal site configuration:

```json
{
  "input": ".",
  "output": "html",
  "output_mode": "site",
  "execute": true,
  "assets": "shared",
  "math": { "backend": "mathjax-chtml" }
}
```

`md2html --example-config -` prints a fuller starter to stdout. Example writers require `--force` to overwrite an existing file.

|Key|Meaning|
|---|---|
|`input`|Markdown file, source directory, or a list of inputs.|
|`exclude`|Skip matching source paths. Exact paths, directory prefixes, and patterns are accepted.|
|`frontmatter`|Default front matter for Jekyll Markdown output. Source front matter wins.|
|`paginate`|Site variable giving the visible posts per paginated index page (`index.html` or `index.md`, including nested indexes).|
|`paginate_path`|Site variable giving the later-page URL; must contain `:num`. Default `/page:num/`. For `blog/index.html`, use a path below `/blog/`, such as `/blog/page:num/`.|
|`images.embed`|Embed local media in standalone pages (default `true`); website assets stay shared.|
|`images.class`|Default class names for Obsidian images. Per-image classes are appended.|
|`images.width`|Default Obsidian image width. A per-image width wins.|
|`commands`|Add or replace execution commands by language name or extension.|
|`site`|Site variables for templates (`title`, `url`, `baseurl`, `permalink`, ...).|
## Writing Pages

Markdown is rendered with Mistune and python-liquid. YAML frontmatter is optional, but useful keys are `title`, `template`, `css`, `stylesheets`, `layout`, `permalink`, `date`, and `tags`. You'll probably want to use things like `{{ page.title }}` in your templates, and use the frontmatter `render_with_liquid: false` or the command line `--no-liquid` to turn this off.

`@` directives go on their own lines and may have a trailing `#` annotation. They expand inside Markdown fences and included documents too.
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

`@src` and `@src-begin` accept `collapsible`, `expanded`, `collapsed`, and `noexecute`.

`@src` detects highlighting from the filename. `@include` and `@src`
resolve paths beside the document containing the directive, then at the project root.
`@toc` lists the headings, omitting `Solution`; `Exercise ...` headings form a compact list
under `Exercises`, or at the end of the TOC if there is no such heading.

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
`{sourcedir}` is the source file's directory.
For inline `@src-begin` snippets, `{source}` is generated inside `{builddir}` and
`{sourcedir}` is that cache directory; the working directory is still the page's directory.
Saved successful output can also be displayed without `--execute`;
`noexecute` suppresses both running and displaying cached output.

For deployment without execution, keep each snippet's `output.txt` and `.complete`
at their existing paths under `.md2html-cache` beside the source page, then build with
`--no-execute`. The directive's optional `execute` marker enables a missing-cache
warning under `--verbose`; it does not enable execution by itself.

Note: some effort is taken to automatically invalidate the cache when the source code changes. However if you have `#include "header.h"` and change the header, this won't be detected, nor if you change a compilation command! In this case, force recompilation using the flag `-F`.

## Math
There are a few different math backends (choose with `--math`):
- `mathjax` leaves the TeX in the page and runs MathJax in the browser. With `cdn` it links the JavaScript and fonts from jsDelivr, so the HTML is small but needs a network connection when it is opened. With `shared`, md2html copies the JavaScript and fonts once to `assets/`; pages remain small and the complete site works offline.
- `mathjax-chtml` runs MathJax under Node while building and puts static CommonHTML in the page. The finished page runs no MathJax JavaScript. This is the default and my preference for offline pages. A standalone math-heavy page can be 500 KB or larger because its required fonts are embedded.
- `mathml` has the smallest standalone file size, but I wouldn't wish reading mathml on my worst enemies.
- `svg` is decent, but large file sizes for math heavy documents.
- `raw` preserves TeX for a custom renderer and supplies no MathJax script.

Use `$...$` for inline math and `$$...$$` for display math; `align`, `gather`,
`multline`, and `equation` environments (including starred forms) are also recognized.
The bundled templates support copying static equations as their original TeX.

With the `--assets` flag we can decide where math assets (fonts, js) live.
- `standalone` is the default in `pages` mode and embeds local media and renderer assets in each page. With browser MathJax, `--math mathjax --assets standalone` warns and uses the CDN instead.
- `shared` writes them to `assets/` and is the default for multi-page sites. Website builds also use shared local assets when given `--standalone`.
- `cdn` links versioned jsDelivr URLs.

`--math-fonts` controls static CommonHTML font delivery. `auto` follows the
asset policy: embedded fonts for `standalone`, copied fonts for `shared`, and
CDN fonts for `cdn`. `inline`, `local`, and `remote` explicitly choose one of
those deliveries, and `none` omits font-face declarations so author styles can supply
them.

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
selected page template. Custom layouts include styles and scripts through the
`md2html` asset fields; see `--example-template -`. Use `--math raw` to preserve
TeX for your own browser renderer.

Like Jekyll, dated posts live in `_posts/YYYY-MM-DD-title.md`. `--jekyll` defaults
to category-prefixed dated post URLs unless `permalink` specifies another pattern. Documents
elsewhere still build normally and are available through `site.pages`. Native dated post URLs default to `/:year/:month/:day/:title.html`. Set `site.permalink` to choose a pattern using `:year`, `:month`, `:day`, `:title`, `:slug`, or `:categories`.
The dated filename supplies the default slug; frontmatter `slug` overrides it.
Per-page `permalink` is a literal URL, such as `/notes/integrals/`, rather than a
pattern; a trailing slash writes `index.html` in that directory. In Jekyll mode,
`published: false` excludes a document. `hidden: true` omits posts from pagination,
but leaves them in collections and feeds.
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
global setting. Shared styles go in `assets/`.
With no configured `css`, a page template uses its adjacent `.css` file if present,
otherwise bundled base CSS. Local CSS imports and relative resource URLs resolve
beside their stylesheet and follow the selected asset policy. The bundled page
template includes reader controls for theme, width, typeface, and text size;
`barebones.html` is a simpler starting point for custom templates.

`site.title` defaults to the source directory's name, and posts receive an `id`
from their URL. Site builds generate `/feed.xml` unless an input supplies that path.
The generated Atom feed contains the newest twenty posts.
Configure `site.author` as a name or an object with `name`, `email`, and
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
