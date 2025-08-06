#!/usr/bin/env python3
"""
Markdown preprocessing tests for md2html
Tests dependency parsing, frontmatter parsing, and custom directives
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

from .testsuite import TestContext, run_command

def parse_build_targets(output: str) -> Dict:
    """Parse the JSON build targets output"""
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None

def get_dependencies(build_targets: Dict, filename: str) -> List[Dict[str, Any]]:
    """Get dependencies for a specific file from build targets"""
    nodes = build_targets.get('nodes', [])
    for node in nodes:
        if Path(node['input']).name == filename:
            return node.get('dependencies', [])
    return []

def get_dependency_names(build_targets: Dict, filename: str) -> Set[str]:
    """Get just the dependency names for a specific file (for backwards compatibility)"""
    dependencies = get_dependencies(build_targets, filename)
    return {dep['name'] for dep in dependencies}

def get_frontmatter(build_targets: Dict, filename: str) -> Dict:
    """Get frontmatter for a specific file from build targets"""
    nodes = build_targets.get('nodes', [])
    for node in nodes:
        if Path(node['input']).name == filename:
            return node.get('frontmatter', {})
    return {}

def create_preprocessing_test_dirs(test_root: Path, ctx: TestContext):
    """Create test directories for preprocessing tests"""
    preprocessing_dir = test_root / 'preprocessing'
    if preprocessing_dir.exists() and not ctx.keep_files:
        shutil.rmtree(preprocessing_dir)
    preprocessing_dir.mkdir(parents=True, exist_ok=True)
    return preprocessing_dir

def test_basic_dependencies(ctx: TestContext, test_dir: Path) -> bool:
    """Test basic @include and @src dependency parsing"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_basic.md"
    test_md.write_text("""# Test File

@include(other.md)
@src(hello.cpp, lang=cpp)

Some content here.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    dependencies = get_dependency_names(build_targets, test_md.name)
    expected = {"other.md", "hello.cpp"}
    
    if dependencies == expected:
        ctx.print(f"✓ Test {ctx.current_test}: Basic dependencies parsed correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected {expected}, got {dependencies}", 'fail')
        return False

def test_frontmatter_parsing(ctx: TestContext, test_dir: Path) -> bool:
    """Test YAML frontmatter parsing"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_frontmatter.md"
    test_md.write_text("""---
title: Test Document
template: custom.html
author: Test Author
---

# Test Content

Some markdown content.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    frontmatter = get_frontmatter(build_targets, test_md.name)
    expected = {
        "title": "Test Document",
        "template": "custom.html",
        "author": "Test Author"
    }
    
    if frontmatter == expected:
        ctx.print(f"✓ Test {ctx.current_test}: Frontmatter parsed correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected {expected}, got {frontmatter}", 'fail')
        return False

def test_complex_directives(ctx: TestContext, test_dir: Path) -> bool:
    """Test complex directives with options"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_complex.md"
    test_md.write_text("""# Complex Test

@include(data.json, format=json, pretty=true)
@src(main.cpp, lang=cpp, lines=1-50)
@include(../other/file.md)

Content here.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    dependencies = get_dependency_names(build_targets, test_md.name)
    expected = {"data.json", "main.cpp", "../other/file.md"}
    
    # Also check that options are preserved
    full_dependencies = get_dependencies(build_targets, test_md.name)
    
    # Find the data.json dependency and check its options
    data_dep = next((dep for dep in full_dependencies if dep['name'] == 'data.json'), None)
    expected_options = {"format=json", "pretty=True"}
    
    if dependencies == expected and data_dep and set(data_dep['options']) == expected_options:
        ctx.print(f"✓ Test {ctx.current_test}: Complex directives with options parsed correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected {expected}, got {dependencies}. Data options: {data_dep['options'] if data_dep else 'None'}", 'fail')
        return False

def test_no_dependencies(ctx: TestContext, test_dir: Path) -> bool:
    """Test markdown file with no dependencies"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_simple.md"
    test_md.write_text("""---
title: Simple Document
---

# Simple Test

Just regular markdown content with no directives.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    dependencies = get_dependency_names(build_targets, test_md.name)
    frontmatter = get_frontmatter(build_targets, test_md.name)
    
    if len(dependencies) == 0 and frontmatter.get("title") == "Simple Document":
        ctx.print(f"✓ Test {ctx.current_test}: No dependencies and frontmatter parsed correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected no dependencies, got {dependencies}, frontmatter: {frontmatter}", 'fail')
        return False

def test_malformed_directives(ctx: TestContext, test_dir: Path) -> bool:
    """Test handling of malformed directives"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_malformed.md"
    test_md.write_text("""# Malformed Test

@include(good.md)
@invalid_directive(bad.md)
@src()
@include(another.md, valid=option)

Content here.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    dependencies = get_dependency_names(build_targets, test_md.name)
    # Should only parse valid directives
    expected = {"good.md", "another.md"}
    
    if dependencies == expected:
        ctx.print(f"✓ Test {ctx.current_test}: Malformed directives handled correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected {expected}, got {dependencies}", 'fail')
        return False

def test_relative_paths(ctx: TestContext, test_dir: Path) -> bool:
    """Test that relative paths are preserved in output"""
    ctx.current_test += 1
    
    test_md = test_dir / "test_paths.md"
    test_md.write_text("""# Relative Paths

@include(./local.md)
@src(../parent.cpp)
@include(subdir/nested.md)

Content here.
""")
    
    success, stdout, stderr = run_command(['--dry-run', str(test_md)])
    
    if not success:
        ctx.print(f"✗ Test {ctx.current_test}: Command failed: {stderr}", 'fail')
        return False
    
    build_targets = parse_build_targets(stdout)
    if not build_targets:
        ctx.print(f"✗ Test {ctx.current_test}: Failed to parse build targets JSON", 'fail')
        return False
    
    dependencies = get_dependency_names(build_targets, test_md.name)
    expected = {"./local.md", "../parent.cpp", "subdir/nested.md"}
    
    # Check that paths are relative (no absolute paths)
    all_relative = all(not Path(dep).is_absolute() for dep in dependencies)
    
    if dependencies == expected and all_relative:
        ctx.print(f"✓ Test {ctx.current_test}: Relative paths preserved correctly", 'normal')
        return True
    else:
        ctx.print(f"✗ Test {ctx.current_test}: Expected {expected}, got {dependencies}, all_relative: {all_relative}", 'fail')
        return False

def run_preprocessing_tests(ctx: TestContext) -> Tuple[int, int]:
    """Run all preprocessing tests and return (passed, failed) counts"""
    
    # Get project root and create test directories
    project_root = Path(__file__).parent.parent
    test_root = project_root / 'tests'
    test_dir = create_preprocessing_test_dirs(test_root, ctx)
    
    tests = [
        test_basic_dependencies,
        test_frontmatter_parsing,
        test_complex_directives,
        test_no_dependencies,
        test_malformed_directives,
        test_relative_paths,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        if test_func(ctx, test_dir):
            passed += 1
        else:
            failed += 1
    
    # Cleanup - only remove our preprocessing directory, not entire tests dir
    # (filepaths tests will clean up the entire tests dir if they run after us)
    if not ctx.keep_files:
        if test_dir.exists():
            shutil.rmtree(test_dir)
            ctx.print(f"Preprocessing test files cleaned up", level='verbose')
    else:
        ctx.print(f"Preprocessing test files preserved in: {test_dir}", level='verbose')
    
    return passed, failed