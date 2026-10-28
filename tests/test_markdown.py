"""Markdown syntax and the HTML/Markdown export boundary."""

import pytest
from bs4 import BeautifulSoup


def read_html(path):
    return BeautifulSoup(path.read_text(), "html.parser")


@pytest.mark.parametrize("wrapper", ["{}", '<div class="code-box">{}</div>'])
def test_raw_code_preserves_markup_and_whitespace(cli, put, tmp_path, wrapper):
    raw = (
        '<pre><code><span class="kn">#lang sicp</span>\n\n'
        '\t(<span class="nb">*</span> x <span class="nb">*</span> y)\n'
        "a_b_c &lt; &amp;lt; `ticks` $not_math$ {{ literal }}\n"
        "</code></pre>"
    )
    put("page.md", wrapper.format(raw) + "\n\nInline <code>*x* **y** $z$ {{raw}}</code>.")
    cli("page.md", "--math", "raw")
    text = (tmp_path / "page.html").read_text()
    doc = read_html(tmp_path / "page.html")
    assert raw in text
    assert not doc.select("pre em, pre strong, pre p, pre .math")
    assert doc.select_one("p code").text == "*x* **y** $z$ {{raw}}"
    assert not doc.select("p code em, p code strong, p code .math")


@pytest.mark.parametrize("mode", ["pages", "jekyll-markdown"])
def test_fence_syntax_inside_html_code_stays_literal(cli, put, tmp_path, mode):
    raw = "<pre><code>\n```python\n*literal* {{ raw }} $raw$\n```\n</code></pre>"
    put("page.md", raw)
    suffix = "md" if mode == "jekyll-markdown" else "html"
    cli("page.md", "--output-mode", mode, "-o", f"out.{suffix}", "--math", "raw")
    assert raw in (tmp_path / f"out.{suffix}").read_text()


