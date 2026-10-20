import json
import shutil
import time
from pathlib import Path
from urllib.parse import unquote

import pytest
from bs4 import BeautifulSoup


def soup(path):
    return BeautifulSoup(path.read_text(), "html.parser")


def test_directives_liquid_code_and_includes(cli, put, tmp_path):
    put(
        "parts/piece.md",
        '# Included\n@src-begin(python, execute) # note\nprint("{{ untouched }}")\n@src-end\n@src(example.py) # note\n',
    )
    put("parts/example.py", 'print("included file")\n')
    put(
        "main.md",
        "---\ntitle: Main\n---\n@toc # contents\n# {{ page.title }}\n@include(parts/piece.md)\n```python\n@src(parts/example.py)\n```\n\n`{{ untouched }}`\n\n```wl\n{{1, 2}, {3, 4}}\n```\n",
    )
    cli("-e", "--math", "raw", "main.md")
    doc = soup(tmp_path / "main.html")
    assert [h.text for h in doc.select("article > h1")] == ["Main", "Included"]
    assert len(doc.select(".code-box")) == 3
    assert "{{ untouched }}" in doc.select_one(".code-output").text
    assert "{{1, 2}, {3, 4}}" in doc.text
    assert doc.select_one('.table-of-contents a[href="#included"]')
    assert "MD2HTML" not in doc.text


def test_code_fences_comments_math_are_protected(cli, put, tmp_path):
    put(
        "a.md",
        "````wl\n```\n{{1,2}} $not math$\n````\n\n<!-- {{bad -->\n<pre>{{raw}}</pre>\n\n    {{indented}}\n\n$\\text{ {{braces}} }$\n",
    )
    cli("--math", "raw", "a.md")
    text = (tmp_path / "a.html").read_text()
    assert "{{1,2}}" in soup(tmp_path / "a.html").text
    assert "{{raw}}" in text and "{{indented}}" in text
    assert "{{braces}}" in text and "<!-- {{bad -->" in text
    assert len(soup(tmp_path / "a.html").select(".math")) == 1


@pytest.mark.parametrize(
    "text", ["@src-end", "@src-begin(py)\nx", "@src-begin(py)\n@src-begin(py)\n@src-end"]
)
def test_unbalanced_blocks_fail(cli, put, text):
    put("bad.md", text)
    cli("bad.md", ok=False)


def test_missing_and_cyclic_includes_warn(cli, put, tmp_path):
    put("a.md", "@include(no.md)\n@include(b.md)\n# Still here\n")
    put("b.md", "@include(a.md)\n")
    result = cli("a.md")
    assert "cycle" in result.stderr
    assert "Still here" in (tmp_path / "a.html").read_text()
    assert len(soup(tmp_path / "a.html").select("aside.warning")) == 2


@pytest.mark.parametrize("text", ["---\n[bad]\n---\ntext", "---\ntitle: [bad\n---\nx", "---\ntitle: x"])
def test_invalid_frontmatter_fails(cli, put, text):
    put("a.md", text)
    cli("a.md", ok=False)


def test_cache_source_only_force_and_noexecute(cli, put, tmp_path):
    code = 'from pathlib import Path\np=Path("counter")\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nprint(n)\n'
    put("counter.py", code)
    put("a.md", "@src(counter.py)\n")
    cli("-e", "a.md")
    cli("-ef", "a.md")
    cli("a.md")
    assert (tmp_path / "counter").read_text() == "1"
    assert "1" in soup(tmp_path / "a.html").select_one(".code-output").text
    cli("-eF", "a.md")
    assert (tmp_path / "counter").read_text() == "2"
    put("counter.py", code + "# changed\n")
    cli("-e", "a.md")
    assert (tmp_path / "counter").read_text() == "3"
    put("a.md", "@src(counter.py, noexecute)\n")
    cli("-e", "a.md")
    assert not soup(tmp_path / "a.html").select(".code-output")
    assert (tmp_path / "counter").read_text() == "3"
    cli("-F", "a.md", ok=False)


