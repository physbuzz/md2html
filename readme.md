> [!WARNING]  
> This was vibecoded. I used OAI's Astra and a few rewrites to keep the complexity minimal (5.6kloc -> 2k lines of python).

# md2html

`md2html` turns Markdown notes into standalone HTML pages, a small static site, or Markdown for Jekyll to render. It's aimed at quick math notes, so on my personal computer I can do `md2html notes.md && upload notes.html` and have a shareable link to a beautiful standalone webpage ready. By default this is an offline standalone page with static CommonHTML and the relevant math fonts embedded, but you can configure it however. While I'm writing textbook notes, I'll have `md2html -erf sicp -o html --serve` running in the background, so I can watch the page update as I code and take notes.

It is heavily Jekyll inspired, so if you want to try rendering a Jekyll site you can with `--jekyll`. If you want to parse the little widgets and features and output Markdown to later be rendered by Jekyll, use `--jekyll-markdown`.

The reason for making Yet Another Static Website Generator is to add some creature comforts and the ability to execute code snippets if the `--execute` flag is enabled. This makes it manifestly unsafe but very useful for writing articles, notes, or solving textbook problems. Source code snippets are done through `@src(file.cpp, collapsed)` or `@src-begin(cpp, execute) ... @src-end`. Other directives include `@include(markdown.md)`, `@toc` for table of contents, and the Obsidian-style `![[foo.png]]` image embeds.

```bash
md2html -h                             # print all CLI options
md2html --readme                       # print this README
md2html --example-config -             # print starter JSON to stdout
md2html --example-config md2html.json  # save starter JSON as a file
md2html --example-template -  # print the default page template to stdout
md2html --example-css -       # print editable default CSS to stdout
```

## Installation

Building from a checkout requires uv 0.13.1 and Node.js 22.23.3.

```bash
make install # build and copy it to ~/.local/bin/md2html

# System-wide installation to /usr/local/bin/md2html
make pyinstaller
sudo make install-global 
```

`make test` runs the full regression suite from source. After `make pyinstaller`,
`make test-packaged` checks bundled renderers, fonts, highlighting, templates,
execution, site generation, and watch/restart behavior outside the checkout.

