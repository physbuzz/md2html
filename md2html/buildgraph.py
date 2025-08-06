from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
from enum import Enum
import argparse
import sys
import json
import os
from .config import Config

class BuildTargetType(Enum):
    MARKDOWN = 'markdown'
    COPY = 'copy'
# not handled currently:
#     HTML = 'html'
#     EXECUTE = 'execute'
#     DEPENDENCY = 'dependency'

@dataclass
class BuildTarget:
    node_type: BuildTargetType
    input_path: Path
    output_path: Optional[Path] = None
@dataclass
class BuildTargets:
    nodes: Dict[Path, BuildTarget] = field(default_factory=dict)

    def node_exists(self, path: Path) -> bool:
        return path in self.nodes
    def add_node(self, node: BuildTarget):
        if self.node_exists(node.input_path):
            print(f"Error: Node for {node.input_path} already exists in build targets", file=sys.stderr)
            sys.exit(1)
        self.nodes[node.input_path] = node
    def get_json_str(self) -> str:
        json_data = {
            "nodes": [
                {
                    "input": str(node.input_path),
                    "output": str(node.output_path) if node.output_path else None,
                    "type": node.node_type.value
                }
                for node in self.nodes.values()
            ]
        }
        return json.dumps(json_data, indent=2)


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
def handle_target(path: Path, config: Config, target_list: BuildTargets):
    if not path.exists():
        print(f"Error: Input file {path} does not exist.", file=sys.stderr)
        sys.exit(1)
    if should_ignore_path(config, path) and not config.single_file_mode:
        return
    
    if path.is_file():
        output_path = config.calculate_output_path(path)
        # Override for single file mode with file output
        if config.single_file_mode and config.output_dir and config.output_dir.suffix:
            output_path = config.output_dir

        if path.suffix.lower() == '.md':
            target_list.add_node(BuildTarget(BuildTargetType.MARKDOWN,path,output_path))
        else:
            if output_path.resolve() != path.resolve():
                target_list.add_node(BuildTarget(BuildTargetType.COPY,path,output_path))
    elif path.is_dir():
        if not config.recursive:
            print(f"Error: {path} is a directory, but recursive mode is not enabled. (Maybe try ./* instead of .)", file=sys.stderr)
            sys.exit(1)
        if config.output_dir \
            and path.resolve() == config.output_dir.resolve() \
            and (config.base_input_path.resolve() in config.output_dir.resolve().parents):
            return
        
        for item in path.iterdir():
            if not should_ignore_path(config, item):
                handle_target(item, config, target_list)