@pytest.mark.parametrize("config_args", [(), ("--config", "md2html.json")])
def test_no_execute_overrides_config_and_reuses_output(cli, put, tmp_path, config_args):
    put("md2html.json", json.dumps({"execute": True, "math": "raw"}))
    code = 'from pathlib import Path\nPath("ran").touch()\nprint("saved result")\n'
    put("example.py", code)
    put("a.md", "@src(example.py, execute)\n")
    cli(*config_args, "a.md", "--no-execute")
    assert not (tmp_path / "ran").exists()
    assert not soup(tmp_path / "a.html").select(".code-output")

    cli(*config_args, "a.md")
    assert (tmp_path / "ran").exists()
    (tmp_path / "ran").unlink()
    cli(*config_args, "a.md", "--force", "--no-execute")
    assert "saved result" in soup(tmp_path / "a.html").select_one(".code-output").text
    assert not (tmp_path / "ran").exists()

    put("example.py", code + "# changed source invalidates saved output\n")
    cli(*config_args, "a.md", "-e", "--no-execute")
    assert not (tmp_path / "ran").exists()
    assert not soup(tmp_path / "a.html").select(".code-output")
    cli(*config_args, "a.md", "--no-execute", "-e")
    assert (tmp_path / "ran").exists()


def test_custom_commands_workspaces_and_artifacts(cli, put, tmp_path):
    put("source folder/test.foo", "anything")
    put("page.md", "@src(source folder/test.foo)\n@src-begin(bar, execute)\nbody\n@src-end\n")
    config = {
        "input": "page.md",
        "execute": True,
        "commands": {
            ".foo": 'printf "%s\\n" {source} {builddir} {executable} {slug} > {output}',
            "bar": "cat {source}; pwd; printf artifact > figure.txt",
        },
    }
    put("md2html.json", json.dumps(config))
    cli()
    doc = soup(tmp_path / "page.html")
    output = doc.select(".code-output")
    assert "source folder/test.foo" in output[0].text
    assert ".md2html-cache/page/foo-test-" in output[0].text
    assert "test.md2html-out" in output[0].text
    assert str(tmp_path) in output[1].text
    assert (tmp_path / "figure.txt").read_text() == "artifact"
    config["commands"]["bar"] = "echo should-not-run"
    put("md2html.json", json.dumps(config))
    cli()
    assert "should-not-run" not in soup(tmp_path / "page.html").select(".code-output")[1].text


@pytest.mark.parametrize("mode", ["pages", "jekyll-markdown"])
def test_execution_warning_stays_with_collapsed_snippet(cli, put, tmp_path, mode):
    put("missing.wl", "1 + 1\n")
    put(
        "page.md",
        "@src(missing.wl, collapsed)\n\n"
        "@src-begin(python)\nprint('successful output')\n@src-end\n\n# After snippets\n",
    )
    put(
        "md2html.json",
        json.dumps(
            {
                "commands": {"wl": "md2html-test-missing-wolframscript"},
                "execute": True,
            }
        ),
    )
    result = cli("page.md", "--output-mode", mode, "-o", "rendered")
    assert "md2html-test-missing-wolframscript" in result.stderr
    output = tmp_path / "rendered" / ("page.md" if mode == "jekyll-markdown" else "page.html")
    doc = soup(output)
    boxes = doc.select(".code-box")
    warning = doc.select_one("aside.warning")
    assert len(doc.select("aside.warning")) == 1
    assert warning.parent == boxes[0]
    assert warning.find_parent("details") is None
    assert "md2html-test-missing-wolframscript" in warning.text
    assert not boxes[1].select(".warning")
    assert "successful output" in boxes[1].select_one(".code-output").text


@pytest.mark.parametrize(
    "language,code,expected",
    [
        ("python", 'print("py works")', "py works"),
        ("racket", '#lang racket\n(displayln "racket works")', "racket works"),
        ("javascript", 'console.log("js works")', "js works"),
        ("bash", 'printf "shell works"', "shell works"),
        ("c", '#include <stdio.h>\nint main() { puts("c works"); }', "c works"),
        ("cpp", '#include <iostream>\nint main() { std::cout << "cpp works"; }', "cpp works"),
    ],
)
def test_languages(cli, put, tmp_path, language, code, expected):
    put("a.md", f"@src-begin({language}, execute) # keep includes\n{code}\n@src-end\n")
    cli("-e", "a.md")
    assert expected in soup(tmp_path / "a.html").select_one(".code-output").text
    assert not list(tmp_path.glob("*.md2html-out"))


