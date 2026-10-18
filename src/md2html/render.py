"""Directives, protected Liquid evaluation, and a single Markdown render."""

import html
import re
import uuid

import mistune
import yaml
from liquid.exceptions import LiquidError

from . import execution

DIRECTIVE = re.compile(r"^\s*@(src-begin|src|include)\((.*?)\)\s*(?:#.*)?$")
END = re.compile(r"^\s*@src-end\s*(?:#.*)?$")
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\n]*)\n", re.M)
MATH = re.compile(
    r"(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<![\\$])\$(?!\$)([^\n]+?)(?<!\\)\$(?!\$)|"
    r"\\begin\{(align\*?|gather\*?|multline\*?|equation\*?)\}.*?\\end\{\3\}",
    re.S,
)


def frontmatter(text):
    if not re.match(r"\A---[ \t]*\n", text):
        return {}, text
    match = re.match(r"\A---[ \t]*\n(.*?)^---[ \t]*(?:\n|$)", text, re.S | re.M)
    if not match:
        raise ValueError("front matter is missing its closing ---")
    metadata = yaml.safe_load(match[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("front matter must contain a mapping")
    return metadata, text[match.end() :]


def slugify(value):
    value = html.unescape(re.sub(r"<[^>]*>", "", value)).strip().lower()
    return re.sub(r"[\s-]+", "-", re.sub(r"[^\w\s-]", "", value)) or "section"


class Stash:
    def __init__(self):
        self.prefix = "MD2HTML" + uuid.uuid4().hex.upper()
        self.items = {}

    def put(self, value):
        token = self.prefix + "X" + str(len(self.items)) + "Z"
        self.items[token] = value
        return token

    def restore(self, text):
        for token, value in reversed(self.items.items()):
            text = text.replace(token, value)
        return text


def liquid_render(environment, text, context, warn):
    text = re.sub(r"{%\s*include\s+([\w./-]+)\s*%}", r"{% include '\1' %}", text)
    try:
        return environment.from_string(text).render(**context)
    except (LiquidError, RecursionError) as error:
        warn(f"Liquid rendering failed: {error}")
        return text


class Renderer(mistune.HTMLRenderer):
    def __init__(self, document):
        super().__init__(escape=False)
        self.document = document
        self.headings = []
        self.seen = {}

    def heading(self, text, level, **attrs):
        base = slugify(self.document.html.restore(text))
        number = self.seen.get(base, 0) + 1
        self.seen[base] = number
        identifier = base if number == 1 else f"{base}-{number}"
        self.headings.append((level, self.document.html.restore(text), identifier))
        return f'<h{level} id="{identifier}">{text}</h{level}>\n'

    def block_code(self, code, info=None):
        self.document.features.add("code")
        language = (info or "").split()[0] if info else ""
        # Directives are macros even inside a fence; render the intervening code normally.
        chunks = re.split(f"({self.document.html.prefix}X[0-9]+Z)", code)
        return "".join(
            chunk
            if chunk in self.document.html.items
            else self.document.build.highlighter.code(chunk, language, True)
            for chunk in chunks
            if chunk.strip()
        )

    def image(self, text, url, title=None):
        self.document.features.add("image")
        return super().image(text, url, title)


class Document:
    def __init__(self, build, page):
        self.build = build
        self.options = build.options
        self.page = page
        self.html = Stash()
        self.features = set()
        self.fonts = set()
        self.warnings = []
        self.toc_token = self.html.put("")

    def warn(self, message, *, at_end=True):
        if at_end:
            self.warnings.append(message)
        self.build.warnings.append(f"{self.page.source}: {message}")
        self.features.add("warning")

    def block(self, markup):
        return "\n\n" + self.html.put(markup) + "\n\n"

    def reference(self, name, origin):
        path = (origin.parent / name).resolve()
        if not path.exists():
            fallback = (self.options.root / name).resolve()
            if fallback.exists():
                path = fallback
        self.build.dependencies.add(path)
        return path

    def source_box(self, source, code, language, flags):
        self.features.add("code")
        markup = self.build.highlighter.code(code, language, filename=source)
        label = html.escape(source.name if source else f"{language} source")
        if source:
            href = self.build.asset_link(source, self.page.target.parent)
            label = f'<a href="{html.escape(href, quote=True)}">{label}</a>'
        if flags & {"collapsed", "collapsible", "expanded"}:
            opened = "" if "collapsed" in flags else " open"
            markup = f'<details class="collapsible-code"{opened}><summary class="code-summary"><span>{label}</span><span class="expand-hint">(click to expand)</span></summary>{markup}</details>'
        else:
            markup = f'<div class="code-header">{label}</div>{markup}'
        warnings = []
        output = execution.run(self.build, self.page.source, source, code, language, flags, warnings.append)
        if output is not None:
            markup += f'<div class="code-output"><span>Output:</span><pre>{html.escape(output)}</pre></div>'
        if not self.options.execute:
            self.build.warnings.extend(f"{self.page.source}: {warning}" for warning in warnings)
            warnings = []
        for warning in warnings:
            self.warn(warning, at_end=False)
            markup += f'<aside class="warning">{html.escape(warning)}</aside>'
        classes = "code-box" if source else "code-box inline-source"
        return self.block(f'<div class="{classes}">{markup}</div>')

    def preprocess(self, body, origin, stack=()):
        lines = iter(enumerate(body.splitlines(keepends=True), 1))
        result = []
        for number, line in lines:
            if END.fullmatch(line.strip()):
                raise ValueError(f"unexpected @src-end in {origin}:{number}")
            match = DIRECTIVE.fullmatch(line.strip())
            if match:
                kind, arguments = match.groups()
                name, *flags = [value.strip().strip("\"'") for value in arguments.split(",")]
                if kind == "src-begin":
                    code = []
                    for end_number, code_line in lines:
                        if END.fullmatch(code_line.strip()):
                            break
                        if re.match(r"\s*@src-begin\(", code_line):
                            raise ValueError(f"nested @src-begin in {origin}:{end_number}")
                        code.append(code_line)
                    else:
                        raise ValueError(f"missing @src-end in {origin}:{number}")
                    result.append(self.source_box(None, "".join(code), name, set(flags)))
                else:
                    path = self.reference(name, origin)
                    try:
                        if kind == "include" and path in (*stack, origin):
                            raise OSError(f"include cycle: {path}")
                        value = path.read_text()
                    except OSError as error:
                        self.warn(str(error))
                        result.append(self.block(f'<aside class="warning">{html.escape(str(error))}</aside>'))
                        continue
                    if kind == "src":
                        result.append(self.source_box(path, value, path.suffix.lstrip("."), set(flags)))
                    else:
                        _, value = frontmatter(value)
                        result.append(self.preprocess(value, path, (*stack, origin)))
            elif re.fullmatch(r"\s*@toc\s*(?:#.*)?", line.strip()):
                self.features.add("toc")
                result.append("\n\n" + self.toc_token + "\n\n")
            else:
                if re.match(r"\s*@(?:src|include)\b", line):
                    self.warn(f"malformed directive at {origin}:{number}")
                # Included Markdown references retain their fragment's directory.
                if origin != self.page.source:

                    def rebase(match):
                        name = match[2]
                        if re.match(r"[\w+.-]+:|[/#]", name):
                            return match[0]
                        return match[1] + str((origin.parent / name).resolve()) + match[3]

                    line = re.sub(r"(!?\[[^\]]*\]\()([^\s)]+)(\))", rebase, line)
                    line = re.sub(
                        r"(!\[\[)([^|\]]+)(?=[|\]])",
                        lambda m: m[1] + str((origin.parent / m[2]).resolve()),
                        line,
                    )
                result.append(line)
        return "".join(result)

    def protect_code(self, body, protected):
        position = 0
        output = []
        while match := FENCE.search(body, position):
            output.append(body[position : match.start()])
            close = re.compile(
                r"^ {0,3}" + re.escape(match[2][0]) + "{" + str(len(match[2])) + r",}[ \t]*$", re.M
            )
            end = close.search(body, match.end())
            stop = end.end() if end else len(body)
            output.append("\n\n" + protected.put(body[match.start() : stop]) + "\n\n")
            position = stop
        output.append(body[position:])
        body = "".join(output)

        def literal(match):
            if match["language"] and not self.options.markdown_mode:
                return self.block(self.build.highlighter.code(match["code"], match["language"], True))
            return protected.put(match[0])

        body = re.sub(
            r"<(pre|code)\b[^>]*>.*?</\1>|<!--.*?-->|"
            r"{%\s*highlight\s+(?P<language>\S+)\s*%}(?P<code>.*?){%\s*endhighlight\s*%}",
            literal,
            body,
            flags=re.S | re.I,
        )
        body = re.sub(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)", lambda m: protected.put(m[0]), body, flags=re.S)
        # A display may contain indented TeX lines; only shield indentation outside math.
        body = re.sub(
            MATH.pattern + r"|(?P<indented>(?:^(?: {4}|\t)[^\n]*(?:\n|$))+)",
            lambda m: protected.put(m[0]) if m["indented"] else m[0],
            body,
            flags=re.M | re.S,
        )
        return body

    def obsidian(self, match):
        self.features.add("image")
        name, *parts = [part.strip() for part in match[1].split("|")]
        attrs = dict(self.options.images)
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                attrs[key] = (str(attrs.get(key, "")) + " " + value).strip() if key == "class" else value
            elif re.fullmatch(r"\d+(?:\.\d+)?(?:%|px|em|rem)?", part):
                attrs["width"] = part
            else:
                attrs["alt"] = part
        path = self.reference(name, self.page.source)
        url = (
            name
            if re.match(r"[\w+.-]+://", name)
            else self.build.asset_link(path, self.page.target.parent, media=True)
        )
        width = str(attrs.get("width") or "")
        if width.isdigit():
            width += "px"
        style = (
            f' style="width:{html.escape(width, quote=True)}"'
            if re.fullmatch(r"\d+(?:\.\d+)?(?:%|px|em|rem)", width)
            else ""
        )
        classes = html.escape("obsidian-image " + str(attrs.get("class") or ""), quote=True)
        return self.html.put(
            f'<img class="{classes}" src="{html.escape(url, quote=True)}" alt="{html.escape(str(attrs.get("alt") or ""), quote=True)}"{style}>'
        )

    def toc(self, headings):
        roots, exercises = [], []
        stack = [(0, roots)]
        for level, title, identifier in headings:
            plain = html.unescape(re.sub(r"<[^>]+>", "", title)).lower()
            if plain == "solution":
                continue
            link = f'<a href="#{identifier}">{title}</a>'
            if re.match(r"exercise\b", plain):
                exercises.append(f"<span>{link}</span>")
                continue
            while stack[-1][0] >= level:
                stack.pop()
            children = []
            stack[-1][1].append((plain, link, children))
            stack.append((level, children))
        exercise_list = '<span class="exercise-list">' + "".join(exercises) + "</span>"

        def listing(nodes):
            items = []
            for title, link, children in nodes:
                extra = (
                    ' <div class="exercise-container">(' + exercise_list + ")</div>"
                    if title == "exercises" and exercises
                    else ""
                )
                items.append("<li>" + link + extra + (listing(children) if children else "") + "</li>")
            return '<ul class="toc-list">' + "".join(items) + "</ul>"

        tail = (
            exercise_list
            if exercises
            and not any(
                html.unescape(re.sub(r"<[^>]+>", "", title)).lower() == "exercises"
                for _, title, _ in headings
            )
            else ""
        )
        return '<div class="table-of-contents"><h2>Directory</h2>' + listing(roots) + tail + "</div>"

    def render(self, context):
        body = self.preprocess(self.page.body, self.page.source)
        protected = Stash()
        body = self.protect_code(body, protected)
        if not self.options.markdown_mode:
            body = MATH.sub(
                lambda m: self.html.put(
                    self.build.math.render(m[1] or m[2] or m[0], bool(m[1] or m[3]), self)
                ),
                body,
            )
        body = re.sub(r"!\[\[([^\]\n]+)\]\]", self.obsidian, body)
        if (
            self.options.parse_liquid
            and self.page.data.get("render_with_liquid", True)
            and not self.options.markdown_mode
        ):
            body = liquid_render(self.build.liquid, body, context, self.warn)
        body = protected.restore(body)
        renderer = Renderer(self)
        plugins = [] if self.options.markdown_mode else ["table", "strikethrough", "task_lists", "url"]
        rendered = mistune.create_markdown(renderer=renderer, plugins=plugins)(body)
        if not self.options.markdown_mode:
            body = rendered
        self.html.items[self.toc_token] = self.toc(renderer.headings)
        # Block macros must not be wrapped in paragraph elements by Markdown.
        body = re.sub(r"<p>(" + self.html.prefix + r"X[0-9]+Z)</p>", r"\1", body)
        body = self.html.restore(body)
        if self.warnings:
            body += "".join(
                f'<aside class="warning">{html.escape(warning)}</aside>' for warning in self.warnings
            )
        return body
