"""Syntax highlighting with one reusable backend per build session."""

import html

from mathematica import MathematicaLexer
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import inherit
from pygments.lexers import TextLexer, get_lexer_by_name, get_lexer_for_filename
from pygments.token import String
from pygments.util import ClassNotFound

from .config import PACKAGE
from .execution import ALIASES
from .highlight_styles import WolframDarkStyle, WolframLightStyle
from .workers import Worker


class WolframLexer(MathematicaLexer):
    """Include escaped newlines in Wolfram string tokens."""

    tokens = {"strings": [(r"\\\r?\n", String), inherit]}


class Highlighter:
    def __init__(self, options):
        self.worker = None
        self.lexers = {}
        self.formatter = HtmlFormatter(nowrap=True)
        if options.highlighter == "rouge":
            try:
                self.worker = Worker(["ruby", str(PACKAGE / "scripts/rouge.rb")])
            except OSError as error:
                raise ValueError(
                    "Rouge highlighting requires Ruby and the rouge gem. Install Ruby and run "
                    "'gem install --user-install rouge', or use '--highlighter pygments'."
                ) from error
        light = options.highlighter_style or ("github.light" if self.worker else "default")
        dark = options.highlighter_dark_style or ("github.dark" if self.worker else "github-dark")
        try:
            light_css, dark_css = (self.style(style) for style in (light, dark))
        except Exception:
            self.close()
            raise
        self.css = (
            "@media (prefers-color-scheme: light) {\n"
            + light_css.replace(".codehilite", 'html:not([data-theme="dark"]) .codehilite')
            + "\n}\n"
            + "\n@media (prefers-color-scheme: dark) {\n"
            + dark_css.replace(".codehilite", 'html:not([data-theme="light"]) .codehilite')
            + "\n}\n"
            + light_css.replace(".codehilite", 'html[data-theme="light"] .codehilite')
            + dark_css.replace(".codehilite", 'html[data-theme="dark"] .codehilite')
        )

    def style(self, name):
        if self.worker:
            return self.worker.request(style=name)["value"]
        wolfram = {"default": WolframLightStyle, "github-dark": WolframDarkStyle}.get(name)
        scope = '.codehilite:not([data-language="wl"])' if wolfram else ".codehilite"
        css = HtmlFormatter(style=name).get_style_defs(scope)
        if wolfram:
            # Layout styles own code-box backgrounds.
            css += "\n" + "\n".join(
                HtmlFormatter(style=wolfram).get_token_style_defs('.codehilite[data-language="wl"]')
            )
        return css

    def code(self, value, language="", fenced=False, filename=None):
        language = ALIASES.get(language.lower(), language.lower())
        if filename:
            try:
                get_lexer_by_name(language)
            except ClassNotFound:
                try:
                    language = get_lexer_for_filename(str(filename)).aliases[0]
                except ClassNotFound:
                    pass
        if self.worker:
            tokens = self.worker.request(code=value, language=language)["value"]
        else:
            if language not in self.lexers:
                try:
                    lexer = (
                        WolframLexer() if language in WolframLexer.aliases else get_lexer_by_name(language)
                    )
                except ClassNotFound:
                    lexer = TextLexer()
                self.lexers[language] = lexer
            tokens = highlight(value, self.lexers[language], self.formatter)
        label = "c++" if language == "cpp" else language
        header = f'<div class="code-language">{html.escape(label)}</div>' if fenced and label else ""
        classes = "codehilite fenced-code" if fenced else "codehilite"
        language = "wl" if language in WolframLexer.aliases else language
        return (
            f'<div class="{classes}" data-language="{html.escape(language)}">'
            f"{header}<pre><code>{tokens}</code></pre></div>\n"
        )

    def close(self):
        if self.worker:
            self.worker.close()