Prebuilt releases support Linux x86-64 with glibc 2.35 or newer. Download the executable from [GitHub Releases](https://github.com/physbuzz/md2html/releases) and install it (replace `1.0.0` with the downloaded version):

```bash
install -Dm755 md2html-1.0.0-linux-x86_64 ~/.local/bin/md2html
md2html --update # or -U; update the packaged executable and exit
```

Renderer dependencies:

- **Pygments syntax highlighting** (default): installed with md2html, including `pygments-mathematica` for Wolfram Language.
- **Rouge syntax highlighting** (optional, `--highlighter rouge`): install Ruby, then `gem install --user-install rouge`.
- **MathJax**: `make install` bundles its npm packages. Static CommonHTML also requires Node.js. For a Python-package installation, run `npm install mathjax@4.1.3 @mathjax/mathjax-tex-font@4.1.3 @mathjax/mathjax-newcm-font@4.1.3` in your project directory or a parent folder.

## CLI

Examples:

```bash
# Turn test.md into test.html, with the default template and inlined CSS.
md2html test.md
md2html test.md -o index.html
md2html note1.md note2.md # creates note1.html and note2.html beside their sources
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

Configuration can be done via CLI or via a config file `md2html.json`. All CLI options and their JSON counterparts:

- `-o, --output PATH`: output file or directory. Without an output setting, pages are written beside their sources and site builds use `_site/`. JSON: `"output"`.
- `-v, --verbose`: report additional diagnostics.
- `-e, --execute`: run executable examples, cache their outputs, and display outputs in the webpage. JSON: `"execute": true`.
- `--no-execute`: disable snippet execution even when `md2html.json` enables it; cached outputs still render.
- `-r, --recursive`: include nested documents in `pages` mode. Site, Jekyll, and Jekyll Markdown modes are recursive by default. JSON: `"recursive": true`.
- `-f, --force`: rebuild pages that would otherwise be skipped. JSON: `"force": true`.
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
- `--assets MODE`: `shared`, `standalone`, or `cdn` asset placement (see Math below). JSON: `"assets"`.
- `--standalone`: Shortcut for `--assets standalone`.
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

CLI args override JSON settings.

## Configuration

`md2html` searches for `md2html.json` in the working directory. Use `--config` to select another file. For example, a minimal site configuration might look like:

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

For a more full example, run `md2html --example-config -` to print JSON to stdout.

Paths inside the config file are resolved relative to its directory. Restart your watch/serve command after changing configuration settings.

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

## Writing Websites

There are three pieces to html generation in md2html:
1. md2html custom directives, which start with `@` and are how you can include and compile/execute external code snippets
2. Liquid templating
3. Markdown rendering

### md2html Directives
These are most of the point of this whole project. `@` directives go on their own line and may carry a trailing `# comment`. The implemented custom directives are:


The `@include(file.md)` directive. This includes another markdown file in-place.

The `@toc` directive.  This creates an html table of contents built from the page's headings. Textbook exercises are listed succinctly in the TOC by treating `Exercises`, `Exercise` and `Solution` as special headings. This is done so that if you have 100 problem solutions on a page, you don't have to scroll past 100 newlines. For example:
```md
### Exercises
#### Exercise 3.1
Problem statement
##### Solution
Solution.
```

The `@src(file.cpp, options...)` directive. This shows a source file in a custom code fence, syntax highlights it, and may execute and display the output in a collapsible or non-collapsible code fence depending on the flags. Allowed flags are `collapsible`, `expanded`, `collapsed`, `noexecute`, and `execute`.

The `@src-begin(lang, options...)` directive allows you to include and execute a code snippet in the page, without referencing an external file. It accepts the same flags as `@src`.

Another feature treated as a custom directive is Obsidian-style image embeds, such as `![[fig.png|width=70%|alt=A figure|class=centered]]`. Defaults for `class` and `width` come from `images.class` and `images.width` in the config.

An example directive-heavy source file might look like the following:

```md
@toc
@include(_partials/header.md)
@src(code/ex2-77.rkt, collapsed, noexecute)   # shown, never run
![[img/fig.svg|width=70%|alt=A figure|class=centered]]

@src-begin(cpp, execute, collapsed)   # runs under --execute
#include <iostream>
int main() { std::cout << "Hello, world!\n"; }
@src-end
```

#### Code Execution

With `-e`/`--execute`, `@src` and `@src-begin` blocks are run and their stdout and stderr are shown together beneath the code, including when the program exits with an error. The `noexecute` flag suppresses execution and output. Commands are built in for Python, shell, JavaScript, Racket, Wolfram Language, C, and C++. Note that `md2html` is intended to be a tool for article writing or notetaking, it is **not** intended to be a fully featured build or dev environment.

For custom build commands, add or replace them under `commands` in `md2html.json`, keyed by language name or file extension:

```json
{
  "timeout": 30,
  "commands": {
    "julia": "julia {source}",
    "cpp": "g++ {source} -o {executable} && {executable} > {output}"
  }
}
```

Commands are run through `sh` with the page's directory as the working directory. The placeholders, shown for `@src(src.cpp)` in `file.md`:

|Placeholder|Value|
|---|---|
|`{source}` (alias `{filename}`)|`src.cpp`|
|`{sourcedir}`|the source file's directory|
|`{slug}`|`src`|
|`{builddir}`|`.md2html-cache/file/cpp-src-HASH`|
|`{executable}`|`{builddir}/src.md2html-out`|
|`{output}`|`{builddir}/output.txt`|
|`{python}`|the running interpreter, or `python3`/`python` from `PATH` for the packaged executable|

For inline `@src-begin` snippets, `{source}` is written inside `{builddir}` and `{sourcedir}` is that cache directory; the working directory is still the page's directory.

Caching:

- Completed runs, including nonzero exits, are cached under `.md2html-cache` beside the page and displayed on later builds even without `--execute`. Timeouts are not cached. `noexecute` suppresses both running and display.
- Incremental build indexes live at `.md2html-cache/build-*.json` in the input root, separately for each output directory. They are disposable and should not be committed or deployed.
- The cache is invalidated when the snippet's own source changes, but not when a `#include`d header or a `commands` entry changes. Use `-eF` to rerun everything.
- To deploy without the necessary build environments, commit the execution caches' `output.txt` and `.complete` files and build with `--no-execute`. Missing cached output is reported only with `--verbose`.

### Math

Another feature of `md2html` is the many options for how to build LaTeX typeset math into a page. Write `$...$` for inline and `$$...$$` for display math; `align`, `gather`, `multline`, and `equation` environments (and their starred forms) are recognized as-is. 

`--math` picks the math renderer backend:

|Backend|What you get|
|---|---|
|`mathjax-chtml` (default)|MathJax runs under Node at build time and the page contains static CommonHTML, with no MathJax JavaScript. A standalone math-heavy page can be 500 KB or more because its fonts are embedded.|
|`mathjax`|TeX stays in the page and MathJax runs in the browser.|
|`svg`|Inline SVG. Decent, but large for math-heavy pages.|
|`mathml`|Native MathML. Smallest standalone files, but I wouldn't wish reading it on my worst enemies.|
|`raw`|TeX is left untouched and no MathJax script is supplied, for your own renderer.|

`--assets` decides where renderer assets (fonts, JavaScript) and local media live:

- `standalone` (default in `pages` mode) tries to embed everything in each page to a single output file, including images. Browser MathJax isn't embedded, so `--math mathjax --assets standalone` uses the CDN instead.
- `shared` (default for multi-page sites) copies them once into `assets/`; pages stay small and the whole site works offline. Website builds given `--standalone` also use shared local assets.
- `cdn` links versioned jsDelivr URLs: small HTML, but the page needs a network connection when opened.

Inline syntax-highlighting CSS includes only the token styles needed by each rendered page, retaining light and dark themes. Shared highlighting stylesheets keep the complete palettes so cached pages remain styled correctly during partial rebuilds.

`--math-fonts` controls CommonHTML font delivery on its own: `auto` follows the asset policy (embedded, copied, or CDN fonts), `inline`, `local`, and `remote` force one of those, and `none` emits no `@font-face` rules so your own stylesheet can supply them.

Sizes for `examples/notes.md` (eight equations, no figures, execution enabled), in rounded KiB; CDN assets are not counted:

|Renderer|Asset policy|HTML|Gzipped HTML|
|---|---|--:|--:|
|Browser MathJax|CDN|64 KiB|8 KiB|
|Static CommonHTML|standalone|320 KiB|191 KiB|
|Native MathML|standalone|68 KiB|9 KiB|
|Inline SVG|standalone|128 KiB|22 KiB|

### Templates and Liquid

Markdown is run through python-liquid, then rendered with Python-Markdown. YAML frontmatter is optional; useful keys are `title`, `template`, `layout`, `css`, `stylesheets`, `feature_css`, `permalink`, `slug`, `date`, and `tags`. Set `render_with_liquid: false` in frontmatter or pass `--no-liquid` to leave Liquid in the source untouched; templates and layouts always render. HTML, HTM, and XML inputs get Liquid only, with no Markdown or directives.

Tables, strikethrough, task lists, and automatic URL links are supported.

### Templates, layouts, and CSS

- A Markdown page without a `layout` uses the page template (`--template`, default `page.html`). The bundled `page.html` includes reader controls for theme, width, typeface, and text size; `barebones.html` is a simpler starting point for your own. Custom layouts pull in styles and scripts through the `md2html` asset fields; see `md2html --example-template -`.
- Templates and layouts are looked up in configured `templates` directories in order, then `_templates` beside the config file, then `_includes` and `_layouts` in the source root, then the bundled templates. Layout names may omit `.html`.
- With no configured `css`, a template uses its adjacent `.css` file if present, otherwise the bundled base CSS. Page `css` and `stylesheets` append to the configured lists; page `feature_css` overrides the global setting.
- Configured CSS paths resolve beside the config file and command-line paths from the working directory; relative frontmatter paths search the project root, the page directory, then the template directories. Standalone pages expand local relative CSS `@import`s and embed resources referenced by `url(...)`, resolving them beside the stylesheet. Other asset modes leave these references as written; directory builds copy static files normally. Shared generated stylesheets go in `assets/`.

### Sites, posts, and Jekyll

Native `site` mode provides pages, posts, layouts, includes, tags, categories, pagination, and an Atom feed. `--jekyll` reads an existing `_config.yml` and layouts but skips plugins, themes, `_data`, and Sass. `--jekyll-markdown` expands md2html directives and leaves the remaining Markdown and Liquid for Jekyll to render; give it an explicit output, such as `md2html --jekyll-markdown note.md -o expanded.md`.

- Posts live in `_posts/YYYY-MM-DD-title.md`. The filename supplies the date and default slug; frontmatter `slug` overrides it. Native post URLs default to `/:year/:month/:day/:title.html`; `--jekyll` defaults to Jekyll's category-prefixed dated URLs. Set `site.permalink` to a pattern built from `:year`, `:month`, `:day`, `:title`, `:slug`, and `:categories`.
- A per-page `permalink` is a literal URL such as `/notes/integrals/`, not a pattern; a trailing slash writes `index.html` in that directory.
- `hidden: true` drops a post from pagination but keeps it in collections and feeds. In Jekyll mode, `published: false` excludes a document, and ordinary pages without frontmatter are copied unchanged; `_posts` files are still rendered. Native pages need no frontmatter.
- `site.posts`, `site.tags`, and `site.categories` index `_posts`. `site.pages` holds every discovered page in native mode; `--jekyll` leaves posts out of it, as Jekyll does.
- `site.title` defaults to the source directory's name. Posts get an `id` from their URL.
- Site builds write `/feed.xml` with the newest twenty posts unless an input already supplies that path. The feed uses `site.author`, either a name or an object with `name`, `email`, and `url` (or `uri`); without it, the feed uses the site title as the author.
- `paginate` and `paginate_path` in the config paginate one `index.html`/`index.md`: the closest index above `paginate_path`. For example, `/blog/page:num/` selects `blog/index.html` if present, otherwise the root index.

### Liquid variables

Use `{{ ... }}` to insert a value and `{% ... %}` for loops, conditions, and includes. Frontmatter fields belong to `page`; values under `"site"` in `md2html.json` belong to `site`. For example, `title: Gaussian Integral` in a page's frontmatter gives you `{{ page.title }}`.

|Variable|How to use it|
|---|---|
|`page`|The current page's frontmatter and generated metadata: `title`, `name`, `path`, `url`, `tags`, `categories`, and `excerpt`. Custom frontmatter fields work too.|
|`site`|Your site settings, plus collections to build listings from: `site.pages`, `site.posts`, and posts grouped by tag or category in `site.tags` and `site.categories`. `site.time` is the build time.|
|`paginator`|On the paginated index, loop over `paginator.posts` for this page's posts. `page` and `total_pages` give the page numbers; `previous_page_path` and `next_page_path` give navigation links, or are empty at the ends.|
|`content`|In a template or layout, `{{ content }}` inserts the rendered page body.|
|`md2html`|Generated assets for custom templates: `css` and `math_css` contain inline CSS; `page_stylesheets`, `math_stylesheets`, and `stylesheets` are lists of stylesheet URLs. Feature flags such as `has_code`, `has_toc`, and `uses_mathjax_chtml` let a template add optional elements. See `--example-template -` for their use.|

The usual `if`, `unless`, `for`, `assign`, and `include` tags are available, along with filters such as `default`, `date`, `where`, `sort`, `map`, `join`, and `escape`. Use `relative_url` for links within your site (it adds `site.baseurl`), or `absolute_url` to include `site.url` as well.

#### Examples

A title and a post list:

```liquid
<title>{{ page.title | escape }} · {{ site.title | escape }}</title>
{% for post in site.posts %}
  <a href="{{ post.url | relative_url | escape }}">{{ post.title | escape }}</a>
{% endfor %}
```

Posts with a particular tag:

```liquid
{% assign math_posts = site.tags["math"] %}
{% for post in math_posts %}
  <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
{% endfor %}
```

Ordinary pages can carry any frontmatter field. Give articles `kind: article`, then select them with `where` and test their tags:

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

## Inputs and outputs

What gets built:

- Markdown inputs are rendered; HTML, HTM, and XML inputs get Liquid only and keep their suffixes, so give them a distinct output destination. Directory builds also copy other files as static assets, whether or not a page references them. With `--output-mode pages` and no output destination, only Markdown files are built beside their sources; other files stay in place.
- Native directory builds skip dotfiles and dot-directories, underscore files and directories other than `_posts`, `md2html.json` at the input root, and any separate output directory. Generated files are ignored while watching. Jekyll mode applies [Jekyll's default exclusions](https://jekyllrb.com/docs/configuration/default/), and `include` in `_config.yml` can opt paths back in. Explicit `exclude` rules always win.

What travels with a page:

- Standalone pages embed local media, stylesheets, and files linked by `@src`; shared builds copy referenced files so their links keep working. Remote URLs are left as they are.
- Set `"images": {"embed": false}` to keep media external in standalone pages.
