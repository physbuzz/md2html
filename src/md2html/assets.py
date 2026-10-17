"""Page-specific asset references with one output owner for the whole build."""

import base64
import hashlib
import json
import mimetypes
import re
from pathlib import Path

import rcssmin

from .config import PACKAGE, values
from .math import CDN, VERSION, npm_root


def data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def css_file(build, path, page, stack=()):
    path = path.resolve()
    build.dependencies.add(path)
    if path in stack:
        raise ValueError(f"CSS import cycle: {path}")
    text = path.read_text()

    def imported(match):
        name = (match[1] or match[2]).strip(" \"'")
        if re.match(r"[\w+.-]+:|//", name):
            return match[0]
        included = css_file(build, path.parent / name, page, (*stack, path))
        media = match[3].strip()
        return "@media " + media + " {" + included + "}" if media else included

    text = re.sub(r"@import\s+(?:url\(\s*([^)]+)\)|([\"'][^\"']+[\"']))\s*([^;]*);", imported, text)

    def rewrite(match):
        name = match[1].strip(" \"'")
        if re.match(r"[\w+.-]+:|[/#]", name):
            return match[0]
        source = (path.parent / name).resolve()
        build.dependencies.add(source)
        if not source.exists():
            return match[0]
        url = data_url(source) if build.options.assets == "standalone" else build.asset_link(source, page)
        return f'url("{url}")'

    return re.sub(r"url\(([^)]+)\)", rewrite, text)


def context(build, page, document, template):
    options = build.options
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
            for feature in ("code", "math", "math_copy", "toc", "image", "warning")
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
    css_paths = page.data.get("css", options.css)
    if css_paths is None:
        companion = template.with_suffix(".css") if template else None
        css_paths = (
            [companion]
            if companion and companion.exists()
            else [
                PACKAGE
                / "assets"
                / ("barebones.css" if template and template.name == "barebones.html" else "page-base.css")
            ]
        )
    css = []
    for name in values(css_paths):
        path = Path(name)
        if not path.is_absolute():
            path = page.source.parent / path
        css.append(css_file(build, path, page))
    if options.feature_css:
        css.extend(
            (PACKAGE / "assets" / f"feature-{feature}.css").read_text()
            for feature in ("code", "math", "toc", "image", "warning")
            if feature in document.features
        )
        if "code" in document.features:
            css.append(build.highlighter.css)
    result["css"] = "\n".join(css)
    for name in values(page.data.get("stylesheets", options.stylesheets)):
        if re.match(r"[\w+.-]+:|//", name):
            result["stylesheets"].append(name)
        else:
            source = (page.source.parent / name).resolve()
            if not source.exists():
                source = (options.root / name).resolve()
            if source.exists():
                css = css_file(build, source, page)
                if options.assets == "standalone":
                    result["inline_stylesheets"].append(css)
                else:
                    result["stylesheets"].append(shared_css(build, page, css, "author"))
            else:
                result["stylesheets"].append(name)
    if "math" in document.features and options.math == "mathjax-chtml":
        root = npm_root(build.source_root, options.root) / "@mathjax/mathjax-tex-font/chtml/woff2"
        fonts = document.fonts
        if options.math_fonts == "all":
            fonts = {p.stem.removeprefix("mjx-tex-") for p in root.glob("*.woff2")}
        families = {"MJX-BRK" if font == "brk" else "MJX-TEX-" + font.upper() for font in fonts}

        def font_face(match):
            family = re.search(r'font-family:\s*["\']?([^;"\'\s]+)', match[0])
            return match[0] if family and family[1] in families and options.math_fonts != "none" else ""

        css = re.sub(r"@font-face[^{}]*\{[^}]*\}", font_face, build.math.stylesheet())
        delivery = options.math_fonts
        if delivery in {"auto", "all"}:
            delivery = {"standalone": "inline", "shared": "local", "cdn": "remote"}[options.assets]

        def font_url(match):
            filename = match[1]
            if delivery == "inline":
                url = data_url(root / filename)
            elif delivery == "remote":
                url = f"{CDN}@mathjax/mathjax-tex-font@{VERSION}/chtml/woff2/{filename}"
            else:
                target = build.output_root / "assets/md2html/mathjax/woff2" / filename
                build.copy(root / filename, target)
                url = build.url(target, page)
                if filename.removeprefix("mjx-tex-").removesuffix(".woff2") in document.fonts:
                    result["font_preloads"].append(url)
            return f'url("{url}")'

        result["math_css"] = re.sub(r'url\(["\']?mathjax/woff2/([^"\')]+)["\']?\)', font_url, css)
    if "math" in document.features and options.math == "mathjax":
        config = {"tex": {"inlineMath": [["$", "$"]], "displayMath": [["$$", "$$"]], "processEscapes": True}}
        result["mathjax_src"] = f"{CDN}mathjax@{VERSION}/tex-mml-chtml.js"
        if options.assets == "shared":
            npm = npm_root(build.source_root, options.root)
            target = build.output_root / "assets/md2html/mathjax.js"
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
                loader={"paths": {"fonts": build.url(target.parent, page)}},
                output={"fontPath": "[fonts]/%%FONT%%-font"},
            )
            result["mathjax_src"] = build.url(target, page)
        elif options.assets == "standalone":
            document.warn("browser MathJax uses the CDN with standalone assets")
        result["mathjax_config"] = "window.MathJax=" + json.dumps(config) + ";"
    for key in ("css", "math_css"):
        if options.minify_css:
            result[key] = rcssmin.cssmin(result[key])
        if result[key] and options.assets == "shared":
            url = shared_css(build, page, result[key], key)
            result["math_stylesheets" if key == "math_css" else "page_stylesheets"].append(url)
            result[key] = ""
    return result


def shared_css(build, page, css, name):
    # Asset URLs in a shared sheet are relative to the sheet, not its page.
    css = re.sub(r'url\("([^"#:]+)"\)', lambda m: 'url("' + build.css_url(m[1], page) + '")', css)
    digest = hashlib.sha256(css.encode()).hexdigest()[:12]
    target = build.output_root / f"assets/md2html/{name}-{digest}.css"
    build.write(target, css, "renderer " + digest)
    return build.url(target, page)
