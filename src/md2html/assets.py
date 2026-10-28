"""Page-specific asset references with one output owner for the whole build."""

import base64
import html
import json
import mimetypes
import re
from html.parser import HTMLParser
from itertools import accumulate
from pathlib import Path

import rcssmin

from .config import PACKAGE, values
from .math import CDN, VERSION, npm_root


def data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def relocate(text, resolve):
    """Rewrite asset attributes without reserializing HTML or touching comments/scripts."""
    result, position = [], 0
    offsets = [0, *accumulate(len(line) for line in text.splitlines(keepends=True))]

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            nonlocal position
            original = self.get_starttag_text()

            def attribute(match):
                name, value = match[1].lower(), html.unescape(match[3] if match[2] else match[4])
                if name == "srcset" and "data:" not in value:
                    candidates = [candidate.strip().split(maxsplit=1) for candidate in value.split(",")]
                    value = ", ".join(
                        " ".join([resolve(parts[0]), *parts[1:]]) for parts in candidates if parts
                    )
                elif name != "srcset":
                    value = resolve(value)
                return match[1] + '="' + html.escape(value, quote=True) + '"'

            rewritten = re.sub(
                r"(?<![\w:-])(src|href|poster|data|srcset)\s*=\s*(?:([\"'])(.*?)\2|([^\s>]+))",
                attribute,
                original,
                flags=re.I | re.S,
            )
            line, column = self.getpos()
            offset = offsets[line - 1] + column
            result.extend([text[position:offset], rewritten])
            position = offset + len(original)

    Links(convert_charrefs=False).feed(text)
    result.append(text[position:])
    return "".join(result)


def embed_css(build, path, stack=()):
    path = path.resolve()
    build.dependencies.add(path)
    if path in stack:
        raise ValueError(f"CSS import cycle: {path}")
    text = path.read_text()

    def imported(match):
        name = (match[1] or match[2]).strip(" \"'")
        if re.match(r"[\w+.-]+:|[/#]", name):
            return match[0]
        included = embed_css(build, path.parent / name, (*stack, path))
        media = match[3].strip()
        return "@media " + media + " {" + included + "}" if media else included

    def resource(match):
        name = match[1].strip(" \"'")
        if re.match(r"[\w+.-]+:|[/#]", name):
            return match[0]
        source = (path.parent / name).resolve()
        build.dependencies.add(source)
        return f'url("{data_url(source)}")' if source.is_file() else match[0]

    text = re.sub(r"@import\s+(?:url\(\s*([^)]+)\)|([\"'][^\"']+[\"']))\s*([^;]*);", imported, text)
    return re.sub(r"url\(([^)]+)\)", resource, text)


def finish_highlighting(build, document, body):
    placeholder = document.html.prefix + "CSS"
    if placeholder not in body:
        return body
    # Generate once, after code in layouts and includes is available.
    css = build.highlighter.css_for(body)
    if build.options.minify_css:
        css = rcssmin.cssmin(css)
    return body.replace(placeholder, css)


