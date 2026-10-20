"""Python-Markdown hooks for code highlighting and document navigation."""

import re

from markdown import Markdown
from markdown.extensions import Extension
from markdown.extensions.tables import TableExtension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from pymdownx.magiclink import MagiclinkExtension
from pymdownx.tasklist import TasklistExtension
from pymdownx.tilde import DeleteSubExtension

FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\n]*)\n", re.M)


def fenced_blocks(body, position=0):
    while match := FENCE.search(body, position):
        close = re.compile(
            r"^ {0,3}" + re.escape(match[2][0]) + "{" + str(len(match[2])) + r",}[ \t]*$", re.M
        )
        end = close.search(body, match.end())
        stop = end.end() if end else len(body)
        yield match, end.start() if end else len(body), stop
        position = stop


class FencedCode(Preprocessor):
    def __init__(self, md, renderer):
        super().__init__(md)
        self.renderer = renderer

    def run(self, lines):
        body = "\n".join(lines)
        output, position = [], 0
        for match, end, stop in fenced_blocks(body):
            output.append(body[position : match.start()])
            code = body[match.end() : end]
            if match[1]:
                code = re.sub(r"^ {0," + str(len(match[1])) + "}", "", code, flags=re.M)
            markup = self.renderer.block_code(code, match[3].strip())
            output.append("\n\n" + self.renderer.document.html.put(markup) + "\n\n")
            position = stop
        output.append(body[position:])
        return "".join(output).split("\n")


class IndentedCode(Treeprocessor):
    def __init__(self, md, renderer):
        super().__init__(md)
        self.renderer = renderer

    def run(self, root):
        for node in root.iter("pre"):
            if len(node) == 1 and node[0].tag == "code":
                # Decode only the three entities escaped by Markdown's code processor.
                code = (node[0].text or "").replace("&lt;", "<").replace("&gt;", ">")
                code = code.replace("&amp;", "&")
                markup = self.renderer.block_code(code)
                tail = node.tail
                node.clear()
                node.tag = "p"
                node.text = self.md.htmlStash.store(markup)
                node.tail = tail


class Structure(Treeprocessor):
    def __init__(self, md, renderer):
        super().__init__(md)
        self.renderer = renderer

    def run(self, root):
        for node in root.iter():
            if node.tag == "img":
                self.renderer.document.features.add("image")
            elif re.fullmatch(r"h[1-6]", node.tag):
                tail, node.tail = node.tail, None
                text = self.md.serializer(node).split(">", 1)[1].rsplit("</", 1)[0]
                node.tail = tail
                for processor in self.md.postprocessors:
                    text = processor.run(text)
                node.set("id", self.renderer.heading(text, int(node.tag[1])))


class Renderer(Extension):
    def __init__(self, document, slugify):
        super().__init__()
        self.document = document
        self.slugify = slugify
        self.headings = []
        self.seen = {}

    def extendMarkdown(self, md):
        # Use document placeholders so fences survive Markdown whitespace normalization.
        md.preprocessors.register(FencedCode(md, self), "md2html_fences", 35)
        md.treeprocessors.register(IndentedCode(md, self), "md2html_code", 25)
        md.treeprocessors.register(Structure(md, self), "md2html_structure", -5)

    def heading(self, text, level):
        text = self.document.html.restore(text)
        base = self.slugify(text)
        number = self.seen.get(base, 0) + 1
        self.seen[base] = number
        identifier = base if number == 1 else f"{base}-{number}"
        self.headings.append((level, text, identifier))
        return identifier

    def block_code(self, code, info=None):
        self.document.features.add("code")
        language = (info or "").split()[0] if info else ""
        token = self.document.html.prefix + r"X[0-9]+Z"
        # Raw HTML occurring in Markdown code blocks is source text, not a macro.
        code = re.sub(
            token,
            lambda m: self.document.html.items[m[0]] if m[0] in self.document.literal_html else m[0],
            code,
        )
        # Directives are macros even inside a fence; render the intervening code normally.
        chunks = re.split(f"({token})", code)
        return "".join(
            chunk
            if chunk in self.document.html.items
            else self.document.build.highlighter.code(chunk, language, True)
            for chunk in chunks
            if chunk.strip()
        )

    def render(self, body):
        extensions = [self]
        if not self.document.options.markdown_mode:
            extensions.extend(
                [
                    TableExtension(),
                    DeleteSubExtension(subscript=False),
                    TasklistExtension(),
                    MagiclinkExtension(),
                ]
            )
        return Markdown(extensions=extensions, output_format="html").convert(body)
