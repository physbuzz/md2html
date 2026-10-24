"""Syntax highlighting with one reusable backend per build session."""

import html
import re
from html.parser import HTMLParser

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
from .metamath import MetamathLexer
from .workers import Worker


class WolframLexer(MathematicaLexer):
    """Include escaped newlines in Wolfram string tokens."""

    tokens = {"strings": [(r"\\\r?\n", String), inherit]}


class HighlightUsage(HTMLParser):
    """Collect conservatively: authored markup and template content count too."""

    def __init__(self, body):
        super().__init__()
        self.classes = set()
        self.scopes = set()
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        self.classes.update(classes)
        if "codehilite" in classes:
            self.scopes.add("wolfram" if attrs.get("data-language") == "wl" else "regular")

    def prune(self, css):
        # Only recognize selectors emitted by our highlighters. Keep unfamiliar
        # selectors intact, including complex selectors from custom Rouge themes.
        selector = re.compile(
            r'\.codehilite(?P<scope>:not\(\[data-language="wl"\]\)|\[data-language="wl"\])?'
            r"(?:\s+\.(?P<token>[\w-]+))?"
        )

        def rule(match):
            selectors = []
            for value in match[1].split(","):
                parsed = selector.fullmatch(value.strip())
                if not parsed:
                    return match[0]
                if parsed["scope"]:
                    language = "regular" if parsed["scope"].startswith(":not") else "wolfram"
                    if language not in self.scopes:
                        continue
                if parsed["token"] is None or parsed["token"] in self.classes:
                    selectors.append(value.strip())
            return ", ".join(selectors) + " {" + match[2] + "}" if selectors else ""

        # These are generated theme styles, never user-authored stylesheets.
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        return re.sub(r"([^{}]+)\{([^{}]*)\}", rule, css)


class Highlighter:
    def __init__(self, options, diagnostic=None):
        self.worker = None
        self.diagnostic = diagnostic
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
            self.light_css, self.dark_css = (self.style(style) for style in (light, dark))
        except Exception:
            self.close()
            raise
        self.css = self.themed(self.light_css, self.dark_css)

    @staticmethod
    def themed(light_css, dark_css):
        def scope(css, selector):
            return selector + " {\n" + css + "\n}\n"

        return (
            "@media (prefers-color-scheme: light) {\n"
            + scope(light_css, 'html:not([data-theme="dark"])')
            + "}\n"
            + "\n@media (prefers-color-scheme: dark) {\n"
            + scope(dark_css, 'html:not([data-theme="light"])')
            + "}\n"
            + scope(light_css, 'html[data-theme="light"]')
            + scope(dark_css, 'html[data-theme="dark"]')
        )

    def css_for(self, body):
        usage = HighlightUsage(body)
        return self.themed(usage.prune(self.light_css), usage.prune(self.dark_css))

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
        if language in MetamathLexer.aliases:
            language = "metamath"
        if filename and language != "metamath":
            try:
                get_lexer_by_name(language)
            except ClassNotFound:
                try:
                    language = (
                        "metamath"
                        if str(filename).lower().endswith(".mm")
                        else get_lexer_for_filename(str(filename)).aliases[0]
                    )
                except ClassNotFound:
                    pass
        if self.worker:
            tokens = self.worker.request(code=value, language=language)["value"]
        else:
            if language not in self.lexers:
                try:
                    if language == "metamath":
                        lexer = MetamathLexer()
                    elif language in WolframLexer.aliases:
                        lexer = WolframLexer()
                    else:
                        lexer = get_lexer_by_name(language)
                except ClassNotFound:
                    lexer = TextLexer()
                    if language and self.diagnostic:
                        self.diagnostic(f"unknown highlighting language {language!r}; using plain text")
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