def context(build, page, document, template):
    options = build.options
    directory = build.output_root / "assets" if options.assets == "shared" else page.target.parent
    result = {
        "css": "",
        "math_css": "",
        "stylesheets": [],
        "page_stylesheets": [],
        "math_stylesheets": [],
        "inline_stylesheets": [],
        "font_preloads": [],
    }
    result.update(
        {
            "has_" + feature: feature in document.features
            for feature in ("code", "math", "toc", "image", "warning", "footnote", "alert")
        }
    )
    result["has_images"] = result["has_image"]
    result["has_warnings"] = result["has_warning"]
    result["uses_svg_math"] = "math" in document.features and options.math == "svg"
    result["jekyll_compatibility"] = options.output_mode == "jekyll"
    result.update(
        {
            "uses_" + backend.replace("-", "_"): "math" in document.features and options.math == backend
            for backend in ("mathjax-chtml", "mathjax", "svg", "mathml", "raw")
        }
    )
    css_paths = options.css
    if css_paths is None:
        companion = template.with_suffix(".css") if template else None
        if companion:
            build.dependencies.add(companion)
        css_paths = (
            [companion]
            if companion and companion.exists()
            else [
                PACKAGE
                / "assets"
                / ("barebones.css" if template and template.name == "barebones.html" else "page-base.css")
            ]
        )

    def sheet(css, name, field="css", owner=None):
        if options.minify_css:
            css = rcssmin.cssmin(css)
        if options.assets == "shared":
            key = {"css": "page_stylesheets", "math_css": "math_stylesheets", "author": "stylesheets"}[field]
            target = directory / (name + ".css")
            build.write(target, css, owner or "renderer " + name)
            result[key].append(build.url(target, page.target.parent))
        elif field == "author":
            result["inline_stylesheets"].append(css)
        else:
            result[field] += css + "\n"

    def authored(name, field):
        path = build.lookup(name, page)
        if path.is_relative_to(PACKAGE / "assets"):
            label = path.stem.removeprefix("page-")
        else:
            relative = (
                path.relative_to(build.source_root)
                if path.is_relative_to(build.source_root)
                else Path(path.name)
            )
            label = "style-" + "-".join(relative.with_suffix("").parts)
        css = embed_css(build, path) if options.assets == "standalone" else path.read_text()
        sheet(css, label, field, str(path))

    for name in dict.fromkeys([*values(css_paths), *values(page.data.get("css"))]):
        authored(name, "css")
    if page.data.get("feature_css", options.feature_css):
        for feature in ("code", "math", "toc", "image", "warning", "footnote", "alert"):
            if feature in document.features:
                path = PACKAGE / "assets" / f"feature-{feature}.css"
                sheet(path.read_text(), feature)
        if "code" in document.features:
            if options.assets == "shared":
                sheet(build.highlighter.css, "highlight")
            else:
                result["css"] += document.html.prefix + "CSS\n"
    for name in dict.fromkeys([*options.stylesheets, *values(page.data.get("stylesheets"))]):
        if re.match(r"[\w+.-]+:|//", name):
            result["stylesheets"].append(name)
        else:
            try:
                authored(name, "author")
            except FileNotFoundError:
                result["stylesheets"].append(name)
    if "math" in document.features and options.math == "mathjax-chtml":
        root = npm_root(build.source_root, options.root) / "@mathjax/mathjax-tex-font/chtml/woff2"
        fonts = document.fonts
        if options.assets == "shared":
            fonts = {p.stem.removeprefix("mjx-tex-") for p in root.glob("*.woff2")}
        families = {"MJX-BRK" if font == "brk" else "MJX-TEX-" + font.upper() for font in fonts}

        def font_face(match):
            family = re.search(r'font-family:\s*["\']?([^;"\'\s]+)', match[0])
            return match[0] if family and family[1] in families and options.math_fonts != "none" else ""

        styles = build.math.stylesheet()
        css = re.sub(r"@font-face[^{}]*\{[^}]*\}", font_face, styles["base"] or styles["css"])
        delivery = options.math_fonts
        if delivery == "auto":
            delivery = {"standalone": "inline", "shared": "local", "cdn": "remote"}[options.assets]

        def font_url(match):
            filename = match[1]
            if delivery == "inline":
                url = data_url(root / filename)
            elif delivery == "remote":
                url = f"{CDN}@mathjax/mathjax-tex-font@{VERSION}/chtml/woff2/{filename}"
            else:
                target = build.output_root / "assets/mathjax/woff2" / filename
                build.copy(root / filename, target)
                url = build.url(target, directory)
                if filename.removeprefix("mjx-tex-").removesuffix(".woff2") in document.fonts:
                    result["font_preloads"].append(build.url(target, page.target.parent))
            return f'url("{url}")'

        sheet(
            re.sub(r'url\(["\']?mathjax/woff2/([^"\')]+)["\']?\)', font_url, css), "mathjax-chtml", "math_css"
        )
        if styles["base"]:
            # Glyph metrics belong to the rendered page; they must survive independent rebuilds.
            result["math_css"] = rcssmin.cssmin(styles["css"]) if options.minify_css else styles["css"]

    if "math" in document.features and options.math == "mathjax":
        config = {"tex": {"inlineMath": [["$", "$"]], "displayMath": [["$$", "$$"]], "processEscapes": True}}
        result["mathjax_src"] = f"{CDN}mathjax@{VERSION}/tex-mml-chtml.js"
        if options.assets == "shared":
            npm = npm_root(build.source_root, options.root)
            target = build.output_root / "assets/mathjax.js"
            if target.resolve() not in build.copied:
                build.copy(npm / "mathjax/tex-mml-chtml.js", target)
                for origin, destination in (
                    (npm / "@mathjax/mathjax-newcm-font/chtml", target.parent / "mathjax-newcm-font/chtml"),
                    (npm / "mathjax/sre", target.parent / "sre"),
                ):
                    for source in origin.rglob("*"):
                        if source.is_file():
                            build.copy(source, destination / source.relative_to(origin))
            config.update(
                loader={"paths": {"fonts": build.url(target.parent, page.target.parent)}},
                output={"fontPath": "[fonts]/%%FONT%%-font"},
            )
            result["mathjax_src"] = build.url(target, page.target.parent)
        result["mathjax_config"] = "window.MathJax=" + json.dumps(config) + ";"
    return result