def test_timeout_stops_descendants_and_retries(cli, put, tmp_path):
    put(
        "late.py",
        "import subprocess, sys, time\nsubprocess.Popen([sys.executable,\"-c\", \"import time,pathlib;time.sleep(1);pathlib.Path('leaked').write_text('bad')\"])\ntime.sleep(10)\n",
    )
    put("a.md", "@src(late.py)\n# Survives\n")
    result = cli("-e", "--timeout", ".15", "a.md")
    assert "timed out" in result.stderr
    assert "timed out" in soup(tmp_path / "a.html").select_one(".code-box > .warning").text
    time.sleep(1.2)
    assert not (tmp_path / "leaked").exists()
    assert not list(tmp_path.rglob(".complete"))
    assert "Survives" in soup(tmp_path / "a.html").text


@pytest.mark.parametrize(
    "backend,marker",
    [
        ("mathjax-chtml", "mjx-container"),
        ("svg", "svg.md2html-math-svg-image"),
        ("mathml", "math.md2html-mathml"),
        ("raw", ".math-raw"),
        ("mathjax", ".math-mathjax"),
    ],
)
def test_math_backends(cli, put, tmp_path, backend, marker):
    put("a.md", "Inline $x^2$ and fraction $\\frac{1}{2}$.\n\n$$\\int_0^1 x^2 dx$$\n")
    cli("--math", backend, "a.md")
    doc = soup(tmp_path / "a.html")
    assert len(doc.select(marker)) == 3
    if backend == "mathjax-chtml":
        assert "data:font/woff2;base64," in str(doc)
        assert not doc.select("script[src]")
    if backend in {"svg", "mathml", "mathjax-chtml"}:
        assert len(doc.select(".math-copy-source")) == 3


@pytest.mark.parametrize("assets", ["standalone", "shared", "cdn"])
@pytest.mark.parametrize("fonts", ["auto", "inline", "local", "remote", "none"])
def test_font_delivery(cli, put, tmp_path, assets, fonts):
    put("a.md", "$x+1$")
    cli("a.md", "-o", "public/a.html", "--assets", assets, "--math-fonts", fonts)
    text = (tmp_path / "public/a.html").read_text()
    doc = soup(tmp_path / "public/a.html")
    for link in doc.select('link[rel="stylesheet"]'):
        text += (tmp_path / "public" / unquote(link["href"])).read_text()
    if fonts == "none":
        assert "@font-face" not in text
    elif fonts == "inline" or fonts == "auto" and assets == "standalone":
        assert "data:font/woff2;base64," in text
    elif fonts == "remote" or fonts == "auto" and assets == "cdn":
        assert "cdn.jsdelivr.net/npm/@mathjax/mathjax-tex-font@4.1.3" in text
    else:
        assert list((tmp_path / "public/assets").rglob("*.woff2"))
        assert doc.select('link[rel="preload"]')


@pytest.mark.parametrize("backend", ["mathjax-chtml", "mathjax"])
def test_multiple_inputs_keep_shared_math(cli, put, tmp_path, backend):
    put("a.md", "$x$")
    put("b.md", "# No math")
    cli("a.md", "b.md", "-o", "public", "--math", backend, "--assets", "shared")
    doc = soup(tmp_path / "public/a.html")
    for tag in doc.select("link[href],script[src]"):
        url = tag.get("href", tag.get("src"))
        assert (tmp_path / "public" / unquote(url)).is_file(), url
    assert list((tmp_path / "public/assets").rglob("*.woff2"))


@pytest.mark.parametrize("backend", ["mathjax-chtml", "mathjax"])
def test_rebuild_restores_shared_math_assets(put, tmp_path, backend):
    from md2html.config import Options
    from md2html.project import Build

    put("notes/a.md", "$x^2$")
    put("notes/nested/b.md", "$x^2$ and $\\frac{1}{2}$")
    output = tmp_path / "public"
    build = Build(
        Options(
            input=[tmp_path / "notes"],
            output=output,
            root=tmp_path,
            recursive=True,
            assets="shared",
            math=backend,
        )
    )
    try:
        build.build()
        shutil.rmtree(output)
        build.build()
        put("notes/nested/b.md", "$x^2$ and $\\sqrt{z}$")
        build.build()
    finally:
        build.close()
    for target in [output / "a.html", output / "nested/b.html"]:
        doc = soup(target)
        for tag in doc.select("link[href],script[src]"):
            url = tag.get("href", tag.get("src"))
            assert (target.parent / unquote(url)).is_file(), url
    doc = soup(output / "nested/b.html")
    if backend == "mathjax-chtml":
        assert doc.select("mjx-msqrt")
        css = "".join(
            (output / "nested" / unquote(link["href"])).read_text()
            for link in doc.select('link[rel="stylesheet"]')
        )
        assert "mjx-msqrt" in css
    else:
        assert list((output / "assets/mathjax-newcm-font").rglob("*.woff2"))


