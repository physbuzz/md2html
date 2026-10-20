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
