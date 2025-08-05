from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
import getopt
import sys
import os
from . import cli

# Command line configuration for md2html
@dataclass
class Config:
    """Configuration for md2html operations"""
    invoked_from : Path
    bundle_root : Path
    input_files: List[Path] = field(default_factory=list)
    output_file: Optional[Path] = None
    output_dir: Path = Path('.')
    recursive: bool = False
    watch: bool = False
    serve: bool = False
    port: int = 8000
    execute: bool = False
    force_overwrite: bool = True
    verbose: bool = False
    build_commands: Dict[str, str] = field(default_factory=dict)
    
    def merge(self, other: 'Config'):
        """Merge another config into this one (other takes precedence)"""
        for field_name in self.__dataclass_fields__:
            other_value = getattr(other, field_name)
            if field_name == 'build_commands':
                # Merge dictionaries
                self.build_commands.update(other_value)
            elif field_name == 'input_files':
                # Extend lists
                self.input_files.extend(other_value)
            elif other_value not in [None, [], {}, Path('.')]:
                # Override non-default values
                setattr(self, field_name, other_value)

#    # Fetch a page template file. First check bundle_root, then
#    # the directory the command was invoked from. TODO: we might want to add
#    # another way to have user-defined templates, or to easily incorporate Jekyll-style
#    # _includes and _layouts.
#    def fetchTemplate(self, template_name: str) -> str:
#        template_path = self.fetchTemplatePath(template_name)
#        with open(template_path, 'r', encoding='utf-8') as file:
#            return file.read()
#    def fetchTemplatePath(self, template_name: str) -> Path:
#        template_path = self.bundle_root / "templates" / template_name
#        if template_path.exists():
#            return template_path
#        template_path = self.invoked_from / "templates" / template_name
#        if template_path.exists():
#            return template_path
#        raise FileNotFoundError(f"Template {template_name} not found in {self.bundle_root / 'templates'}")
#    
#    # Fetch a file included in markdown through @include. Prioritize the working directory,
#    # then the invoked_from.
#    def fetchInclude(self, include_name: str) -> str:
#        include_path = self.fetchIncludePath(include_name)
#        with open(include_path, 'r', encoding='utf-8') as file:
#            return file.read()
#    def fetchIncludePath(self, include_name: str) -> Path:
#        include_path = self.work_dir / include_name
#        if include_path.exists():
#            return include_path
#        include_path = self.invoked_from / include_name
#        if include_path.exists():
#            return include_path
#        raise FileNotFoundError(f"Include {include_name} not found in {self.work_dir} or {self.invoked_from}")


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
    -o, --output FILE                Output filename (single file mode only)
    -O, --output-dir DIR             Output directory for multiple files
    -r, --recursive                  Process directories recursively
    -w, --watch                      Watch files for changes and rebuild
    -s, --serve                      Start development server (implies --watch)
    -p, --port PORT                  Server port (default: 8000)
    -e, --execute                    Execute embedded code blocks
    -j, --jekyll                     Jekyll compatibility mode
    -c, --config FILE                Use configuration file
    -n, --no-overwrite              Don't overwrite existing files
    -v, --verbose                    Verbose output

Examples:
    md2html note.md                  # Creates note.html (overwrites)
    md2html file1.md file2.md        # Creates file1.html, file2.html
    md2html -r src/ -O html/         # Recursive with structure preserved
    md2html -r . -O _site --serve    # Build site and serve
""")

def parse_args(argv: List[str]) -> Config:
    """Parse command line arguments into Config"""

    invoked_from = Path.cwd()
    if getattr(sys, 'frozen', False):
        bundle_root = Path(sys._MEIPASS).resolve()
    else:
        bundle_root = Path(__file__).resolve().parent.parent
    config = Config(invoked_from=invoked_from, bundle_root=bundle_root)
    
    try:
        opts, args = getopt.getopt(argv, "ho:O:rwsp:env", [
            "help", "output=", "output-dir=", "recursive", "watch",
            "serve", "port=", "execute", 
            "no-overwrite", "verbose"])
    except getopt.GetoptError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif opt in ("-o", "--output"):
            config.output_file = Path(arg)
        elif opt in ("-O", "--output-dir"):
            config.output_dir = Path(arg)
        elif opt in ("-r", "--recursive"):
            config.recursive = True
        elif opt in ("-w", "--watch"):
            config.watch = True
        elif opt in ("-s", "--serve"):
            config.serve = True
            config.watch = True
        elif opt in ("-p", "--port"):
            config.port = int(arg)
        elif opt in ("-e", "--execute"):
            config.execute = True
        elif opt in ("-n", "--no-overwrite"):
            config.force_overwrite = False
        elif opt in ("-v", "--verbose"):
            config.verbose = True
    return config, args

#def addBuildGraph(config: Config, file_path: Path, graph):
def addBuildGraph(config: Config, file_path: Path):
    if not file_path.exists():
        print(f"Error: File {file_path} does not exist.", file=sys.stderr)
        sys.exit(1)
    #if graph.has_node(file_path):
        #return
    
    if not file_path.is_dir():
        if file_path.suffix.lower() == '.md':
            print("MD build: ", file_path, " -> ", config.output_dir / file_path.with_suffix('.html').name)
            # graph.add_node(file_path)
        else:
            print("copy: ", file_path, " -> ", config.output_dir / file_path.name)
    else:
        if not config.recursive:
            print(f"Error: {file_path} is a directory, but recursive mode is not enabled. (Maybe try ./* instead of .)", file=sys.stderr)
            sys.exit(1)
        if config.output_dir is None:
            print(f"Error: Output directory must be specified for recursive builds: {file_path}", file=sys.stderr)
            sys.exit(1)
        for item in file_path.iterdir():
            addBuildGraph(config, item)

    
def main():
    argumentList = sys.argv[1:]

    cfg, args = parse_args(argumentList)

    for arg in args:
        path = Path(arg)
        addBuildGraph(cfg, path)


if __name__ == "__main__":
    main()