def test_highlighting_blocks_have_independent_lexer_state(cli, put, tmp_path):
    put("a.md", "```python\n'''unfinished string\n```\n\n```python\ndef f():\n    return 1\n```\n")
    cli("a.md", "--math", "raw")
    blocks = soup(tmp_path / "a.html").select("pre code")
    assert "unfinished string" in blocks[0].text
    assert [span.text for span in blocks[1].select(".k")] == ["def", "return"]


def test_site_layouts_listing_pagination_and_feed(cli, put, tmp_path):
    put(
        "_layouts/outer.html",
        '<html><head>{% for sheet in md2html.page_stylesheets %}<link rel="stylesheet" href="{{sheet}}">{% endfor %}</head><body>{{content}}</body></html>',
    )
    put("_layouts/post.html", "---\nlayout: outer\n---\n<header>{{page.title}}</header>{{content}}")
    put("_includes/banner.html", "<b>{{site.title}}</b>")
    put(
        "index.html",
        '---\nlayout: outer\n---\n{% include banner.html %}{% for post in paginator.posts %}<a href="{{post.url | relative_url}}">{{post.title}}</a>{% endfor %}',
    )
    for number in range(1, 4):
        put(
            f"_posts/2025-01-0{number}-p{number}.md",
            f"---\ntitle: Post {number}\nlayout: post\ntags: [math]\n---\n# Post {number}",
        )
    put(
        "md2html.json",
        json.dumps(
            {
                "input": ".",
                "output": "public",
                "output_mode": "site",
                "math": "raw",
                "paginate": 2,
                "site": {"title": "My site", "baseurl": "/blog", "url": "https://example.test"},
            }
        ),
    )
    cli()
    assert "Post 3" in (tmp_path / "public/index.html").read_text()
    assert "Post 1" in (tmp_path / "public/page2/index.html").read_text()
    assert "My site" in (tmp_path / "public/index.html").read_text()
    assert "https://example.test/blog/2025/01/03/p3.html" in (tmp_path / "public/feed.xml").read_text()
    put("_posts/2025-01-03-p3.md", "---\ntitle: New title\n---\nchanged")
    cli()
    assert "New title" in (tmp_path / "public/index.html").read_text()


def test_jekyll_and_markdown_modes(cli, put, tmp_path):
    put("_config.yml", "title: Jekyll title\npermalink: /:title/\n")
    put("plain.md", "# untouched")
    put("page.md", "---\ntitle: Page\n---\n# {{site.title}}\n@include(part.md)\n")
    put("part.md", "Included")
    put("_posts/2025-01-01-post.md", "---\ntitle: Post\n---\nPost")
    cli("--jekyll", ".", "-o", "public", "--math", "raw")
    assert (tmp_path / "public/plain.md").read_text() == "# untouched"
    assert (tmp_path / "public/post/index.html").exists()
    assert "Jekyll title" in (tmp_path / "public/page.html").read_text()
    cli("--jekyll-markdown", "page.md", "-o", "expanded.md")
    text = (tmp_path / "expanded.md").read_text()
    assert "# {{site.title}}" in text and "Included" in text


def test_config_discovery_uses_only_working_directory(cli, put, tmp_path):
    put("md2html.json", "invalid parent configuration")
    put("child/page.md", "# {{ site.title }}")
    directory = tmp_path / "child"
    cli("page.md", "--math", "raw", cwd=directory)
    assert soup(directory / "page.html").select_one("h1").text == "child"

    put("child/md2html.json", json.dumps({"input": "page.md", "math": "raw", "site": {"title": "LOCAL"}}))
    cli(cwd=directory)
    assert soup(directory / "page.html").select_one("h1").text == "LOCAL"

    put(
        "md2html.json",
        json.dumps(
            {
                "input": "child/page.md",
                "output": "explicit/page.html",
                "math": "raw",
                "site": {"title": "EXPLICIT"},
            }
        ),
    )
    cli("--config", "../md2html.json", cwd=directory)
    assert soup(tmp_path / "explicit/page.html").select_one("h1").text == "EXPLICIT"
    cli("--config", "missing.json", cwd=directory, ok=False)


