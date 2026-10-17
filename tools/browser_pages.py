"""Build the four example pages used by tests/browser.cjs."""

import sys
from pathlib import Path

from md2html.config import resolve
from md2html.project import Build

source = Path(__file__).resolve().parents[1] / "examples/notes.md"
output = Path(sys.argv[1]).resolve()
for backend in ("mathjax-chtml", "mathjax", "svg", "mathml"):
    build = Build(
        resolve(
            {
                "input": [str(source)],
                "output": str(output / (backend + ".html")),
                "math": backend,
                "assets": "shared",
                "execute": True,
            }
        )
    )
    try:
        build.build()
        if build.warnings:
            raise RuntimeError("\n".join(build.warnings))
    finally:
        build.close()
