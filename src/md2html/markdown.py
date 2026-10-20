"""Python-Markdown hooks for code highlighting and document navigation."""

import re

from markdown import Markdown
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
    """Render fences after Liquid, including fences supplied by variables or includes."""

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
            markup = self.renderer.document.block_code(code, match[3].strip())
            output.append("\n\n" + self.renderer.document.html.put(markup) + "\n\n")
            position = stop
        output.append(body[position:])
        return "".join(output).split("\n")


class Renderer(Treeprocessor):
    def __init__(self, document, slugify):
        extensions = [] if document.options.markdown_mode else [
            TableExtension(),
            DeleteSubExtension(subscript=False),
            TasklistExtension(),
            MagiclinkExtension(),
        ]
        super().__init__(Markdown(extensions=extensions, output_format="html"))
        self.md.preprocessors.register(FencedCode(self.md, self), "md2html_fences", 35)
        self.md.treeprocessors.register(self, "md2html", -5)
        self.document = document
        self.slugify = slugify
        self.headings = []
        self.seen = {}

    def run(self, root):
        for node in root.iter():
            if node.tag == "pre" and len(node) == 1 and node[0].tag == "code":
                # Decode only the three entities escaped by Markdown's code processor.
                code = (node[0].text or "").replace("&lt;", "<").replace("&gt;", ">")
                code = code.replace("&amp;", "&")
                markup = self.document.block_code(code)
                tail = node.tail
                node.clear()
                node.tag = "p"
                node.text = self.md.htmlStash.store(markup)
                node.tail = tail
            elif node.tag == "img":
                self.document.features.add("image")
            elif re.fullmatch(r"h[1-6]", node.tag):
                tail, node.tail = node.tail, None
                text = self.md.serializer(node).split(">", 1)[1].rsplit("</", 1)[0]
                node.tail = tail
                for processor in self.md.postprocessors:
                    text = processor.run(text)
                node.set("id", self.heading(text, int(node.tag[1])))

    def heading(self, text, level):
        text = self.document.html.restore(text)
        base = self.slugify(text)
        number = self.seen.get(base, 0) + 1
        self.seen[base] = number
        identifier = base if number == 1 else f"{base}-{number}"
        self.headings.append((level, text, identifier))
        return identifier

    def render(self, body):
        return self.md.convert(body)