def test_config_precedence_paths_and_templates(cli, put, tmp_path):
    put("project/a.md", "# {{page.title}}\n\n```py\nprint(1)\n```")
    put(
        "project/templates/custom.html",
        "<html><title>{{page.title}}</title><style>{{md2html.css}}</style>{{content}}</html>",
    )
    put("project/custom.css", "body { color: purple; }")
    config = put(
        "project/md2html.json",
        json.dumps(
            {
                "input": "a.md",
                "output": "public/a.html",
                "template": "custom.html",
                "templates": "templates",
                "css": "custom.css",
                "math": "raw",
            }
        ),
    )
    cli("--config", config, "--no-minify-css")
    text = (tmp_path / "project/public/a.html").read_text()
    assert "body { color: purple; }" in text and ".codehilite" in text
    cli("--config", config, "--no-default-css", "-o", "override.html")
    assert "<style></style>" in (tmp_path / "override.html").read_text()


def test_liquid_only_and_no_liquid(cli, put, tmp_path):
    put("page.html", "---\ntitle: HTML\n---\n{{page.title}}\n# heading\n@src(foo.py)\n$x$")
    cli("page.html", "-o", "public/page.html")
    text = (tmp_path / "public/page.html").read_text()
    assert "HTML\n# heading\n@src(foo.py)\n$x$" == text
    put("a.md", "---\ntitle: Title\n---\n{{page.title}}")
    cli("--no-liquid", "a.md")
    text = (tmp_path / "a.html").read_text()
    assert "<title>Title</title>" in text and "{{page.title}}" in text


@pytest.mark.parametrize("backend,style", [("pygments", "monokai"), ("rouge", "github.light")])
def test_highlighters(cli, put, tmp_path, request, backend, style):
    if backend == "rouge":
        request.getfixturevalue("rouge")
    put("a.md", "```python\nprint(42)\n```")
    cli("a.md", "--highlighter", backend, "--highlighter-style", style)
    doc = soup(tmp_path / "a.html")
    assert doc.select(".codehilite span") and doc.select_one(".code-language").text == "python"
    assert ".codehilite" in doc.style.text


@pytest.mark.parametrize("option", ["--highlighter-style", "--highlighter-dark-style"])
def test_unknown_rouge_theme_explains_how_to_fix(cli, put, rouge, option):
    put("a.md", "```python\nprint(42)\n```")
    result = cli("a.md", "--math", "raw", "--highlighter", "rouge", option, "missing-theme", ok=False)
    assert 'Unknown Rouge theme "missing-theme"' in result.stderr
    assert "gem install --user-install rouge" in result.stderr
    assert "undefined method" not in result.stderr
    assert "Traceback" not in result.stderr


