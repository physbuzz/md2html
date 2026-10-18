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


def npm_root(root, config_root=None):
    config_paths = (config_root, *config_root.parents) if config_root else ()
    roots = (
        root,
        *root.parents,
        *config_paths,
        PACKAGE.parent.parent,
        Path(getattr(sys, "_MEIPASS", PACKAGE)),
    )
    for base in roots:
        candidate = base / "node_modules"
        if (candidate / "mathjax/package.json").is_file():
            return candidate
    raise OSError(
        "MathJax packages not found; in the notes directory or a parent, run "
        f"npm install mathjax@{VERSION} @mathjax/mathjax-tex-font@{VERSION} "
        f"@mathjax/mathjax-newcm-font@{VERSION}"
    )


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

    def stylesheet(self):
        return self.worker.request(stylesheet=True)

    def close(self):
        if self.worker:
            self.worker.close()

    def render(self, tex, display, document):
        backend = self.options.math
        document.features.add("math")
        delimiter = "$$" if display else "$"
        raw = tex if tex.startswith(r"\begin{") else delimiter + tex + delimiter
        if backend in {"raw", "mathjax"}:
            markup = html.escape(raw)
        else:
            try:
                key = (tex, display)
                if key not in self.cache:
                    if backend == "mathjax-chtml":
                        if self.worker is None:
                            self.worker = Worker(
                                [
                                    "node",
                                    str(PACKAGE / "scripts/chtml.mjs"),
                                    str(npm_root(document.build.source_root, self.options.root)),
                                    self.options.assets,
                                ]
                            )
                        result = self.worker.request(tex=tex, display=display)
                        self.cache[key] = result["html"]
                    else:
                        self.cache[key] = static_math(tex, display, backend)
                rendered = self.cache[key]
                if "data-mjx-error" in rendered:
                    message = re.search(r'data-mjx-error="([^"]+)"', rendered)
                    detail = html.unescape(message[1]) if message else "invalid expression"
                    preview = " ".join(tex.split())[:160]
                    document.warn(f"could not render TeX ({detail}): {preview}")
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
        # Browser MathJax must leave static equations and their copyable TeX alone.
        ignore = " tex2jax_ignore mathjax_ignore" if backend not in {"raw", "mathjax"} else ""
        return f'<{tag} class="math {mode}-math math-{backend}{ignore}">{markup}</{tag}>'
