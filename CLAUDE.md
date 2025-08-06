# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

md2html is a Python-based markdown to HTML converter that integrates markdown processing with Pygments syntax highlighting, python-liquid templating, and other static site generation features. It supports both single-page conversion and recursive website building with Jekyll-like functionality.

## Common Commands

### Development
```bash
# Run the main application
make run
python -m md2html.md2html

# Run tests
make test
python -m md2html.test --quiet

# Build executable
make build
pyinstaller -F main.py -n md2html

# Clean build artifacts
make clean
```

### Testing Options
```bash
# Run all test suites
python -m md2html.test

# Run specific test suite
python -m md2html.test --testsuite=filepaths

# Quiet mode (only failures)
python -m md2html.test --quiet

# Very quiet mode (only counts)
python -m md2html.test --veryquiet

# Verbose mode with details
python -m md2html.test --verbose

# Keep test files for debugging
python -m md2html.test --keep-files
```

### Usage Examples
```bash
# Single file conversion
python -m md2html.md2html input.md

# Convert with specific output
python -m md2html.md2html input.md -o index.html

# Recursive directory processing
python -m md2html.md2html -r src -o html

# Watch mode for development
python -m md2html.md2html -r . -o _site --serve

# Dry run to see build graph
python -m md2html.md2html --dry-run input.md
```

## Architecture

### Core Components

**md2html/md2html.py**: Main entry point that handles command-line parsing and orchestrates the build process.

**md2html/config.py**: Configuration management with CLI argument parsing. Contains the `Config` dataclass that manages:
- Input/output path calculations
- Single file vs. multi-file mode detection
- Build options (recursive, watch, serve, execute)

**md2html/buildgraph.py**: Build target management system that creates a dependency graph for files:
- `BuildTarget`: Represents individual files to be processed
- `BuildTargetType`: Enum for MARKDOWN, COPY, HTML, EXECUTE, DEPENDENCY
- `BuildTargets`: Collection managing the build DAG
- `handle_target()`: Recursively processes files and directories

**main.py**: PyInstaller entry point that imports and calls the main function.

### Key Design Patterns

1. **Build Target System**: Files are modeled as build targets in a dependency graph, supporting future features like `@include` and `@src` directives for recursive markdown inclusion.

2. **Path Resolution**: Complex logic for handling different input/output scenarios:
   - Single file: `note.md` → `note.html`
   - Directory: `md2html -r src -o html` creates mirrored structure
   - Multi-input: `md2html src1 src2 -o html` preserves relative paths

3. **Configuration Cascade**: Supports multiple config sources (CLI args, JSON files, defaults) with planned support for `_md2html.json` config files.

### Template System

Templates are located in `templates/` directory:
- `default.css`: Default styling
- `head.html`: HTML head template

The system will search for templates in this order:
1. User-specified templates
2. `./templates` directory
3. `config.bundle_dir/templates` (bundled resources)

### Testing Framework

Custom test framework in `md2html/test.py` with modular test suites:
- `filepaths`: Tests file path resolution and DAG generation
- Planned: `server`, `watch` test suites

Uses `TestContext` for output management (quiet/verbose modes) and temporary file handling.

## Dependencies

Key Python packages (see requirements.txt):
- `Markdown`: Core markdown processing
- `Pygments`: Syntax highlighting
- `python-liquid`: Liquid templating engine
- `python-frontmatter`: YAML front matter parsing  
- `watchdog`: File watching for development server
- `pyinstaller`: Executable building
- `pytest`: Testing framework

## Future Features

The codebase is architected to support several planned features:
- Liquid template processing with Jekyll-like variables
- Code execution with `@src` directives
- File watching and serving for development
- Dependency graph for `@include` directives
- MathML/KaTeX rendering
- RSS generation
- Jekyll site compatibility