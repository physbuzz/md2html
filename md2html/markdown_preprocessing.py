"""
Markdown preprocessing functionality for custom syntax.

Handles:
- YAML front matter parsing for template configuration
- @include(file.md, opts) directive parsing
- @src(file.cpp, opts) directive parsing
- Dependency extraction for build graph construction
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
from pathlib import Path
import re
import yaml
import frontmatter


@dataclass
class MarkdownDirective:
    """Represents a parsed @include or @src directive"""
    directive_type: str  # "include" or "src"
    file_path: str
    options: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0


@dataclass
class MarkdownMetadata:
    """Contains parsed metadata from a markdown file"""
    yaml_frontmatter: Dict[str, Any] = field(default_factory=dict)
    template: Optional[str] = None
    directives: List[MarkdownDirective] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)


def parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML front matter from markdown content.
    
    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)
    """
    try:
        post = frontmatter.loads(content)
        return post.metadata, post.content
    except yaml.YAMLError:
        # If YAML parsing fails, return empty metadata and original content
        return {}, content


def parse_directive_line(line: str, line_number: int) -> Optional[MarkdownDirective]:
    """
    Parse a single line for @include or @src directive.
    
    Expected formats:
    - @include(file.md)
    - @include(file.md, key=value, key2=value2)
    - @src(file.cpp)
    - @src(file.cpp, lang=cpp, lines=1-10)
    
    Returns:
        MarkdownDirective if line contains a valid directive, None otherwise
    """
    # Regex to match @directive(file, optional_args)
    pattern = r'@(include|src)\s*\(\s*([^,)]+)(?:\s*,\s*(.+))?\s*\)'
    match = re.search(pattern, line.strip())
    
    if not match:
        return None
    
    directive_type = match.group(1)
    file_path = match.group(2).strip().strip('"\'')
    options_str = match.group(3)
    
    options = {}
    if options_str:
        # Parse key=value pairs
        # Simple parsing - could be enhanced for more complex syntax
        for option in options_str.split(','):
            option = option.strip()
            if '=' in option:
                key, value = option.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                # Try to convert to appropriate type
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.isdigit():
                    value = int(value)
                options[key] = value
    
    return MarkdownDirective(
        directive_type=directive_type,
        file_path=file_path,
        options=options,
        line_number=line_number
    )


def parse_markdown_directives(content: str) -> List[MarkdownDirective]:
    """
    Parse all @include and @src directives from markdown content.
    
    Returns:
        List of MarkdownDirective objects found in the content
    """
    directives = []
    lines = content.split('\n')
    
    for line_number, line in enumerate(lines, 1):
        directive = parse_directive_line(line, line_number)
        if directive:
            directives.append(directive)
    
    return directives


def extract_dependencies_from_directives(directives: List[MarkdownDirective], base_path: Path) -> List[Dict[str, Any]]:
    """
    Extract file dependencies from parsed directives.
    
    Args:
        directives: List of parsed directives
        base_path: Base path to resolve relative file paths against
        
    Returns:
        List of dependency dictionaries with name and options
    """
    dependencies = []
    
    for directive in directives:
        # Keep relative paths relative, only resolve absolute paths
        if Path(directive.file_path).is_absolute():
            dep_path = directive.file_path
        else:
            dep_path = directive.file_path
        
        # Create options list from the directive's parsed options
        options = []
        for key, value in directive.options.items():
            options.append(f"{key}={value}")
        
        dependencies.append({
            "name": dep_path,
            "options": options
        })
    
    return dependencies


def parse_markdown_metadata(markdown_file: Path) -> MarkdownMetadata:
    """
    Parse a markdown file and extract all metadata including:
    - YAML front matter
    - Template specification from front matter
    - @include and @src directives
    - File dependencies
    
    Args:
        markdown_file: Path to the markdown file to parse
        
    Returns:
        MarkdownMetadata object containing all parsed information
    """
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")
    
    content = markdown_file.read_text(encoding='utf-8')
    
    # Parse YAML front matter
    frontmatter_data, content_without_frontmatter = parse_yaml_frontmatter(content)
    
    # Extract template from front matter
    template = frontmatter_data.get('template')
    
    # Parse directives from the content (including front matter)
    directives = parse_markdown_directives(content)
    
    # Extract dependencies
    base_path = markdown_file.parent
    dependencies = extract_dependencies_from_directives(directives, base_path)
    
    return MarkdownMetadata(
        yaml_frontmatter=frontmatter_data,
        template=template,
        directives=directives,
        dependencies=dependencies
    )


def get_markdown_dependencies(markdown_file: Path) -> List[Dict[str, Any]]:
    """
    Quick function to get just the dependencies from a markdown file.
    
    Args:
        markdown_file: Path to the markdown file
        
    Returns:
        List of dependency dictionaries with name and options
    """
    metadata = parse_markdown_metadata(markdown_file)
    return metadata.dependencies