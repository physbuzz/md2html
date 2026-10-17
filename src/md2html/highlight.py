"""Syntax highlighting with one reusable backend per build session."""

import html

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from .config import PACKAGE
from .execution import ALIASES
from .workers import Worker


class Highlighter:
    def __init__(self, options):
        self.worker = (
            Worker(["ruby", str(PACKAGE / "scripts/rouge.rb")]) if options.highlighter == "rouge" else None
        )
        light = options.highlighter_style or ("github.light" if self.worker else "default")
        dark = options.highlighter_dark_style or ("github.dark" if self.worker else "github-dark")
        try:
            light_css, dark_css = (self.style(style) for style in (light, dark))
        except Exception:
            self.close()
            raise
        self.css = (
            light_css
            + "\n@media (prefers-color-scheme: dark) {\n"
            + dark_css
            + "\n}\n"
            + light_css.replace(".codehilite", 'html[data-theme="light"] .codehilite')
            + dark_css.replace(".codehilite", 'html[data-theme="dark"] .codehilite')
        )

    def style(self, name):
        if self.worker:
            return self.worker.request(style=name)["value"]
        return HtmlFormatter(style=name).get_style_defs(".codehilite")

    def code(self, value, language="", fenced=False):
        language = ALIASES.get(language.lower(), language.lower())
        if self.worker:
            tokens = self.worker.request(code=value, language=language)["value"]
        else:
            try:
                lexer = get_lexer_by_name(language)
            except ClassNotFound:
                lexer = TextLexer()
            tokens = highlight(value, lexer, HtmlFormatter(nowrap=True))
        label = "c++" if language == "cpp" else language
        header = f'<div class="code-language">{html.escape(label)}</div>' if fenced and label else ""
        classes = "codehilite fenced-code" if fenced else "codehilite"
        return f'<div class="{classes}">{header}<pre><code>{tokens}</code></pre></div>\n'

    def close(self):
        if self.worker:
            self.worker.close()
