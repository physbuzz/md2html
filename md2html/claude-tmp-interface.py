#!/usr/bin/env python3
# Claude 4 Sonnet generated
"""
md2html CLI - Main command line interface and build orchestration
"""

import sys
import os
import getopt
import json
import threading
import time
import signal
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque

# External imports (from other modules in the project)
# from md2html.scanner import scan_markdown_dependencies
# from md2html.converter import convert_markdown_to_html
# from md2html.watcher import FileWatcher
# from md2html.server import DevServer
# from md2html.executor import execute_code_block

@dataclass
class Config:
    """Configuration for md2html operations"""
    input_files: List[Path] = field(default_factory=list)
    output_file: Optional[Path] = None
    output_dir: Path = Path('.')
    recursive: bool = False
    watch: bool = False
    serve: bool = False
    port: int = 8000
    execute: bool = False
    jekyll_mode: bool = False
    config_file: Optional[Path] = None
    force_overwrite: bool = True
    preserve_structure: bool = True
    verbose: bool = False
    build_commands: Dict[str, str] = field(default_factory=dict)
    template_path: Optional[Path] = None
    default_css: bool = True
    
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


@dataclass
class BuildItem:
    """Represents a single item in the build plan"""
    src: Path
    dest: Path
    include_dependencies: List[Path] = field(default_factory=list)
    build_dependencies: List[Path] = field(default_factory=list)
    build_command: Optional[str] = None
    item_type: str = 'markdown'  # 'markdown', 'code', 'resource'
    
    def __hash__(self):
        return hash(self.src)

