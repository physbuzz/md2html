A markdown -> html generator for several purposes: 

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

