"""Inline highlighting stays small without losing styles across pages or themes."""

import re

import pytest
import rcssmin
from bs4 import BeautifulSoup

from md2html.config import Options
from md2html.highlight import Highlighter, HighlightUsage


def stylesheet(path):
    doc = BeautifulSoup(path.read_text(), "html.parser")
    return "\n".join(style.text for style in doc.select("style"))


@pytest.mark.parametrize("backend,style", [("pygments", None), ("pygments", "monokai"), ("rouge", None)])
def test_subset_preserves_every_matching_rule(request, backend, style):
    if backend == "rouge":
        request.getfixturevalue("rouge")
    highlighter = Highlighter(Options(highlighter=backend, highlighter_style=style))
    try:
        body = highlighter.code('int main() { return 42; } // comment\n"text"', "cpp")
        body += highlighter.code('f[x_] := Module[{local}, Sin[x] + 42]; "text"', "wl")
        doc = BeautifulSoup(body, "html.parser")
        usage = HighlightUsage(body)
        for original in (highlighter.light_css, highlighter.dark_css):
            subset = rcssmin.cssmin(usage.prune(original))
            rules = re.findall(r"([^{}]+)\{([^{}]*)\}", rcssmin.cssmin(original))
            for selectors, declarations in rules:
                for selector in selectors.split(","):
                    if doc.select(selector):
                        assert any(
                            selector in kept.split(",") and declarations == value
                            for kept, value in re.findall(r"([^{}]+)\{([^{}]*)\}", subset)
                        ), selector
    finally:
        highlighter.close()


def test_unknown_selectors_are_preserved():
    css = '.codehilite[data-note="a,b"] .unused:hover { color: red; }'
    assert HighlightUsage('<div class="codehilite"></div>').prune(css) == css


@pytest.mark.parametrize("backend", ["pygments", "rouge"])
@pytest.mark.parametrize(
    "mode,assets", [("pages", "standalone"), ("pages", "cdn"), ("site", "cdn"), ("jekyll", "cdn")]
)
def test_inline_styles_are_page_specific_and_refresh(cli, put, tmp_path, request, backend, mode, assets):
    if backend == "rouge":
        request.getfixturevalue("rouge")
    put("wolfram.md", '---\n---\n```wl\nSin[x] + "text"\n```\n')
    put("plain.md", "---\n---\n```cpp\nint value;\n```\n")
    args = (
        "wolfram.md",
        "plain.md",
        "--output-mode",
        mode,
        "--assets",
        assets,
        "--math",
        "raw",
        "--highlighter",
        backend,
        "-o",
        "html",
    )
    cli(*args)
    plain = tmp_path / "html/plain.html"
    other = tmp_path / "html/wolfram.html"
    css = stylesheet(plain)
    assert not re.search(r"\.s\s*\{", css)
    if backend == "pygments":
        assert '.codehilite[data-language="wl"]' not in css
        assert plain.stat().st_size < 30000
        assert '.codehilite[data-language="wl"]' in stylesheet(other)
    assert 'html[data-theme="light"]' in css and 'html[data-theme="dark"]' in css
    before = other.stat().st_mtime_ns
    put("plain.md", '---\n---\n```cpp\nconst char *value = "new token";\n```\n')
    cli(*args)
    assert re.search(r"\.s\s*\{", stylesheet(plain))
    assert other.stat().st_mtime_ns == before
    assert "Built 0 pages" in cli(*args).stdout


@pytest.mark.parametrize("mode", ["pages", "site", "jekyll"])
def test_shared_styles_survive_partial_rebuilds(cli, put, tmp_path, mode):
    put("a.md", "---\n---\n```cpp\nint value;\n```\n")
    put("b.md", '---\n---\n```wl\nSin[x] + "text"\n```\n')
    args = ("a.md", "b.md", "--output-mode", mode, "--assets", "shared", "--math", "raw", "-o", "html")
    cli(*args)
    sheet = tmp_path / "html/assets/highlight.css"
    original = sheet.read_bytes()
    other = tmp_path / "html/b.html"
    before = other.stat().st_mtime_ns
    put("a.md", "---\n---\n```cpp\nint changed;\n```\n")
    cli(*args)
    assert sheet.read_bytes() == original
    assert other.stat().st_mtime_ns == before
    sheet.unlink()
    cli(*args)
    assert sheet.read_bytes() == original


@pytest.mark.parametrize("minify", [True, False])
def test_template_tokens_and_authored_css_are_preserved(cli, put, tmp_path, minify):
    put("a.md", "```cpp\nint value;\n```\n")
    authored = ".codehilite .unused { color: teal; }"
    put(
        "_templates/custom.html",
        "<style>{{ md2html.css }}</style><style>" + authored + "</style>{{ content }}"
        '<div class="codehilite" data-language="wl"><span class="nb">Sin</span></div>',
    )
    cli("a.md", "--math", "raw", "--template", "custom.html", *(() if minify else ("--no-minify-css",)))
    css = stylesheet(tmp_path / "a.html")
    assert authored in css
    assert '.codehilite[data-language="wl"] .nb' in css


def test_markdown_export_does_not_inject_styles(cli, put, tmp_path):
    put("a.md", "```cpp\nint value;\n```\n")
    cli("a.md", "--jekyll-markdown", "-o", "export", "--math", "raw")
    output = (tmp_path / "export/a.md").read_text()
    assert "int value;" in output and "<style" not in output
    assert not (tmp_path / "export/assets/highlight.css").exists()
