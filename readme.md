> Right now this is mostly a placeholder repo

A markdown -> html generator that ties together `markdown`, `pygments`, 
`python-liquid` and a few other things for static website and standalone
static page generation.

Use cases include:

1. Generating single webpages with default styling, suitable for notes on 
math and programming. So, syntax highlighting and LaTeX -> MathML or KaTeX by 
default.
2. Including an additional `@include` directive for recursively adding markdown
files, and a `@src` directive for calling out and running arbitrary code,
adding its output if that's wanted. 
3. Running in `--watch` mode to generate a static website and rerun files 
when needed, with convenient tools to run arbitrary code included in markdown.
4. Supporting a minimal subset of Jekyll-like syntax so that I can replace my
Jekyll sites with minimal configuration.

## Example Usage

Examples of single page markdown to html.
```bash
# Create input.html with default styling and no code execution.
md2html input.md

# Create index.html and serve it, watching for changes and using default
# commands for compilation and execution of embedded source code.
md2html input.md -o index.html --watch --execute
```

Examples of building websites websites
```bash
# Build all files in src recursively and output to html directory, watching for
# changes and serving.
md2html -r src/* -O html --watch

# Does its best to try to compile a jekyll website at the current directory. 
# Only basic Jekyll functionality is supported.
md2html . --jekyll --execute

# Build with more customized configs (specific compilation tools, etc.)
md2html --config=md2html.json
```

***

TODO:

[x] Generate list of files to generate
[x] Generate folder watch list. (Note: "watch" functionality will be added later, for static website generation this is still important to satisfy the constraint: we can never generate into a watched folder unless the directory and the watched folder are equal.)
[x] Write sensible functions for finding templates (first user specified, then 
search `./templates`, then search `config.bundle_dir/templates`)
[x] Parse markdown for yaml headers and `@includes,@src,@src_begin,@src_end` and add to dependency graph recursively. Conceptually, we have the build targets (a bunch of nodes) the watch targets (also a bunch of nodes) but also a dependency graph. The dependency graph is a DAG whose purpose is twofold: For watching, we traverse downstream to the build target node to inform the build target it needs to be rebuilt. When building, we traverse upstream to pull in and load all the necessary info.
[] Build full dependency graph. Can traverse downstream (notify for building) or upstream (might need during build step).
[] Implement loading configuration JSON files. (start with `_MEIPASS/templates/_md2html.json` for defaults, then merge in user config. Prioritize `--config=`, else look for `./_md2html.json`)
[] Implement basic liquid templates (default.html with a {% page_contents %}) and markdown generation.
[] Implement basic conditional switches (include latex? inline CSS?)
[] Implement watch-and-serve for single files or directories.
[] Figure out mathml and also latex generation. Ensure that it works in both mathml, katex, mathjax modes.
[] Implement @toc command.
[] Get basic code highlighting working. 
[] Work on compilation of external code snippets `@src(file,opts)`.
[] Work on compilation of internal code snippets `@src_begin(opts)`.
[] Iron out bugs in single page content generation.
[] Challenge: add a minify flag, specifically intended for standalone page generation and getting standalone tutorial pages to be as small as possible.

Next, work on website generation...
[] Ensure flags for making CSS, js, etc. inlined or not (or CDN'd where relevant) work. 
[] Get my SICP project webpage building.
[] Work on using less basic Liquid features: control flow, predefined Jekyll-like variables.
[] RSS generation
[] Jekyll site building






