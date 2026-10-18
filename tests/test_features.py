"""User-visible build choices and dependency behavior."""

import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest
from bs4 import BeautifulSoup


def test_pages_embed_media_and_allow_shared_override(cli, put, tmp_path):
    put("notes/picture.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
    for name in ("a", "b"):
        put(
            f"notes/{name}.md", '![image](picture.svg)\n\n![[picture.svg]]\n\n<audio src="sound.wav"></audio>'
        )
    (tmp_path / "notes/sound.wav").write_bytes(b"RIFF")
    cli("notes/a.md", "notes/b.md", "-o", "html", "--math", "raw")
    for name in ("a", "b"):
        doc = BeautifulSoup((tmp_path / f"html/{name}.html").read_text(), "html.parser")
        assert all(tag["src"].startswith("data:") for tag in doc.select("img,audio"))
        assert not doc.select('link[rel="stylesheet"]')
    cli("notes/a.md", "-o", "shared/a.html", "--assets", "shared", "--math", "raw")
    assert (tmp_path / "shared/picture.svg").exists()
    put("md2html.json", json.dumps({"images": {"embed": False}}))
    cli("notes/a.md", "-o", "linked/a.html", "--math", "raw")
    assert (tmp_path / "linked/picture.svg").exists()
    assert "data:image" not in (tmp_path / "linked/a.html").read_text()


def test_site_standalone_means_shared_local_assets(cli, put, tmp_path):
    put("notes/a.md", "![image](picture.svg)")
    put("notes/picture.svg", "<svg/>")
    cli("notes", "-o", "html", "--output-mode", "site", "--standalone", "--math", "raw")
    assert (tmp_path / "html/picture.svg").exists()
    assert 'src="picture.svg"' in (tmp_path / "html/a.html").read_text()
    assert (tmp_path / "html/assets").exists()


@pytest.mark.parametrize("arguments", [("page.md",), ("page.md", "other.md"), ("-r", "page.md")])
def test_listed_files_default_to_standalone(cli, put, tmp_path, arguments):
    put("page.md", "![image](picture.svg)")
    put("other.md", "Other page")
    put("picture.svg", "<svg/>")
    cli(*arguments, "--math", "raw")
    target = tmp_path / ("html/page.html" if "other.md" in arguments else "page.html")
    assert 'src="data:image/svg+xml;base64,' in target.read_text()


@pytest.mark.parametrize("flags", [(), ("-r",)])
def test_directory_defaults_to_site_and_excludes_nested_output(cli, put, tmp_path, flags):
    put("index.md", "![image](picture.svg)")
    put("picture.svg", "<svg/>")
    put("nested/page.md", "Nested page")
    put("html/keep.txt", "User output file")
    args = (*flags, ".", "-o", "html", "--math", "raw")
    cli(*args)
    assert 'src="picture.svg"' in (tmp_path / "html/index.html").read_text()
    assert (tmp_path / "html/assets/base.css").exists()
    assert (tmp_path / "html/nested/page.html").exists()
    assert (tmp_path / "html/feed.xml").exists()
    assert "Built 0 files" in cli(*args).stdout
    assert not (tmp_path / "html/html").exists()
    assert (tmp_path / "html/keep.txt").read_text() == "User output file"


def test_explicit_mode_overrides_directory_default(cli, put, tmp_path):
    put("notes/page.md", "![image](picture.svg)")
    put("notes/picture.svg", "<svg/>")
    put("md2html.json", json.dumps({"input": "notes", "output_mode": "pages"}))
    cli("-o", "pages", "--math", "raw")
    assert 'src="data:image/svg+xml;base64,' in (tmp_path / "pages/page.html").read_text()
    cli("--output-mode", "site", "-o", "site", "--math", "raw")
    assert 'src="picture.svg"' in (tmp_path / "site/page.html").read_text()
    put("md2html.json", json.dumps({"input": "notes", "output_mode": "site"}))
    cli("--output-mode", "pages", "-o", "pages", "--math", "raw")
    assert 'src="data:image/svg+xml;base64,' in (tmp_path / "pages/page.html").read_text()


def test_missing_explicit_execution_cache_is_verbose_only(cli, put, tmp_path):
    put("a.md", '@src-begin(python, execute)\nprint("HELLO")\n@src-end\n')
    assert "cached output unavailable" not in cli("a.md", "--math", "raw").stderr
    assert "cached output unavailable" in cli("a.md", "--math", "raw", "-v").stderr
    assert "cached output unavailable" not in (tmp_path / "a.html").read_text()
    cli("a.md", "--math", "raw", "-e")
    assert "cached output unavailable" not in cli("a.md", "--math", "raw", "-v").stderr


def test_example_writer_requires_force(cli, put, tmp_path):
    put("config.json", "KEEP")
    assert "--force" in cli("--example-config", "config.json", ok=False).stderr
    assert (tmp_path / "config.json").read_text() == "KEEP"
    cli("--example-config", "config.json", "-f")
    assert json.loads((tmp_path / "config.json").read_text())["output"] == "html"


def test_site_selection_and_jekyll_explicit_include(cli, put, tmp_path):
    for name in (
        "index.md",
        "img/share.gif",
        "_private/secret.txt",
        "Gemfile",
        "Gemfile.lock",
        "node_modules/package/file.js",
        "gemfiles/ruby.gemfile",
        "vendor/bundle/file.txt",
        "vendor/cache/file.txt",
        "vendor/gems/file.txt",
        "vendor/ruby/file.txt",
        "vendor/file.txt",
        "venv/file.txt",
        ".venv/file.txt",
        "nested/.secret",
        ".hidden/file.txt",
        "nested/md2html.json",
        "_download.txt",
        "backup.txt~",
        "#draft.txt",
        "~draft.txt",
        ".htaccess",
        "skip/file.txt",
    ):
        put("site/" + name, "content")
    put("site/md2html.json", "{}")
    put("site/_config.yml", "include: [_public, node_modules/keep, skip]\n")
    put("site/_public/share.txt", "EXPLICIT")
    put("site/node_modules/keep/file.js", "EXPLICIT")
    put("md2html.json", json.dumps({"exclude": ["skip"]}))
    for mode in ("pages", "site", "jekyll"):
        cli("-r", "site", "-o", "out-" + mode, "--output-mode", mode, "--math", "raw")
        output = tmp_path / ("out-" + mode)
        assert (output / "img/share.gif").exists()
        for name in ("md2html.json", "_private", ".venv", "nested/.secret", ".hidden", "skip"):
            assert not (output / name).exists()
        for name in ("vendor/file.txt", "venv/file.txt", "nested/md2html.json", "node_modules/keep/file.js"):
            assert (output / name).exists()
        for name in (
            "Gemfile",
            "Gemfile.lock",
            "gemfiles",
            "node_modules/package",
            "vendor/bundle",
            "vendor/cache",
            "vendor/gems",
            "vendor/ruby",
            "_download.txt",
            "backup.txt~",
            "#draft.txt",
            "~draft.txt",
        ):
            assert (output / name).exists() == (mode != "jekyll")
        assert (output / "_public/share.txt").exists() == (mode == "jekyll")
    # With no explicit include list, Jekyll includes .htaccess by default.
    put("site/_config.yml", "{}")
    cli("site", "--jekyll", "-o", "default-jekyll", "--math", "raw")
    assert (tmp_path / "default-jekyll/.htaccess").exists()


def test_nested_pagination_hidden_posts_and_feed_metadata(cli, put, tmp_path):
    put("site/blog/index.html", "{% for p in paginator.posts %}{{p.title}}:{{p.id}};{% endfor %}")
    put("site/_posts/2026-01-01-a.md", "---\ntitle: Visible A\n---\na")
    put("site/_posts/2026-01-02-b.md", "---\ntitle: Visible B\n---\nb")
    put("site/_posts/2026-01-03-c.md", "---\ntitle: Secret\nhidden: true\n---\nc")
    put(
        "md2html.json",
        json.dumps(
            {
                "site": {
                    "paginate": 1,
                    "paginate_path": "/blog/page:num/",
                    "url": "https://example.test",
                    "author": {
                        "name": "Ada",
                        "email": "ada@example.test",
                        "url": "https://example.test/about",
                    },
                }
            }
        ),
    )
    cli("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    assert "Visible B:/2026/01/02/b.html" in (tmp_path / "html/blog/index.html").read_text()
    assert "Visible A" in (tmp_path / "html/blog/page2/index.html").read_text()
    assert not (tmp_path / "html/blog/page3").exists()
    assert (tmp_path / "html/2026/01/03/c.html").exists()
    from xml.etree import ElementTree as ET

    feed = ET.parse(tmp_path / "html/feed.xml").getroot()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert feed.findtext("a:title", namespaces=ns) == "site"
    assert feed.findtext("a:id", namespaces=ns) == "https://example.test/feed.xml"
    assert feed.findtext("a:author/a:name", namespaces=ns) == "Ada"
    assert feed.findtext("a:author/a:uri", namespaces=ns) == "https://example.test/about"
    assert feed.find("a:link[@rel='self']", ns) is not None
    assert feed.findtext("a:updated", namespaces=ns) == "2026-01-03T00:00:00+00:00"


def test_filename_highlighting_and_math_toc(cli, put, tmp_path):
    put("example.h", "int answer = 42;")
    put("a.md", "@toc\n\n# Equation $x^2$\n\n@src(example.h)")
    cli("a.md", "--math", "mathml")
    doc = BeautifulSoup((tmp_path / "a.html").read_text(), "html.parser")
    assert doc.select_one(".codehilite .kt")
    assert doc.select_one(".table-of-contents math")
    assert "MD2HTML" not in doc.get_text()


def test_shared_styles_are_additive_descriptive_and_independent(cli, put, tmp_path):
    put("site/css/common.css", "p { color: teal; }")
    put("site/css/extra.css", "h1 { color: coral; }")
    put("site/nested/css/extra.css", "WRONG { color: red; }")
    put("site/index.md", "```cpp\nint x;\n```\n")
    put(
        "site/nested/a.md",
        "---\nstylesheets: [css/extra.css]\nfeature_css: false\n---\n```cpp\nint x;\n```\n",
    )
    put("site/b.md", "```cpp\nint x;\n```\n\n![a](image.svg)")
    put("site/image.svg", "<svg/>")
    put(
        "site/md2html.json",
        json.dumps(
            {
                "input": ".",
                "output": "../html",
                "output_mode": "site",
                "stylesheets": ["css/common.css"],
                "math": "raw",
            }
        ),
    )
    cli("--config", "site/md2html.json")
    sheets = {p.name: p.read_text() for p in (tmp_path / "html/assets").glob("*.css")}
    assert {
        "base.css",
        "code.css",
        "highlight.css",
        "image.css",
        "style-css-common.css",
        "style-css-extra.css",
    } <= sheets.keys()
    assert "coral" in sheets["style-css-extra.css"] and "WRONG" not in sheets["style-css-extra.css"]
    assert not (tmp_path / "html/assets/md2html").exists()
    doc = BeautifulSoup((tmp_path / "html/nested/a.html").read_text(), "html.parser")
    links = [Path(link["href"]).name for link in doc.select('link[rel="stylesheet"]')]
    assert "style-css-common.css" in links and "style-css-extra.css" in links
    assert "highlight.css" not in links and "code.css" not in links
    assert "codehilite" not in sheets["image.css"]


def test_layout_errors_warn_and_leave_content(cli, put, tmp_path):
    put("site/a.md", "---\nlayout: missing\n---\n# Keep A")
    put("site/b.md", "---\nlayout: cycle\n---\n# Keep B")
    put("site/_layouts/cycle.html", "---\nlayout: cycle\n---\n<section>{{content}}</section>")
    result = cli("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    assert "file not found: missing" in result.stderr and "layout cycle" in result.stderr
    assert "Keep A" in (tmp_path / "html/a.html").read_text()
    assert "Keep B" in (tmp_path / "html/b.html").read_text()


@pytest.mark.parametrize("assets", ["standalone", "shared"])
def test_css_resources_resolve_from_stylesheets(cli, put, tmp_path, assets):
    put("notes/a.md", "Hello")
    put("notes/deep/b.md", "Nested")
    put("notes/styles/main.css", '@import "nested/extra.css" screen; body { background: url("root.svg"); }')
    put("notes/styles/nested/extra.css", 'p { background: url("glyph.svg"); }')
    put("notes/styles/nested/glyph.svg", "<svg>GLYPH</svg>")
    put("notes/styles/root.svg", "<svg>ROOT</svg>")
    cli(
        "notes",
        "-r",
        "--output-mode",
        "pages",
        "--assets",
        assets,
        "--math",
        "raw",
        "--css",
        "notes/styles/main.css",
        "-o",
        "html",
    )
    for name in ("a.html", "deep/b.html"):
        page = tmp_path / "html" / name
        document = BeautifulSoup(page.read_text(), "html.parser")
        if assets == "standalone":
            assert document.style.text.count("data:image/svg+xml;base64,") == 2
        else:
            sheet = (page.parent / document.select_one('link[rel="stylesheet"]')["href"]).resolve()
            urls = re.findall(r'url\("([^\"]+)"\)', sheet.read_text())
            assert {(sheet.parent / unquote(url)).read_text() for url in urls} == {
                "<svg>GLYPH</svg>",
                "<svg>ROOT</svg>",
            }


def test_raw_math_in_jekyll_is_configurable(cli, put, tmp_path):
    put("site/a.md", "---\ntitle: Raw\n---\n$x^2$\n\n\\begin{align}x&=1\\end{align}")
    cli("site", "-o", "html", "--jekyll", "--math", "raw")
    text = (tmp_path / "html/a.html").read_text()
    assert "$x^2$" in text and "\\begin{align}x&amp;=1\\end{align}" in text
    assert "$$\\begin" not in text and "mjx-container" not in text


def test_incremental_restart_dependencies_and_collections(cli, put, tmp_path):
    put("site/_includes/list.html", "{% for p in site.posts %}{{p.title}};{% endfor %}")
    put("site/index.html", "{% include list.html %}")
    put("site/a.md", "@include(fragment.txt)\n@src(example.cpp)")
    put("site/fragment.txt", "# ORIGINAL")
    put("site/example.cpp", "int main() {}")
    put("site/b.md", "# Independent")
    put("site/_posts/2026-01-01-one.md", "---\ntitle: ONE\n---\nPost")
    args = ("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    cli(*args)
    paths = [tmp_path / "html" / name for name in ("index.html", "a.html", "b.html")]
    before = [p.stat().st_mtime_ns for p in paths]
    assert "Built 0 files" in cli(*args).stdout
    assert before == [p.stat().st_mtime_ns for p in paths]
    put("site/fragment.txt", "# CHANGED")
    cli(*args)
    assert "CHANGED" in paths[1].read_text()
    assert before[0] == paths[0].stat().st_mtime_ns
    assert before[2] == paths[2].stat().st_mtime_ns
    put("site/_posts/2026-01-02-two.md", "---\ntitle: TWO\n---\nPost")
    cli(*args)
    assert "TWO;ONE;" in paths[0].read_text()
    assert before[2] == paths[2].stat().st_mtime_ns
    (tmp_path / "site/_posts/2026-01-01-one.md").unlink()
    cli(*args)
    assert "ONE" not in paths[0].read_text()
    put("site/_includes/list.html", "Updated {% for p in site.posts %}{{p.title}};{% endfor %}")
    cli(*args)
    assert paths[0].read_text().startswith("Updated")
    assert before[2] == paths[2].stat().st_mtime_ns
    put("site/_templates/list.html", "{% include 'inner.html' %}")
    put("site/_templates/inner.html", "Priority {% for p in site.posts %}{{p.title}};{% endfor %}")
    cli(*args)
    assert paths[0].read_text().startswith("Priority TWO;")
    put("site/_posts/2026-01-03-three.md", "---\ntitle: THREE\n---\nPost")
    cli(*args)
    assert "Priority THREE;TWO;" in paths[0].read_text()
    assert before[2] == paths[2].stat().st_mtime_ns


def test_incremental_cache_changes_and_missing_assets(cli, put, tmp_path):
    put("a.md", "@src(example.py, execute)\n\n![x](x.svg)")
    put("example.py", 'print("CACHED")')
    put("x.svg", "<svg/>")
    args = ("a.md", "-o", "html/a.html", "--assets", "shared", "--math", "raw")
    cli(*args, "-e")
    cli(*args)
    output = next((tmp_path / ".md2html-cache/a").rglob("output.txt"))
    output.write_text("UPDATED CACHE")
    cli(*args)
    assert "UPDATED CACHE" in (tmp_path / "html/a.html").read_text()
    (tmp_path / "html/x.svg").unlink()
    cli(*args)
    assert (tmp_path / "html/x.svg").exists()


def test_incremental_restart_skips_math_renderer(cli, put, tmp_path, monkeypatch):
    put("a.md", "$x^2$")
    cli("a.md")
    monkeypatch.setenv("PATH", "")
    assert "Built 0 files" in cli("a.md").stdout
    result = cli("a.md", "--force", ok=False)
    assert "node" in result.stderr


def test_standalone_media_attributes_leave_comments_and_scripts_alone(cli, put, tmp_path):
    put("x.svg", "<svg/>")
    put(
        "a.md",
        """<picture><source srcset="x.svg 1x, x.svg 2x"><img src=x.svg></picture>

<video poster="x.svg"><source src="x.svg"></video>

<!-- <img src="x.svg"> -->
<script>const example = '<img src="x.svg">';</script>
""",
    )
    cli("a.md", "--math", "raw")
    text = (tmp_path / "a.html").read_text()
    doc = BeautifulSoup(text, "html.parser")
    assert doc.select_one("picture source")["srcset"].count("data:image/svg+xml;base64,") == 2
    assert doc.select_one("video")["poster"].startswith("data:")
    assert '<!-- <img src="x.svg"> -->' in text
    assert "const example = '<img src=\"x.svg\">';" in text


def test_directory_pages_embed_and_shared_math_survives_incremental_changes(cli, put, tmp_path):
    put("notes/image.svg", "<svg/>")
    put("notes/a.md", "![a](image.svg)\n\n$x$")
    put("notes/b.md", r"$\sqrt{y}$")
    cli("notes", "-o", "embedded", "--output-mode", "pages")
    assert "data:image/svg+xml;base64," in (tmp_path / "embedded/a.html").read_text()
    args = ("notes", "-o", "shared", "--assets", "shared")
    cli(*args)
    sheet = tmp_path / "shared/assets/mathjax-chtml.css"
    content = sheet.read_text()
    before = (tmp_path / "shared/b.html").stat().st_mtime_ns
    put("notes/a.md", "![a](image.svg)\n\n$z^2$")
    cli(*args)
    assert (tmp_path / "shared/b.html").stat().st_mtime_ns == before
    assert sheet.read_text() == content
    assert "mjx-msqrt" in content


def test_removed_pages_preserve_user_files_and_separate_outputs(cli, put, tmp_path):
    put("site/a.md", "Alpha")
    put("site/b.md", "Beta")
    args = ("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    cli(*args)
    put("html/upload.gif", "USER FILE")
    put("html/b.html", "MANUALLY MODIFIED")
    (tmp_path / "site/a.md").unlink()
    (tmp_path / "site/b.md").unlink()
    cli(*args)
    assert not (tmp_path / "html/a.html").exists()
    assert (tmp_path / "html/b.html").read_text() == "MANUALLY MODIFIED"
    assert (tmp_path / "html/upload.gif").read_text() == "USER FILE"
    put("note.md", "Note")
    cli("note.md", "-o", "pages/first.html", "--math", "raw")
    cli("note.md", "-o", "pages/second.html", "--math", "raw")
    assert (tmp_path / "pages/first.html").exists()


def test_config_and_page_css_append_with_project_precedence(cli, put, tmp_path):
    put("common.css", "p { color: teal; }")
    put("extra.css", "h1 { color: coral; }")
    put("notes/extra.css", "BAD { color: red; }")
    put("notes/a.md", "---\ncss: [extra.css]\n---\n# Hello")
    put("md2html.json", json.dumps({"css": ["common.css"]}))
    cli("notes/a.md", "--math", "raw")
    text = (tmp_path / "notes/a.html").read_text()
    assert "color:teal" in text and "color:coral" in text and "BAD{" not in text


def test_feed_limits_entries_and_preserves_offsets(cli, put, tmp_path):
    for number in range(1, 23):
        put(
            f"site/_posts/2026-01-{number:02d}-post.md",
            f"---\ndate: 2026-01-{number:02d}T12:00:00+03:00\n---\nPost",
        )
    cli("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    from xml.etree import ElementTree as ET

    feed = ET.parse(tmp_path / "html/feed.xml").getroot()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert len(feed.findall("a:entry", ns)) == 20
    assert feed.findtext("a:updated", namespaces=ns) == "2026-01-22T12:00:00+03:00"