class BuildPlanner:
    """Plans and orders the build process"""
    
    def __init__(self, config: Config):
        self.config = config
        self.build_items: Dict[Path, BuildItem] = {}
        self.dependency_graph: Dict[Path, Set[Path]] = defaultdict(set)
        
    def plan_build(self, input_files: List[Path]) -> List[BuildItem]:
        """Create a complete build plan with proper dependency ordering"""
        # First pass: Create build items for all markdown files
        for md_file in input_files:
            self._create_markdown_build_item(md_file)
        
        # Second pass: Scan for dependencies and create build items for them
        self._scan_all_dependencies()
        
        # Third pass: Order by dependencies
        ordered_items = self._topological_sort()
        
        return ordered_items
    
    def _create_markdown_build_item(self, src_file: Path) -> BuildItem:
        """Create a build item for a markdown file"""
        if src_file in self.build_items:
            return self.build_items[src_file]
        
        dest_file = self._determine_output_path(src_file)
        item = BuildItem(
            src=src_file,
            dest=dest_file,
            item_type='markdown'
        )
        self.build_items[src_file] = item
        return item
    
    def _determine_output_path(self, src_file: Path) -> Path:
        """Calculate where the output file should go"""
        # Special case: single file with explicit output
        if len(self.config.input_files) == 1 and self.config.output_file:
            return self.config.output_file
        
        # Find relative path from input directory
        rel_path = src_file
        for input_path in self.config.input_files:
            if input_path.is_dir():
                try:
                    rel_path = src_file.relative_to(input_path)
                    break
                except ValueError:
                    pass
        
        # Change extension based on file type
        if src_file.suffix == '.md':
            output_name = rel_path.with_suffix('.html')
        else:
            # Code files get .out extension
            output_name = rel_path.parent / (rel_path.name + '.out')
        
        # Apply output directory and structure preferences
        if self.config.output_dir != Path('.'):
            if self.config.preserve_structure:
                output_path = self.config.output_dir / output_name
            else:
                output_path = self.config.output_dir / output_name.name
        else:
            # In-place conversion
            output_path = src_file.parent / output_name.name
        
        return output_path
    
    def _scan_all_dependencies(self):
        """Scan all markdown files for dependencies"""
        # Work on a copy since we'll be adding items during iteration
        markdown_items = [item for item in self.build_items.values() 
                         if item.item_type == 'markdown']
        
        for item in markdown_items:
            # Use external scanner function
            deps = scan_markdown_dependencies(item.src)
            
            # Process each dependency
            for dep_info in deps:
                dep_path = item.src.parent / dep_info['path']
                dep_path = dep_path.resolve()
                
                if dep_info['type'] == 'include':
                    # @include dependencies just need watching
                    item.include_dependencies.append(dep_path)
                    # But we still need to process them for their dependencies
                    if dep_path.suffix == '.md' and dep_path not in self.build_items:
                        self._create_markdown_build_item(dep_path)
                
                elif dep_info['type'] == 'src':
                    # @src dependencies need building
                    if dep_path not in self.build_items:
                        self._create_code_build_item(dep_path, dep_info.get('options', {}))
                    item.build_dependencies.append(dep_path)
                    self.dependency_graph[item.src].add(dep_path)
    
    def _create_code_build_item(self, src_file: Path, options: Dict[str, Any]) -> BuildItem:
        """Create a build item for a code file"""
        if src_file in self.build_items:
            return self.build_items[src_file]
        
        dest_file = self._determine_output_path(src_file)
        
        # Determine build command
        build_command = None
        if self.config.execute and options.get('execute', True):
            ext = src_file.suffix
            if ext in self.config.build_commands:
                build_command = self.config.build_commands[ext].format(
                    src=str(src_file),
                    dest=str(dest_file)
                )
            else:
                # Default commands for common languages
                default_commands = {
                    '.py': 'python3 {src} > {dest}',
                    '.js': 'node {src} > {dest}',
                    '.cpp': 'g++ -o {dest}.exe {src} && {dest}.exe > {dest}',
                    '.c': 'gcc -o {dest}.exe {src} && {dest}.exe > {dest}',
                    '.java': 'javac {src} && java {src_base} > {dest}',
                    '.rs': 'rustc {src} -o {dest}.exe && {dest}.exe > {dest}',
                    '.go': 'go run {src} > {dest}',
                    '.rb': 'ruby {src} > {dest}',
                    '.sh': 'bash {src} > {dest}',
                }
                build_command = default_commands.get(ext)
                if build_command:
                    build_command = build_command.format(
                        src=str(src_file),
                        dest=str(dest_file),
                        src_base=src_file.stem
                    )
        
        item = BuildItem(
            src=src_file,
            dest=dest_file,
            build_command=build_command,
            item_type='code'
        )
        self.build_items[src_file] = item
        return item
    
    def _topological_sort(self) -> List[BuildItem]:
        """Sort build items by dependencies"""
        # Calculate in-degree for each node
        in_degree = defaultdict(int)
        for src in self.build_items:
            for dep in self.dependency_graph[src]:
                in_degree[dep] += 1
        
        # Find all nodes with no dependencies
        queue = deque([src for src in self.build_items if in_degree[src] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(self.build_items[current])
            
            # Remove this node from graph
            for dependent in self.dependency_graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Check for cycles
        if len(result) != len(self.build_items):
            # Find cycle for error reporting
            remaining = set(self.build_items.keys()) - {item.src for item in result}
            raise ValueError(f"Circular dependency detected involving: {remaining}")
        
        # Reverse to get dependency-first order
        return list(reversed(result))

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
    config = Config()
    
    try:
        opts, args = getopt.getopt(argv, "ho:O:rwsp:ejc:nv", [
            "help", "output=", "output-dir=", "recursive", "watch",
            "serve", "port=", "execute", "jekyll", "config=",
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
        elif opt in ("-j", "--jekyll"):
            config.jekyll_mode = True
        elif opt in ("-c", "--config"):
            config.config_file = Path(arg)
        elif opt in ("-n", "--no-overwrite"):
            config.force_overwrite = False
        elif opt in ("-v", "--verbose"):
            config.verbose = True
        elif opt == "--preserve-structure":
            config.preserve_structure = True
        elif opt == "--flatten":
            config.preserve_structure = False
        elif opt == "--template":
            config.template_path = Path(arg)
        elif opt == "--no-css":
            config.default_css = False
    
    # Process input files
    for arg in args:
        path = Path(arg)
        if path.exists():
            config.input_files.append(path)
        else:
            print(f"Warning: File not found: {arg}", file=sys.stderr)
    
    return config

def load_config_file(path: Path) -> Config:
    """Load configuration from JSON file"""
    config = Config()
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Map JSON to Config fields
        if 'input' in data:
            if isinstance(data['input'], str):
                config.input_files = [Path(data['input'])]
            else:
                config.input_files = [Path(p) for p in data['input']]
        
        if 'output_dir' in data:
            config.output_dir = Path(data['output_dir'])
        
        # Simple boolean/string/int mappings
        simple_fields = {
            'recursive': 'recursive',
            'watch': 'watch',
            'execute': 'execute',
            'jekyll': 'jekyll_mode',
            'verbose': 'verbose',
            'force_overwrite': 'force_overwrite',
            'preserve_structure': 'preserve_structure',
            'port': 'port',
            'template': 'template_path',
            'default_css': 'default_css'
        }
        
        for json_key, config_key in simple_fields.items():
            if json_key in data:
                value = data[json_key]
                if json_key == 'template':
                    value = Path(value)
                setattr(config, config_key, value)
        
        # Handle serve (might be boolean or dict)
        if 'serve' in data:
            if isinstance(data['serve'], bool):
                config.serve = data['serve']
            elif isinstance(data['serve'], dict):
                config.serve = data['serve'].get('enabled', False)
                config.port = data['serve'].get('port', config.port)
        
        # Build commands
        if 'build_commands' in data:
            config.build_commands = data['build_commands']
        
        return config
        
    except Exception as e:
        print(f"Error loading config file: {e}", file=sys.stderr)
        sys.exit(1)

def collect_input_files(config: Config) -> List[Path]:
    """Expand input paths to actual markdown files"""
    all_files = []
    
    for input_path in config.input_files:
        if input_path.is_file():
            if input_path.suffix == '.md':
                all_files.append(input_path)
        elif input_path.is_dir():
            if config.recursive:
                all_files.extend(input_path.rglob('*.md'))
            else:
                all_files.extend(input_path.glob('*.md'))
    
    # Remove duplicates and sort
    return sorted(set(all_files))

def execute_build_item(item: BuildItem, config: Config) -> bool:
    """Execute a single build item"""
    try:
        # Skip if destination exists and overwrite is disabled
        if item.dest.exists() and not config.force_overwrite:
            if config.verbose:
                print(f"Skipping {item.src} -> {item.dest} (exists)")
            return True
        
        # Create output directory
        item.dest.parent.mkdir(parents=True, exist_ok=True)
        
        if config.verbose:
            print(f"Building {item.src} -> {item.dest}")
        
        if item.item_type == 'markdown':
            # Convert markdown to HTML
            html_content = convert_markdown_to_html(
                item.src,
                template=config.template_path,
                include_css=config.default_css,
                execute_code=config.execute
            )
            item.dest.write_text(html_content, encoding='utf-8')
            
        elif item.item_type == 'code' and item.build_command:
            # Execute code and capture output
            output = execute_code_block(item.build_command, cwd=item.src.parent)
            item.dest.write_text(output, encoding='utf-8')
        
        return True
        
    except Exception as e:
        print(f"Error building {item.src}: {e}", file=sys.stderr)
        return False

def build_all(build_plan: List[BuildItem], config: Config) -> Dict[Path, Path]:
    """Execute all build items and return mapping of src->dest"""
    successful_builds = {}
    failed_count = 0
    
    for item in build_plan:
        if execute_build_item(item, config):
            successful_builds[item.src] = item.dest
        else:
            failed_count += 1
    
    if config.verbose or failed_count > 0:
        print(f"Built {len(successful_builds)} files, {failed_count} failed")
    
    return successful_builds

def run_jekyll_mode(config: Config):
    """Run in Jekyll compatibility mode"""
    print("Jekyll mode: Setting up Jekyll-style build...")
    
    # Override config for Jekyll conventions
    config.input_files = [Path('.')]
    config.output_dir = Path('_site')
    config.recursive = True
    
    # Look for _config.yml
    jekyll_config = Path('_config.yml')
    if jekyll_config.exists():
        # We'd parse this for Jekyll-specific settings
        pass
    else:
        print("Warning: No _config.yml found")
    
    # Exclude Jekyll directories
    excludes = {'_site', '.jekyll-cache', '_drafts', '.git', '.github'}
    
    # Collect files with Jekyll filtering
    all_files = []
    for f in Path('.').rglob('*.md'):
        if not any(part.startswith('.') or part.startswith('_') or part in excludes 
                  for part in f.parts):
            all_files.append(f)
    
    # Continue with normal build
    return all_files

def watch_files(build_plan: List[BuildItem], file_mapping: Dict[Path, Path], config: Config):
    """Watch files and rebuild on changes"""
    print("Watching for changes... Press Ctrl+C to stop")
    
    # Create reverse mapping for efficient lookups
    all_watched_files = set()
    file_to_items = defaultdict(set)
    
    for item in build_plan:
        # Watch the source file
        all_watched_files.add(item.src)
        file_to_items[item.src].add(item)
        
        # Watch include dependencies
        for dep in item.include_dependencies:
            all_watched_files.add(dep)
            file_to_items[dep].add(item)
        
        # Watch build dependencies
        for dep in item.build_dependencies:
            all_watched_files.add(dep)
            file_to_items[dep].add(item)
    
    # Use external watcher
    watcher = FileWatcher(list(all_watched_files))
    
    def on_file_changed(changed_file: Path):
        affected_items = file_to_items.get(changed_file, set())
        if affected_items:
            print(f"\nFile changed: {changed_file}")
            print(f"Rebuilding {len(affected_items)} affected files...")
            
            # Rebuild affected items in dependency order
            items_to_rebuild = []
            for item in build_plan:
                if item in affected_items:
                    items_to_rebuild.append(item)
            
            for item in items_to_rebuild:
                execute_build_item(item, config)
    
    watcher.start(on_file_changed)
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping watch...")
        watcher.stop()

def start_server(config: Config):
    """Start the development server"""
    server = DevServer(
        root_dir=config.output_dir,
        port=config.port
    )
    
    print(f"Starting server at http://localhost:{config.port}")
    print(f"Serving files from {config.output_dir.absolute()}")
    
    server.start()

def main():
    """Main entry point"""
    # Handle no arguments - look for config file
    if len(sys.argv) == 1:
        config_path = Path('md2html.json')
        if config_path.exists():
            config = load_config_file(config_path)
        else:
            print("No input files specified and no md2html.json found")
            print_usage()
            sys.exit(1)
    else:
        # Parse command line arguments
        config = parse_args(sys.argv[1:])
        
        # Load additional config file if specified
        if config.config_file:
            file_config = load_config_file(config.config_file)
            config.merge(file_config)
    
    # Handle Jekyll mode
    if config.jekyll_mode:
        input_files = run_jekyll_mode(config)
    else:
        # Collect input files
        input_files = collect_input_files(config)
    
    if not input_files:
        print("No markdown files found to process")
        sys.exit(1)
    
    print(f"Found {len(input_files)} markdown files to process")
    
    # Create build plan
    planner = BuildPlanner(config)
    build_plan = planner.plan_build(input_files)
    
    if config.verbose:
        print(f"Build plan contains {len(build_plan)} items")
        for item in build_plan:
            print(f"  {item.src} -> {item.dest} ({item.item_type})")
    
    # Execute build
    file_mapping = build_all(build_plan, config)
    
    # Start server if requested
    if config.serve:
        server_thread = threading.Thread(
            target=start_server,
            args=(config,),
            daemon=True
        )
        server_thread.start()
    
    # Watch files if requested
    if config.watch:
        # Set up signal handling for clean shutdown
        def signal_handler(sig, frame):
            print("\nShutting down...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        watch_files(build_plan, file_mapping, config)
    else:
        print(f"Successfully built {len(file_mapping)} files")

# External function signatures that would be implemented elsewhere:
#
# def scan_markdown_dependencies(file_path: Path) -> List[Dict[str, Any]]:
#     """Scan a markdown file for @import and @src directives
#     Returns: [{type: 'include'|'src', path: 'relative/path', options: {...}}, ...]
#     """
#
# def convert_markdown_to_html(src: Path, template: Optional[Path] = None, 
#                             include_css: bool = True, execute_code: bool = False) -> str:
#     """Convert markdown file to HTML string"""
#
# def execute_code_block(command: str, cwd: Path) -> str:
#     """Execute a command and return its output"""
#
# class FileWatcher:
#     """Watch files for changes using watchdog"""
#     def __init__(self, files: List[Path]): ...
#     def start(self, callback: Callable[[Path], None]): ...
#     def stop(self): ...
#
# class DevServer:
#     """Simple HTTP development server"""
#     def __init__(self, root_dir: Path, port: int): ...
#     def start(self): ...

