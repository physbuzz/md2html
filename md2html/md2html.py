from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
from enum import Enum
import argparse
import sys
import json
import os

from .config import Config, parse_args
from .buildgraph import BuildTarget, BuildTargetType, BuildTargets, handle_target




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

    targets = BuildTargets()
    
    for path in args:
        handle_target(path, config, targets)
    
    if config.dry_run:
        print(targets.get_json_str())

if __name__ == "__main__":
    main()
