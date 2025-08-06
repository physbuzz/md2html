from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
from enum import Enum
import argparse
import sys
import json
import os
from . import cli

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


class BuildNodeType(Enum):
    MARKDOWN = 'markdown'
    COPY = 'copy'
# not handled currently:
#     HTML = 'html'
#     EXECUTE = 'execute'
#     DEPENDENCY = 'dependency'

@dataclass
class BuildNode:
    node_type: BuildNodeType
    input_path: Path
    output_path: Optional[Path] = None
@dataclass
class BuildGraph:
    nodes: Dict[Path, BuildNode] = field(default_factory=dict)

    def node_exists(self, path: Path) -> bool:
        return path in self.nodes
    def add_node(self, node: BuildNode):
        if self.node_exists(node.input_path):
            print(f"Error: Node for {node.input_path} already exists in the graph", file=sys.stderr)
            sys.exit(1)
        self.nodes[node.input_path] = node
    def graph_json(self) -> str:
        graph_data = {
            "nodes": [
                {
                    "input": str(node.input_path),
                    "output": str(node.output_path) if node.output_path else None,
                    "type": node.node_type.value
                }
                for node in self.nodes.values()
            ]
        }
        return json.dumps(graph_data, indent=2)

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

    return config, args.inputs  # args.inputs is the list of positional args

def calculate_output_path(config: Config, input_path: Path) -> Path:
    if not (config.base_input_path.resolve() in input_path.resolve().parents):
        print(f"Error: {input_path} is not under base input path {config.base_input_path}", file=sys.stderr)
        sys.exit(1)
    
    if config.output_dir is None:
        output_file=input_path 
    else:
        output_file=config.output_dir/input_path.relative_to(config.base_input_path)

    if output_file.suffix.lower() == '.md':
        output_file = output_file.with_suffix('.html')
    
    return output_file

""" 
`md2html _file.md` still builds `_file.html`.
`md2html html -o html` should still parse the html directory. It's fine because base_input_dir = "html".
`md2html html html2 -o html` should give a warning to the user in verbose mode. 
    If we were to build html into html/html we would recurse forever, so we have to ignore it, which might not be expected behavior.
`md2html -o html ./*` makes sure to ignore the html directory. This could also cause infinite recursion if not handled, 
    but it's such a common case we should figure it out and not give an error to the user.
"""
def should_ignore_path(config: Config, file_path: Path) -> bool:
    if file_path.name.startswith('_') or file_path.name.startswith('.'):
        return True
    return False
def handle_target(path: Path, config: Config, graph: BuildGraph):
    if not path.exists():
        print(f"Error: Input file {path} does not exist.", file=sys.stderr)
        sys.exit(1)
    
    if path.is_file():

        output_path = calculate_output_path(config, path)
        # Override for single file mode with file output
        if config.single_file_mode and config.output_dir and config.output_dir.suffix:
            output_path = config.output_dir

        if path.suffix.lower() == '.md':
            graph.add_node(BuildNode(BuildNodeType.MARKDOWN,path,output_path))
        else:
            if output_path.resolve() != path.resolve():
                graph.add_node(BuildNode(BuildNodeType.COPY,path,output_path))
    elif path.is_dir():
        if not config.recursive:
            print(f"Error: {path} is a directory, but recursive mode is not enabled. (Maybe try ./* instead of .)", file=sys.stderr)
            sys.exit(1)
        if config.output_dir \
            and path.resolve() == config.output_dir.resolve() \
            and (config.base_input_path in config.output_dir.parents):
            return
        
        for item in path.iterdir():
            if not should_ignore_path(config, item):
                handle_target(item, config, graph)

def main():
    argument_list = sys.argv[1:]
    
    config, args = parse_args(argument_list)
    
    # TODO: allow for no args to mean "look for md2html.json config"
    if not args:
        print("Error: No input files specified", file=sys.stderr)
        sys.exit(1)

    args = [Path(arg) for arg in args]
    if len(args) == 1:
        if not args[0].exists():
            print(f"Error: Input file argument {args[0]} does not exist", file=sys.stderr)
            sys.exit(1)
        elif args[0].is_dir():
            config.base_input_path = args[0]
        elif args[0].is_file():
            config.base_input_path = args[0].parent
            config.single_file_mode = True
        else:
            print(f"Error: {args[0]} is neither a file nor a directory", file=sys.stderr)
            sys.exit(1)
    else:
        config.base_input_path = config.invoked_from

    graph = BuildGraph()
    
    for path in args:
        handle_target(path, config, graph)
    
    print(graph.graph_json())

if __name__ == "__main__":
    main()