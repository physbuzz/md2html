from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
from enum import Enum
import argparse
import sys
import json
import os

################################################################
############################## CLI #############################
################################################################

def print_usage():
    print("""md2html - Markdown to HTML converter with advanced features

Usage:
    md2html [options] [files...]
    md2html                          # Look for md2html.json config

Options:
    -h, --help                       Show this help message
    -o, --output PATH                Output file (single input) or directory (multiple inputs)
    -r, --recursive                  Process directories recursively
    -w, --watch                      Watch files for changes and rebuild
    -s, --serve                      Start development server (implies --watch)
    -p, --port PORT                  Server port (default: 8000)
    -e, --execute                    Execute embedded code blocks
    -n, --no-overwrite              Don't overwrite existing files
    -v, --verbose                    Verbose output
    --d, --dry-run                    Dry run mode (output build DAG as JSON)
    --templates PATH                 Templates directory (default: ./templates, then bundle/templates)

Examples:
    md2html note.md                  # Creates note.html (overwrites)
    md2html note.md -o index.html    # Creates index.html
    md2html file1.md file2.md -o html/   # Creates html/file1.html, html/file2.html
    md2html -r src -o html         # Creates html/file1.html, ...
    md2html -r src1 src2 -o html/         # Creates html/src1/file1.html, html/src2/file2.html
    md2html -r . -o _site --serve    # Build site and serve
""")

# Command line configuration for md2html
@dataclass
class Config:
    # Internal config:
    invoked_from : Path
    bundle_root : Path # root package directory or temp directory for bundled resources
    # If we call `md2html src -o html` then this points to src, and we generate html/file1.html, html/file2.html
    # If we call `md2html src1 src2 -o html` then this points to . and we generate html/src1/file1.html, html/src2/file2.html
    # If we call `md2html note.md -o index.html` then this points to . and we generate index.html
    base_input_path: Optional[Path] = None
    single_file_mode: bool = False  # True if only one file is given, False if multiple files or directories are given

    # CLI options
    output_dir: Optional[Path] = None # may be file (single input) or dir (multiple inputs)
    recursive: bool = False
    watch: bool = False
    serve: bool = False
    port: int = 8000
    execute: bool = False
    force_overwrite: bool = True
    verbose: bool = False
    dry_run: bool = False
    templates_dir: Optional[Path] = None  
    def calculate_output_path(self, input_path: Path) -> Path:
        if not (self.base_input_path.resolve() in input_path.resolve().parents):
            print(f"Error: {input_path} is not under base input path {self.base_input_path}", file=sys.stderr)
            sys.exit(1)
        
        if self.output_dir is None:
            output_file=input_path 
        else:
            output_file=self.output_dir/input_path.resolve().relative_to(self.base_input_path.resolve())

        if output_file.suffix.lower() == '.md':
            output_file = output_file.with_suffix('.html')
        
        return output_file

    def find_template(self, template_name: str) -> Optional[Path]:
        """Find a template file, searching in order:
        1. User-specified templates directory
        2. ./templates
        3. bundle_root/templates
        
        Returns None if template is not found in any location.
        """
        search_paths = []
        
        # 1. User-specified templates directory
        if self.templates_dir:
            search_paths.append(self.templates_dir)
        
        # 2. ./templates (relative to where md2html was invoked)
        search_paths.append(self.invoked_from / "templates")
        
        # 3. bundle_root/templates (bundled templates)
        search_paths.append(self.bundle_root / "templates")
        
        for templates_dir in search_paths:
            if templates_dir.exists() and templates_dir.is_dir():
                template_path = templates_dir / template_name
                if template_path.exists() and template_path.is_file():
                    return template_path
        
        return None

    def get_templates_search_paths(self) -> List[Path]:
        """Get the list of directories that will be searched for templates"""
        search_paths = []
        
        if self.templates_dir:
            search_paths.append(self.templates_dir)
        
        search_paths.append(self.invoked_from / "templates")
        search_paths.append(self.bundle_root / "templates")
        
        return search_paths

def parse_args(argv: List[str]) -> Tuple[Config, List[str]]:
    invoked_from = Path.cwd()
    if getattr(sys, 'frozen', False):
        bundle_root = Path(sys._MEIPASS).resolve()
    else:
        bundle_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        description="Markdown to HTML converter with advanced features",
        usage="md2html [options] [files...]",
        add_help=False  # We'll handle -h manually if needed
    )
    parser.add_argument('-h', '--help', action='store_true', help="Show this help message")
    parser.add_argument('-o', '--output', type=Path, help="Output file (single input) or directory (multiple inputs)")
    parser.add_argument('-r', '--recursive', action='store_true', help="Process directories recursively")
    parser.add_argument('-w', '--watch', action='store_true', help="Watch files for changes and rebuild")
    parser.add_argument('-s', '--serve', action='store_true', help="Start development server (implies --watch)")
    parser.add_argument('-p', '--port', type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument('-e', '--execute', action='store_true', help="Execute embedded code blocks")
    parser.add_argument('-n', '--no-overwrite', action='store_true', help="Don't overwrite existing files")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose output")
    parser.add_argument('-d', '--dry-run', action='store_true', help="Dry run mode (output build DAG as JSON)")
    parser.add_argument('--templates', type=Path, help="Templates directory (default: ./templates, then bundle/templates)")
    parser.add_argument('inputs', nargs='*', help="Input files or directories")  # Positional args

    args = parser.parse_args(argv)

    if args.help:
        print_usage()
        sys.exit(0)

    config = Config(invoked_from=invoked_from, bundle_root=bundle_root)
    config.output_dir = args.output
    config.recursive = args.recursive
    config.watch = args.watch
    config.serve = args.serve
    if config.serve:
        config.watch = True
    config.port = args.port
    config.execute = args.execute
    config.force_overwrite = not args.no_overwrite
    config.verbose = args.verbose
    config.dry_run = args.dry_run
    config.templates_dir = args.templates

    return config, args.inputs  # args.inputs is the list of positional args