def test_export_and_second_render_preserve_code(cli, put, tmp_path):
    code = "#lang sicp\n\n(define (square x) (* x x))\n(define (cube x) (* x (* x x)))\n"
    put("sample.rkt", code)
    put(
        "page.md",
        "---\nrender_with_liquid: false\n---\n@toc\n\n# Code *examples*\n\n"
        '@src(sample.rkt)\n\n```python\nprint("{{ literal }} $raw$")\n```\n',
    )
    cli("page.md", "--jekyll-markdown", "-o", "export/page.md", "--math", "raw")
    exported = (tmp_path / "export/page.md").read_text()
    assert "# Code *examples*" in exported and "```python" in exported
    assert "@src(" not in exported and "@toc" not in exported
    assert read_html(tmp_path / "export/page.md").select_one("pre code").text == code
    cli("export/page.md", "-o", "public/page.html", "--math", "raw")
    doc = read_html(tmp_path / "public/page.html")
    assert doc.select_one(".code-box pre code").text == code
    assert not doc.select("pre em, pre strong, pre p")
    assert doc.select_one('.table-of-contents a[href="#code-examples"] em').text == "examples"
    assert doc.select_one("h1#code-examples em").text == "examples"
    assert "{{ literal }} $raw$" in doc.select("pre code")[1].text


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fenced_and_indented_code_use_existing_highlighter(cli, put, tmp_path, fence):
    code = "\t*x* **y** {{raw}} $raw$ &lt; <tag>\n"
    put("page.md", f"{fence}unknown-language\n{code}{fence}\n\n    *x* &lt; <tag>\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    blocks = doc.select(".codehilite pre code")
    assert [b.text for b in blocks] == [code, "*x* &lt; <tag>\n"]
    assert not doc.select("pre em, pre strong, pre .math")
    assert doc.select_one(".code-language").text == "unknown-language"


def test_longer_and_unclosed_fences(cli, put, tmp_path):
    put("page.md", "````text\n```\n*literal*\n`````\n\n```text\nunclosed *literal*\n")
    cli("page.md", "--math", "raw")
    assert [b.text for b in read_html(tmp_path / "page.html").select("pre code")] == [
        "```\n*literal*\n",
        "unclosed *literal*\n",
    ]


def test_multiline_inline_code_stays_literal(cli, put, tmp_path):
    put("page.md", "Code `{{ untouched }}\n$x$` and *emphasis*.\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert doc.select_one("p code").text == "{{ untouched }}\n$x$"
    assert not doc.select(".math")


@pytest.mark.parametrize("source", ["{{ page.example }}", "{% include 'example.md' %}"])
def test_liquid_generated_fences_are_highlighted(cli, put, tmp_path, source):
    code = 'print("{{ literal }} $literal$")\n'
    put("_includes/example.md", "```python\nprint(123)\n```\n")
    put(
        "page.md",
        "---\nexample: |\n  ```python\n  print(123)\n  ```\n---\n"
        + "```python\n" + code + "```\n\n" + source + "\n",
    )
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert [node.text for node in doc.select("pre code")] == [code, "print(123)\n"]
    assert len(doc.select('.codehilite[data-language="python"] .nb')) == 2
    assert not doc.select(".math")


def test_extensions_and_literal_counterparts(cli, put, tmp_path):
    put(
        "page.md",
        """| Name | Value |
| --- | --- |
| item | **value** |

~~deleted~~ H~2~O

- [x] done
- [ ] pending

https://example.test/path?q=1&x=2

`~~literal~~ https://example.test/ [x]`

```
~~literal~~ https://example.test/ [x]
```
""",
    )
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert doc.select_one("table td strong").text == "value"
    assert doc.select_one("del").text == "deleted"
    assert not doc.select("sub")
    boxes = doc.select(".task-list-item input")
    assert len(boxes) == 2 and all(b.has_attr("disabled") for b in boxes)
    assert boxes[0].has_attr("checked") and not boxes[1].has_attr("checked")
    assert doc.select_one('a[href="https://example.test/path?q=1&x=2"]')
    assert not doc.select("code a, code del, code input")


def test_heading_ids_and_formatted_toc_are_document_local(cli, put, tmp_path):
    body = (
        "@toc\n\n# A *title* & `code`\n\n# A *title* & `code`\n\n"
        "# <span>HTML</span> <code>*literal*</code>\n\n"
        "## Exercises\n\n### Exercise 1.1\n\n#### Solution\n"
    )
    put("notes/a.md", body)
    put("notes/b.md", body)
    cli("notes", "-o", "public", "--math", "raw")
    for name in ["a", "b"]:
        doc = read_html(tmp_path / f"public/{name}.html")
        assert [h["id"] for h in doc.select("article > h1")] == [
            "a-title-code",
            "a-title-code-2",
            "html-literal",
        ]
        toc = doc.select_one(".table-of-contents")
        assert toc.select_one('a[href="#a-title-code"] em').text == "title"
        assert toc.select_one('a[href="#a-title-code"] code').text == "code"
        assert toc.select_one('a[href="#html-literal"] code').text == "*literal*"
        assert toc.select_one('.exercise-list a[href="#exercise-11"]')
        assert not toc.select('a[href="#solution"]')
        assert "MD2HTML" not in str(doc) and "wzxhzdk" not in str(doc)


def test_native_list_indentation_and_emphasis(cli, put, tmp_path):
    put("page.md", "- parent\n    - child\n\nword_with_underscores and *emphasis*\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert doc.select_one("article ul li ul li").text == "child"
    assert [em.text for em in doc.select("article em")] == ["emphasis"]
    assert "word_with_underscores" in doc.text


def test_indented_html_is_code_and_raw_inline_code_keeps_its_paragraph(cli, put, tmp_path):
    put("page.md", "    <pre>*literal*</pre>\n\n    <code>**literal**</code>\n\n<code>*literal*</code>\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert doc.select_one(".codehilite pre code").text == "<pre>*literal*</pre>\n\n<code>**literal**</code>\n"
    assert doc.select_one("article > p > code").text == "*literal*"
    assert not doc.select("pre pre, pre em, pre strong")


def test_footnotes_number_references_and_preserve_rich_definitions(cli, put, tmp_path):
    put("page.md", "First[^later], second[^1], repeated[^later], missing[^missing].\n\n"
        "[^1]: Definition one with `code`.\n\n"
        "[^later]: A **bold** note with [a link](https://example.test) and $x^2$.\n\n"
        "    Second paragraph with *emphasis*.\n")
    cli("page.md", "--math", "mathml")
    doc = read_html(tmp_path / "page.html")
    refs = doc.select("a.footnote-ref")
    assert [ref.text for ref in refs] == ["1", "2", "1"]
    assert refs[0]["href"] == refs[2]["href"]
    assert len({ref.parent["id"] for ref in refs}) == 3
    for ref in refs:
        note = doc.find(id=ref["href"][1:])
        assert note is not None
        assert note.select_one(f'a.footnote-backref[href="#{ref.parent["id"]}"]')
    assert doc.select_one(".footnote strong").text == "bold"
    assert doc.select_one(".footnote math")
    assert doc.select_one(".footnote code").text == "code"
    assert "[^missing]" in doc.text
    assert "footnote-tooltip" in doc.select_one("style").text
    assert any("function setup()" in script.text for script in doc.select("script"))


@pytest.mark.parametrize("kind", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
def test_github_alerts_keep_block_content(cli, put, tmp_path, kind):
    put("page.md", f"> [!{kind}]\n> A **bold** message with a [link](https://example.test).\n>\n"
        "> - One\n> - Two\n>\n> Another paragraph.[^1]\n\n[^1]: A footnote.\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    alert = doc.select_one(f".markdown-alert-{kind.lower()}")
    assert alert.select_one(".markdown-alert-title").text == kind.capitalize()
    assert alert.select_one("strong").text == "bold"
    assert len(alert.select("li")) == 2
    assert alert.select_one("a.footnote-ref")
    assert f"[!{kind}]" not in alert.text
    assert not doc.select("aside.warning")


def test_footnotes_and_alerts_leave_literals_and_export_intact(cli, put, tmp_path):
    body = ("`[^1]` and `> [!NOTE]`\n\n```text\n[^1]: literal\n> [!WARNING]\n```\n\n"
            "> Ordinary quote\n\n> [!UNKNOWN]\n> Still a quote\n\n"
            "Actual[^1].\n\n[^1]: The note.\n\n> [!NOTE]\n> The alert.\n")
    put("page.md", body)
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert len(doc.select(".markdown-alert")) == 1
    assert "Ordinary quote" in doc.select_one("blockquote").text
    assert "[!UNKNOWN]" in doc.select_one("blockquote").text
    assert len(doc.select(".footnote-ref")) == 1
    assert "[^1]: literal\n> [!WARNING]" in doc.select_one("pre code").text
    cli("page.md", "--jekyll-markdown", "-o", "export.md", "--math", "raw")
    exported = (tmp_path / "export.md").read_text()
    for block in body.strip().split("\n\n"):
        assert block in exported
    assert "footnote-tooltip" not in exported and "markdown-alert" not in exported


def test_adjacent_alerts_and_quotes_remain_separate(cli, put, tmp_path):
    put("page.md", "> Plain before\n\n> [!NOTE]\n> First\n\n> [!WARNING]\n> Second\n\n> Plain after\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert [node.get_text(" ", strip=True) for node in doc.select(".markdown-alert")] == [
        "Note First", "Warning Second",
    ]
    assert [node.text.strip() for node in doc.select("blockquote")] == ["Plain before", "Plain after"]


def test_footnote_in_heading_does_not_duplicate_reference_in_toc(cli, put, tmp_path):
    put("page.md", "@toc\n\n# A heading[^1]\n\n[^1]: Heading note.\n")
    cli("page.md", "--math", "raw")
    doc = read_html(tmp_path / "page.html")
    assert doc.select_one("h1#a-heading .footnote-ref")
    assert doc.select_one('.table-of-contents a[href="#a-heading"]').text == "A heading"
    assert not doc.select(".table-of-contents .footnote-ref")
    ids = [node["id"] for node in doc.select("[id]")]
    assert len(ids) == len(set(ids))


def test_new_feature_assets_are_conditional_and_shared(cli, put, tmp_path):
    put("site/plain.md", "Plain page")
    put("site/notes.md", "Note[^1].\n\n[^1]: Footnote.\n\n> [!TIP]\n> Helpful.\n")
    cli("site", "-o", "public", "--math", "raw")
    plain = read_html(tmp_path / "public/plain.html")
    notes = read_html(tmp_path / "public/notes.html")
    assert not any("footnote" in str(node) or "alert.css" in str(node) for node in plain.select("link, script"))
    assert notes.select_one('link[href="assets/footnote.css"]')
    assert notes.select_one('link[href="assets/alert.css"]')
    assert (tmp_path / "public/assets/footnote.css").is_file()
    assert (tmp_path / "public/assets/alert.css").is_file()
