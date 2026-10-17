"""Math rendering and the shared npm package lookup policy."""

import hashlib
import html
import re
import sys
from pathlib import Path

from .config import PACKAGE
from .workers import Worker

CDN = "https://cdn.jsdelivr.net/npm/"
VERSION = "4.1.3"


def npm_root(root):
    roots = (root, *root.parents, PACKAGE.parent.parent, Path(getattr(sys, "_MEIPASS", PACKAGE)))
    for base in roots:
        candidate = base / "node_modules"
        if (candidate / "mathjax/package.json").is_file():
            return candidate
    raise OSError("MathJax packages not found; run npm install in the notes directory or a parent")


def multiline(tex):
    return "\\\\" in tex or bool(re.search(r"\\begin\{(?:align|gather|split|multline)", tex))


def static_math(tex, display, backend):
    from latex2mathml.converter import convert

    normalized = re.sub(r"\\(begin|end)\{aligned\}", r"\\\1{align*}", tex)
    markup = convert(normalized, display="block" if display else "inline")
    if backend == "mathml":
        scale = 1.12
        if display and not multiline(tex):
            if re.search(r"\\(?:int|iint|iiint|oint|sum|prod)(?![A-Za-z])", tex) and (
                "_" in tex or "^" in tex
            ):
                scale = 1.45
            elif len(re.sub(r"\s+", "", tex)) > 140:
                scale = 1.18
        return markup.replace(
            "<math ", f'<math class="md2html-mathml" style="--md2html-mathml-display-scale:{scale}" ', 1
        )
    import ziamath

    svg = ziamath.Math(markup).svg()
    prefix = "md2html-math-" + hashlib.sha1((tex + str(display)).encode()).hexdigest()[:10]
    for identifier in set(re.findall(r'\bid="([^"]+)"', svg)):
        svg = svg.replace(f'id="{identifier}"', f'id="{prefix}-{identifier}"')
        svg = svg.replace(f'href="#{identifier}"', f'href="#{prefix}-{identifier}"')
    box = re.search(r'viewBox="([^"]+)"', svg)
    _, y, _, height = map(float, box[1].split()) if box else (0, 0, 0, 0)
    depth = max(0, min(1, (y + height) / height)) if height else 0.15
    inline_height = max(1.05, min(1.7, height * 0.049)) if height else 1.15
    display_height = max(1, height * (0.82 if multiline(tex) else 0.72) / 16)
    style = (
        f"--md2html-math-svg-depth:{depth:.4f};--md2html-math-svg-inline-height:{inline_height:.4f}em;"
        f"--md2html-math-svg-inline-align:{-inline_height * depth:.4f}em;"
        f"--md2html-math-svg-display-height:{display_height:.4f}em"
    )
    svg = svg.replace('fill="black"', 'fill="currentColor"').replace(
        'stroke="black"', 'stroke="currentColor"'
    )
    return svg.replace(
        "<svg ", f'<svg class="md2html-math-svg-image" fill="currentColor" style="{style}" ', 1
    )


class Math:
    def __init__(self, options):
        self.options = options
        self.worker = None
        self.cache = {}
        self.css = ""

    def close(self):
        if self.worker:
            self.worker.close()

    def render(self, tex, display, document):
        backend = self.options.math
        document.features.add("math")
        delimiter = "$$" if display else "$"
        raw = delimiter + tex + delimiter
        if backend in {"raw", "mathjax"}:
            markup = html.escape(raw)
        else:
            try:
                key = (tex, display)
                if key not in self.cache:
                    if backend == "mathjax-chtml":
                        if self.worker is None:
                            self.worker = Worker(
                                ["node", str(PACKAGE / "scripts/chtml.mjs"), str(npm_root(self.options.root))]
                            )
                        result = self.worker.request(tex=tex, display=display)
                        self.css = re.sub(r"^<style[^>]*>|</style>$", "", result["css"])
                        self.cache[key] = result["html"]
                    else:
                        self.cache[key] = static_math(tex, display, backend)
                rendered = self.cache[key]
                if "data-mjx-error" in rendered:
                    document.warn(f"could not render TeX: {tex}")
                document.fonts.add("zero")
                document.fonts.update(name.lower() for name in re.findall(r"\bTEX-([A-Z0-9]+)\b", rendered))
                if "mjx-break" in rendered:
                    document.fonts.add("brk")
                document.features.add("math_copy")

                def accessible(match):
                    tag = match[0]
                    if 'class="' in tag:
                        tag = tag.replace('class="', 'class="math-rendered ', 1)
                    else:
                        tag = tag[:-1] + ' class="math-rendered">'
                    return tag[:-1] + ' aria-hidden="true">'

                rendered = re.sub(r"^<[^>]+>", accessible, rendered, count=1)
                markup = f'<span class="math-copy-source">{html.escape(raw)}</span>{rendered}'
            except (OSError, FileNotFoundError):
                raise
            except Exception as error:
                document.warn(f"could not render TeX: {error}")
                markup = html.escape(raw)
        tag = "div" if display else "span"
        mode = "display" if display else "inline"
        return f'<{tag} class="math {mode}-math math-{backend}">{markup}</{tag}>'