def test_moved_page_assets_and_image_options(cli, put, tmp_path):
    put("images/a.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
    put("x.py", "print(1)")
    put(
        "a.md", "![[images/a.svg|width=70%|class=extra|alt=Picture]]\n\n![ordinary](images/a.svg)\n@src(x.py)"
    )
    put("md2html.json", json.dumps({"images": {"class": "centered", "width": "40%"}}))
    cli("a.md", "-o", "public/a.html", "--assets", "shared")
    doc = soup(tmp_path / "public/a.html")
    for tag in doc.select("img[src],.code-header a[href]"):
        assert (tmp_path / "public" / tag.get("src", tag.get("href"))).is_file()
    image = doc.select_one(".obsidian-image")
    assert image["style"] == "width:70%" and set(image["class"]) >= {"extra", "centered"}


@pytest.mark.parametrize("permalink", ["../../escape.html", "/%2e%2e/escape.html"])
def test_output_escape_rejected(cli, put, permalink):
    put("a.md", f"---\npermalink: {permalink}\n---\nx")
    cli(".", "-o", "public", ok=False)


def test_collisions_and_clean_safety(cli, put, tmp_path):
    put("notes/a.md", "---\npermalink: /same.html\n---\na")
    put("notes/b.md", "---\npermalink: /same.html\n---\nb")
    assert "output collision" in cli("notes", "-o", "public").stderr
    assert (tmp_path / "public/same.html").exists()
    cli("notes", "-o", ".", "--output-mode", "site", "--clean", ok=False)
    assert (tmp_path / "notes/a.md").is_file()


def test_scaffolds(cli, tmp_path):
    assert json.loads(cli("--example-config", "-").stdout)["host"] == "127.0.0.1"
    assert "{{ content }}" in cli("--example-template", "-").stdout
    assert "--reader-page-bg" in cli("--example-css", "-").stdout
    assert "--host" in cli("--help").stdout
    assert "Yet Another" in cli("--readme").stdout


def test_nested_asset_paths_and_frontmatter_styles(cli, put, tmp_path):
    put("style/base.css", '@import "colors.css"; p { background: url(icon.svg); }')
    put("style/colors.css", "body { color: teal; }")
    put("style/icon.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
    put("notes/page.md", "---\nstylesheets: [../style/base.css]\ncss: []\n---\nHello")
    cli("notes/page.md", "-o", "public/deep/page.html")
    text = (tmp_path / "public/deep/page.html").read_text()
    assert "color:teal" in text and "data:image/svg+xml;base64," in text


def test_permalinks_local_assets_and_toc_duplicates(cli, put, tmp_path):
    put("notes/picture.svg", "<svg/>")
    put(
        "notes/page.md",
        "---\npermalink: /deep/article/\n---\n@toc\n# Heading\n# Heading\n![Picture](picture.svg)",
    )
    cli("notes", "-o", "public", "--math", "raw", "--assets", "shared")
    doc = soup(tmp_path / "public/deep/article/index.html")
    assert doc.select_one('a[href="#heading-2"]')
    image = doc.select_one("img")
    assert (tmp_path / "public/deep/article" / image["src"]).is_file()


def test_markdown_export_toc_defaults_and_liquid(cli, put, tmp_path):
    put(
        "a.md",
        "---\ntitle: Mine\n---\n@toc\n# First\n\n{{page.title}}\n\n@src-begin(python)\nprint(1)\n@src-end",
    )
    put("md2html.json", json.dumps({"frontmatter": {"layout": "post", "title": "Default"}}))
    cli("--jekyll-markdown", "a.md", "-o", "export/a.md")
    text = (tmp_path / "export/a.md").read_text()
    assert "layout: post" in text and "title: Mine" in text
    assert "{{page.title}}" in text and 'href="#first"' in text and "@toc" not in text
    assert "\nurl:" not in text


@pytest.mark.parametrize(
    "setting,value",
    [
        ("execute", "false"),
        ("math", "unknown"),
        ("timeout", 0),
        ("images", []),
        ("css", 12),
        ("port", "abc"),
        ("commands", {"python": []}),
    ],
)
def test_invalid_configuration_is_a_clean_error(cli, put, setting, value):
    put("a.md", "# Page")
    put("md2html.json", json.dumps({"input": "a.md", setting: value}))
    result = cli(ok=False)
    assert "error:" in result.stderr and "Traceback" not in result.stderr


def test_npm_lookup_from_notes_parent(cli, put, tmp_path):
    # This project has its own parent installation; no package lives beside the notes.
    import os

    npm = Path(__file__).resolve().parents[1] / "node_modules"
    os.symlink(npm, tmp_path / "node_modules", target_is_directory=True)
    put("nested/notes/a.md", "$x$")
    for backend in ["mathjax-chtml", "mathjax"]:
        cli(
            "a.md",
            "-o",
            f"public/{backend}.html",
            "--math",
            backend,
            "--assets",
            "shared",
            cwd=tmp_path / "nested/notes",
        )
        assert list((tmp_path / "nested/notes/public/assets").rglob("*.woff2"))


def test_timeout_reaps_orphan_with_new_session(cli, put, tmp_path):
    import os

    put(
        "orphan.py",
        "import subprocess,sys,time\np=subprocess.Popen([sys.executable,\"-c\", \"import pathlib,time,os;pathlib.Path('child.pid').write_text(str(os.getpid()));time.sleep(1);pathlib.Path('leaked').touch()\"],start_new_session=True)\ntime.sleep(10)\n",
    )
    put("a.md", "@src(orphan.py)")
    result = cli("-e", "--timeout", ".3", "a.md")
    assert "timed out" in result.stderr
    pid = int((tmp_path / "child.pid").read_text())
    time.sleep(1.1)
    assert not (tmp_path / "leaked").exists()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_included_markdown_assets_follow_the_fragment(cli, put, tmp_path):
    put("parts/img.svg", "<svg/>")
    put("parts/fragment.md", "![Included](img.svg)")
    put("a.md", "@include(parts/fragment.md)")
    cli("a.md", "-o", "public/a.html")
    image = soup(tmp_path / "public/a.html").select_one("img")
    assert image["src"] == "data:image/svg+xml;base64,PHN2Zy8+"


def test_shared_authored_stylesheets_preserve_imports_and_urls(cli, put, tmp_path):
    put("styles/main.css", '@import url("nested/colors.css"); body { background: url("icon.svg"); }')
    put("styles/nested/colors.css", "body { color: teal; }")
    put("styles/icon.svg", "<svg/>")
    put("notes/a.md", "# Hello")
    config = put(
        "md2html.json",
        json.dumps(
            {
                "input": "notes/a.md",
                "output": "public/nested/a.html",
                "assets": "shared",
                "stylesheets": "styles/main.css",
            }
        ),
    )
    cli("--config", config)
    target = tmp_path / "public/nested/a.html"
    doc = soup(target)
    sheet = target.parent / doc.select('link[rel="stylesheet"]')[-1]["href"]
    assert '@import url("nested/colors.css")' in sheet.read_text()
    assert 'url("icon.svg")' in sheet.read_text()
    assert "color:teal" not in sheet.read_text()
    assert not list((tmp_path / "public").rglob("*.svg"))


def test_indented_display_math_preserves_following_content(cli, put, tmp_path):
    put(
        "a.md",
        r"""$$\left(\matrix{1 & 2 \cr
        3 & 4 \cr }\right)$$

After the matrix.

$$\begin{array}{cc}
    1 & 2 \\
    3 & 4
\end{array}$$

    $not math$ {{ literal }}

The final $x^2$ remains inline.
""",
    )
    result = cli("a.md")
    doc = soup(tmp_path / "a.html")
    assert not result.stderr
    assert len(doc.select(".display-math")) == 2
    assert len(doc.select(".inline-math")) == 1
    assert "After the matrix." in doc.text
    assert "$not math$ {{ literal }}" in doc.select_one("pre").text
    assert "MD2HTML" not in doc.text


def test_custom_layout_warns_when_math_styles_are_omitted(cli, put, tmp_path):
    put("_layouts/post.html", "<html><body>{{ content }}</body></html>")
    put("a.md", "---\nlayout: post\n---\n$x^2$\n")
    result = cli("a.md")
    assert "layout omits generated CommonHTML styles" in result.stderr
    put(
        "_layouts/post.html",
        "<html><head><style>{{ md2html.math_css }}</style></head><body>{{ content }}</body></html>",
    )
    assert "layout omits" not in cli("a.md").stderr


def test_jekyll_highlight_preserves_indentation_and_literal_syntax(cli, put, tmp_path):
    put(
        "a.md",
        """{% highlight python %}
def example():
    return "{{literal}} $not_math$ `code`"
{% endhighlight %}

After code.
""",
    )
    assert not cli("a.md").stderr
    doc = soup(tmp_path / "a.html")
    assert '    return "{{literal}} $not_math$ `code`"' in doc.select_one("pre").text
    assert "MD2HTML" not in doc.text
    assert "After code." in doc.text


def test_highlight_tags_inside_literal_code_stay_literal(cli, put, tmp_path):
    put(
        "a.md",
        """```liquid
{% highlight python %}{{ literal }}{% endhighlight %}
```

<pre>{% highlight python %}{{ literal }}{% endhighlight %}</pre>

{% highlight html %}
<pre>{{ another }}</pre>
{% endhighlight %}
""",
    )
    assert not cli("a.md").stderr
    doc = soup(tmp_path / "a.html")
    assert len(doc.select("pre")) == 3
    assert doc.text.count("{% highlight python %}") == 2
    assert "<pre>{{ another }}</pre>" in doc.select("pre")[2].text
    assert "MD2HTML" not in doc.text


def test_jekyll_default_category_urls_match_index_and_feed(cli, put, tmp_path):
    put(
        "_posts/2026-07-05-example.md",
        "---\ntitle: Example\ncategories: physics math\ntags: [algebra]\n---\nContent",
    )
    put(
        "index.html",
        '---\n---\n{% for post in site.categories.physics %}<a href="{{ post.url }}">{{ post.title }}</a>{% endfor %}',
    )
    cli("--jekyll", ".", "-o", "public", "--math", "raw")
    url = "/physics/math/2026/07/05/example.html"
    assert (tmp_path / "public" / url.lstrip("/")).exists()
    assert soup(tmp_path / "public/index.html").a["href"] == url
    assert url in (tmp_path / "public/feed.xml").read_text()


def test_wolfram_operators_and_multiline_text(cli, put, tmp_path):
    code = """(* comment with a dot .
and a second line *)
a.b + .5 + 1.5;
f[x_:1] := "first line
second line";
"""
    code += 'label = "continued ' + "\\\n" + 'string";\n'
    put("a.md", "```mathematica\n" + code + "```\n")
    cli("a.md")
    doc = soup(tmp_path / "a.html")
    assert not doc.select(".err")
    assert doc.select_one("pre code").text == code
    assert any(token.text == "." for token in doc.select(".o"))
    assert any(".5" in token.text for token in doc.select(".m,.mf"))


@pytest.mark.parametrize("mode", ["pages", "jekyll"])
def test_wolfram_builtins_without_external_tools(cli, put, tmp_path, monkeypatch, mode):
    builtins = ["Integrate", "RandomReal", "MultinormalDistribution", "Eigensystem", "CholeskyDecomposition"]
    code = " ".join([*builtins, "MyFunction", "sigma"]) + "\n"
    aliases = ["mathematica", "mma", "nb", "wl", "wolfram", "wolfram-language", "m", "Mathematica"]
    page = "\n".join(f"```{language}\n{code}```\n" for language in aliases)
    for filename in ("example.m", "example.wl"):
        put(filename, code)
        page += f"\n@src({filename})\n"
    put("a.md", "---\n---\n" + page + "\n$x^2$\n")
    monkeypatch.setenv("PATH", "")
    result = cli("a.md", "--output-mode", mode, "--math", "mathml", "-o", "public")
    doc = soup(tmp_path / "public/a.html")
    assert not result.stderr
    assert not doc.select(".err")
    blocks = doc.select("pre code")
    assert len(blocks) == len(aliases) + 2
    for block in blocks:
        assert block.parent.parent["data-language"] == "wl"
        assert block.text == code
        assert [span.text for span in block.select(".nb")] == builtins
        assert [span.text for span in block.select(".nv")] == ["MyFunction", "sigma"]
    assert doc.select("math")


def test_mixed_language_highlighting_and_custom_palettes(cli, put, tmp_path):
    put("a.md", "```wl\nf[x_] := AbsoluteTiming[x^2]\n```\n\n```cpp\nint main() { return 0; }\n```")
    cli("a.md", "--math", "raw", "--no-minify-css")
    doc = soup(tmp_path / "a.html")
    assert doc.select_one('[data-language="wl"] .nb').text == "AbsoluteTiming"
    assert doc.select_one('[data-language="cpp"] .kt').text == "int"
    assert '.codehilite[data-language="wl"] .nb { color: #000' in doc.style.text
    assert '.codehilite[data-language="wl"] .nb { color: #E6EDF3' in doc.style.text
    assert '.codehilite[data-language="wl"] .p { color: #555' in doc.style.text
    assert '.codehilite[data-language="wl"] .nv { color: #79C0FF' in doc.style.text
    assert '.codehilite:not([data-language="wl"]) .kt { color: #B00040' in doc.style.text
    cli("a.md", "--math", "raw", "--highlighter-style", "monokai", "--highlighter-dark-style", "monokai")
    css = soup(tmp_path / "a.html").style.text
    assert ".codehilite .nb{color:#a6e22e" in css.lower()


@pytest.mark.parametrize("missing", ["ruby", "gem"])
def test_unavailable_rouge_explains_optional_dependency(cli, put, tmp_path, monkeypatch, missing):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if missing == "gem":
        ruby = shutil.which("ruby")
        if not ruby:
            pytest.skip("requires Ruby to test missing gem")
        (bin_dir / "ruby").symlink_to(ruby)
        monkeypatch.setenv("GEM_HOME", str(tmp_path / "empty-gems"))
        monkeypatch.setenv("GEM_PATH", str(tmp_path / "empty-gems"))
    monkeypatch.setenv("PATH", str(bin_dir))
    put("a.md", "```python\nprint(42)\n```\n")
    result = cli("a.md", "--math", "raw", "--highlighter", "rouge", ok=False)
    assert "requires Ruby and the rouge gem" in result.stderr
    assert "gem install --user-install rouge" in result.stderr
    assert "--highlighter pygments" in result.stderr
    assert "Traceback" not in result.stderr
