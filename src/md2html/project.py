"""A complete build plan for pages, static files, and generated assets."""

import hashlib
import html
import math
import os
import re
import shutil
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET

import yaml

from . import assets
from .config import DOCUMENTS, MARKDOWN, PACKAGE, values
from .highlight import Highlighter
from .incremental import Environment, State, Templates, stamp
from .math import Math
from .render import Document, frontmatter, liquid_render, slugify


@dataclass
class Page:
    source: Path
    relative: Path
    target: Path
    body: str
    data: dict
    metadata: dict
    paginator: dict | None = None


def output_path(url):
    url = unquote(url)
    if ".." in Path(url).parts or urlsplit(url).scheme or url.startswith("//"):
        raise ValueError(f"invalid output URL: {url}")
    return Path(url.lstrip("/")) / "index.html" if url.endswith("/") else Path(url.lstrip("/"))


class Build:
    def __init__(self, options):
        self.options = options
        self.source_root = Path(os.path.commonpath([p if p.is_dir() else p.parent for p in options.input]))
        self.single = len(options.input) == 1 and options.input[0].is_file()
        self.in_place = options.output is None
        self.output_file = (
            self.single and not self.in_place and bool(options.output.suffix) and not options.output.is_dir()
        )
        self.output_root = (
            options.output.parent if self.output_file else options.output or self.source_root
        ).resolve()
        self.dependencies = set()
        self.products = set()
        self.collections = set()
        self.collection_keys = {"posts", "pages", "tags", "categories", "tag_list", "category_list"}
        self.warnings = []
        self.owners = {}
        self.copied = set()
        self.written = []
        self.site_config = {}
        config = self.source_root / "_config.yml"
        if options.output_mode == "jekyll" and config.exists():
            self.site_config = yaml.safe_load(config.read_text()) or {}
            if not isinstance(self.site_config, dict):
                raise ValueError("_config.yml must contain a mapping")
        self.site_config.update(options.site)
        self.template_dirs = [
            *options.templates,
            options.root / "_templates",
            self.source_root / "_includes",
            self.source_root / "_layouts",
            PACKAGE / "default_templates",
        ]
        self.liquid = Environment(loader=Templates(self.template_dirs), autoescape=False)
        self.liquid.build = self
        self.liquid.context_depth_limit = 30
        self.liquid.add_filter("relative_url", self.relative_url)
        self.liquid.add_filter(
            "absolute_url",
            lambda value: str(self.site_config.get("url", "")).rstrip("/") + self.relative_url(value),
        )
        self.highlighter = Highlighter(options)
        self.math = Math(options)

    def close(self):
        self.math.close()
        self.highlighter.close()

    def relative_url(self, value):
        return str(self.site_config.get("baseurl", "")).rstrip("/") + "/" + str(value or "").lstrip("/")

    def url(self, target, directory):
        return quote(os.path.relpath(target, directory).replace(os.sep, "/"), safe="/:@")

    def claim(self, target, owner):
        target = target.resolve()
        if not target.is_relative_to(self.output_root):
            raise ValueError(f"output escapes destination: {target}")
        previous = self.owners.setdefault(target, owner)
        if previous != owner:
            self.warnings.append(f"output collision at {target}: {previous} and {owner}; skipping {owner}")
            return None
        if target in self.source_files:
            self.warnings.append(f"output would overwrite source: {target}; skipping")
            return None
        return target

    def write(self, target, text, owner):
        target = self.claim(target, owner)
        if target is None:
            return
        self.products.add(target)
        data = text.encode("utf-8")
        if target.is_file() and target.read_bytes() == data:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name("." + target.name + ".md2html-tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        self.written.append(target)

    def copy(self, source, target):
        source, target = source.resolve(), target.resolve()
        if source == target:
            return
        if self.claim(target, str(source)) is None:
            return
        self.products.add(target)
        if target in self.copied or target.is_file() and stamp(source) == stamp(target):
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        self.copied.add(target)

    def asset_link(self, source, directory, *, media=False):
        source = source.resolve()
        self.dependencies.add(source)
        if not source.is_file():
            return self.url(source, directory)
        if self.options.assets == "standalone" and (not media or self.options.images.get("embed", True)):
            return assets.data_url(source)
        if self.in_place or self.output_root == self.source_root and self.output_file:
            return self.url(source, directory)
        if source.is_relative_to(self.source_root):
            relative = source.relative_to(self.source_root)
        else:
            digest = hashlib.sha256(str(source).encode()).hexdigest()[:10]
            relative = Path("assets/files") / digest / source.name
        target = self.output_root / relative
        self.copy(source, target)
        return self.url(target, directory)

    def excluded(self, path, root):
        relative = path.relative_to(root)
        if (
            not self.in_place and not self.output_file and path.is_relative_to(self.output_root)
        ) or relative == Path("md2html.json"):
            return True

        def matches(patterns):
            return any(
                relative.is_relative_to(pattern.strip("/")) or relative.match(pattern.strip("/"))
                for pattern in patterns
            )

        if matches([*self.options.exclude, *values(self.site_config.get("exclude"))]):
            return True
        if self.options.output_mode == "jekyll":
            if matches(values(self.site_config.get("include", [".htaccess"]))):
                return False
            if matches(
                [
                    "gemfiles",
                    "Gemfile",
                    "Gemfile.lock",
                    "node_modules",
                    "vendor/bundle",
                    "vendor/cache",
                    "vendor/gems",
                    "vendor/ruby",
                ]
            ):
                return True
            return any(
                part != "_posts" and (part.startswith((".", "_", "#", "~")) or part.endswith("~"))
                for part in relative.parts
            )
        return any(part.startswith(".") for part in relative.parts) or any(
            part.startswith("_") and part != "_posts" for part in relative.parts[:-1]
        )

    def discover(self):
        pages, static = [], []
        self.source_files = set()
        multiple_dirs = sum(path.is_dir() for path in self.options.input) > 1
        for source in self.options.input:
            if not source.exists():
                raise ValueError(f"input does not exist: {source}")
            if not self.in_place and source.is_dir() and source.is_relative_to(self.output_root):
                raise ValueError("output directory must not contain an input directory")
            paths = source.glob("**/*" if self.options.recursive else "*") if source.is_dir() else [source]
            for path in sorted(paths):
                if self.in_place and source.is_dir() and path.suffix.lower() not in MARKDOWN:
                    continue
                if not path.is_file() or source.is_dir() and self.excluded(path, source):
                    continue
                path = path.resolve()
                if path in self.source_files:
                    continue
                self.source_files.add(path)
                root = source.parent if source.is_file() or multiple_dirs else source
                relative = path.relative_to(
                    root if multiple_dirs or len(self.options.input) == 1 else self.source_root
                )
                if path.suffix.lower() not in DOCUMENTS:
                    if source.is_file():
                        raise ValueError(f"unsupported page type: {path}")
                    static.append((path, self.output_root / relative))
                    continue
                text = path.read_text()
                data, body = frontmatter(text)
                metadata = dict(data)
                post = "_posts" in relative.parts
                if self.options.output_mode == "jekyll":
                    if data.get("published") is False:
                        continue
                    if not text.startswith("---\n") and not post and path.name != "feed.xml":
                        static.append((path, self.output_root / relative))
                        continue
                if self.options.markdown_mode and path.suffix.lower() not in MARKDOWN:
                    static.append((path, self.output_root / relative))
                    continue
                data = (self.options.frontmatter if self.options.markdown_mode else {}) | data
                data.setdefault("title", path.name)
                data.update(name=path.name, path=relative.as_posix())
                for key in ("tags", "categories"):
                    names = data.get(key, data.get("tag" if key == "tags" else "category", []))
                    data[key] = re.split(r"[,\s]+", names) if isinstance(names, str) else values(names)
                data.setdefault(
                    "excerpt",
                    next(
                        (
                            p.strip().lstrip("# ")
                            for p in body.split("\n\n")
                            if p.strip() and not p.startswith(("@", "{%"))
                        ),
                        "",
                    ),
                )
                output = relative.with_suffix(".html") if path.suffix.lower() in MARKDOWN else relative
                url = (
                    "/" + (output.parent.as_posix().strip(".") + "/").lstrip("/")
                    if output.name == "index.html"
                    else "/" + output.as_posix()
                )
                dated = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.+)", path.stem) if post else None
                if dated:
                    year, month, day, title = dated.groups()
                    data.setdefault("date", f"{year}-{month}-{day}")
                    data.setdefault("slug", slugify(title))
                    default = (
                        "date" if self.options.output_mode == "jekyll" else "/:year/:month/:day/:title.html"
                    )
                    url = str(self.site_config.get("permalink", default))
                    url = {
                        "pretty": "/:categories/:year/:month/:day/:title/",
                        "date": "/:categories/:year/:month/:day/:title.html",
                    }.get(url, url)
                    for name, value in dict(
                        year=year,
                        month=month,
                        day=day,
                        title=data["slug"],
                        slug=data["slug"],
                        categories="/".join(data["categories"]),
                    ).items():
                        url = url.replace(":" + name, value)
                    url = re.sub("/+", "/", url)
                data["date"] = str(
                    data.get("date", datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
                )
                url = str(data.get("permalink") or url)
                target = self.output_root / output_path(url)
                if self.options.markdown_mode:
                    target = self.output_root / relative
                if self.in_place:
                    target = path.with_suffix(".html") if path.suffix.lower() in MARKDOWN else path
                    url = "/" + target.relative_to(self.output_root).as_posix()
                elif self.output_file:
                    target = self.options.output
                if target.resolve() == path:
                    self.warnings.append(f"source and output are the same file: {path}; skipping")
                    continue
                data["url"] = "/" + url.lstrip("/")
                if post:
                    data.setdefault("id", data["url"].rstrip("/") or "/")
                pages.append(Page(path, relative, target, body, data, metadata))
        self.site = self.site_config | {"time": datetime.now(timezone.utc), "pages": [p.data for p in pages]}
        self.site.setdefault("title", self.source_root.name)
        posts = sorted(
            (p.data for p in pages if "_posts" in p.relative.parts), key=lambda p: p["date"], reverse=True
        )
        self.site["posts"] = posts
        if self.options.output_mode == "jekyll":
            self.site["pages"] = [p.data for p in pages if "_posts" not in p.relative.parts]
        for key in ("tags", "categories"):
            groups = {}
            for post in posts:
                for name in post[key]:
                    groups.setdefault(name, []).append(post)
            self.site[key] = groups
            self.site["tag_list" if key == "tags" else "category_list"] = [
                dict(name=name, slug=slugify(name), posts=group, size=len(group))
                for name, group in sorted(groups.items())
            ]
        per_page = int(self.site.get("paginate") or 0)
        if self.options.site_mode and per_page:
            pattern = str(self.site.get("paginate_path", "/page:num/"))
            prefix = pattern.split(":num")[0]
            indexes = [p for p in pages if p.relative.stem == "index" and prefix.startswith(p.data["url"])]
            index = max(indexes, key=lambda p: len(p.data["url"]), default=None)
            posts = [post for post in posts if not post.get("hidden", False)]
            if not index or ":num" not in pattern or per_page < 1:
                raise ValueError(
                    "pagination requires an index page above paginate_path, positive paginate, and :num in paginate_path"
                )
            total = max(1, math.ceil(len(posts) / per_page))
            urls = [
                index.data["url"],
                *[pattern.replace(":num", str(number)) for number in range(2, total + 1)],
            ]
            pages.remove(index)
            for number, url in enumerate(urls, 1):
                paginator = dict(
                    page=number,
                    per_page=per_page,
                    total_posts=len(posts),
                    total_pages=total,
                    posts=posts[(number - 1) * per_page : number * per_page],
                    previous_page=number - 1 if number > 1 else None,
                    next_page=number + 1 if number < total else None,
                    previous_page_path=urls[number - 2] if number > 1 else None,
                    next_page_path=urls[number] if number < total else None,
                )
                pages.append(
                    replace(
                        index,
                        target=self.output_root / output_path(url),
                        data=index.data | {"url": url},
                        paginator=paginator,
                    )
                )
        pages = [page for page in pages if self.claim(page.target, str(page.source)) is not None]
        static = [
            (source, target) for source, target in static if self.claim(target, str(source)) is not None
        ]
        return pages, static

    def lookup(self, name, page=None, *, layout=False, template=False):
        directories = (
            self.template_dirs
            if template or layout
            else [
                self.options.root,
                *([page.source.parent] if page else []),
                *self.template_dirs,
                PACKAGE / "assets",
            ]
        )
        for directory in directories:
            for filename in (name, str(name) + ".html") if layout else (name,):
                path = (directory / filename).resolve()
                self.dependencies.add(path)
                if path.is_file():
                    return path
        raise FileNotFoundError(f"file not found: {name}")

    def relocate(self, text, page):
        def resolve(name):
            parsed = urlsplit(name)
            if parsed.scheme or parsed.netloc or not parsed.path:
                return name
            # Generated links already resolve to a planned output file.
            if (
                self.options.assets != "standalone"
                and (page.target.parent / unquote(parsed.path)).resolve() in self.owners
            ):
                return name
            source = (page.source.parent / unquote(parsed.path)).resolve()
            if parsed.path.startswith("/") and not source.is_file():
                source = self.source_root / unquote(parsed.path).lstrip("/")
            self.dependencies.add(source)
            if not source.is_file() or source.suffix.lower() in DOCUMENTS:
                return name
            return parsed._replace(path=self.asset_link(source, page.target.parent, media=True)).geturl()

        return assets.relocate(text, resolve)

    def render_page(self, page):
        document = Document(self, page)
        context = dict(page=page.data, site=self.site, paginator=page.paginator)
        if page.source.suffix.lower() in MARKDOWN:
            body = document.render(context)
        else:
            body = (
                liquid_render(self.liquid, page.body, context, document.warn)
                if self.options.parse_liquid and page.data.get("render_with_liquid", True)
                else page.body
            )
        if self.options.markdown_mode:
            return (
                "---\n"
                + yaml.safe_dump(self.options.frontmatter | page.metadata, sort_keys=False)
                + "---\n"
                + body
            )
        layout = page.data.get("layout")
        if page.source.suffix.lower() not in MARKDOWN and not layout:
            return self.relocate(body, page)
        template = None
        if page.source.suffix.lower() in MARKDOWN and not layout:
            try:
                template = self.lookup(
                    str(page.data.get("template", self.options.template)), page, template=True
                )
            except FileNotFoundError as error:
                document.warn(str(error))
        context["md2html"] = assets.context(self, page, document, template)
        body = self.relocate(body, page)
        seen = set()
        while layout and layout != "none":
            try:
                path = self.lookup(str(layout), page, layout=True)
            except FileNotFoundError as error:
                document.warn(str(error))
                break
            if path in seen:
                document.warn(f"layout cycle: {path}")
                break
            seen.add(path)
            metadata, text = frontmatter(path.read_text())
            body = liquid_render(
                self.liquid, text, context | {"content": body, "layout": metadata}, document.warn
            )
            layout = metadata.get("layout")
        if template:
            body = liquid_render(
                self.liquid, template.read_text(), context | {"content": body}, document.warn
            )
        fields = context["md2html"]
        if fields["uses_mathjax_chtml"] and (
            any(html.escape(url, quote=True) not in body for url in fields["math_stylesheets"])
            or fields["math_css"]
            and fields["math_css"] not in body
        ):
            document.warn(
                "layout omits generated CommonHTML styles; provide equivalent author CSS or include "
                "md2html.math_stylesheets and "
                "md2html.math_css (see --example-template -)"
            )
        return assets.prune_highlighting(self, document, body)

    def feed(self):
        namespace = "http://www.w3.org/2005/Atom"
        ET.register_namespace("", namespace)
        root = ET.Element("{" + namespace + "}feed")

        def field(parent, name, value):
            ET.SubElement(parent, "{" + namespace + "}" + name).text = str(value)

        def absolute(url):
            return str(self.site.get("url", "")).rstrip("/") + self.relative_url(url)

        field(root, "title", self.site.get("title", self.source_root.name))
        posts = self.site["posts"][:20]

        def timestamp(value):
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).isoformat()

        field(root, "id", absolute("/feed.xml"))
        ET.SubElement(root, "{" + namespace + "}link", rel="self", href=absolute("/feed.xml"))
        field(
            root,
            "updated",
            timestamp(posts[0]["date"])
            if posts
            else timestamp(max((p["date"] for p in self.site["pages"]), default="1970-01-01")),
        )
        author = self.site.get("author") or self.site["title"]
        author = author if isinstance(author, dict) else {"name": author}
        node = ET.SubElement(root, "{" + namespace + "}author")
        field(node, "name", author.get("name") or self.site["title"])
        for key, value in dict(email=author.get("email"), uri=author.get("uri") or author.get("url")).items():
            if value:
                field(node, key, value)
        for post in posts:
            entry = ET.SubElement(root, "{" + namespace + "}entry")
            for key, value in dict(
                title=post["title"],
                id=absolute(post["url"]),
                updated=timestamp(post["date"]),
            ).items():
                field(entry, key, value)
            ET.SubElement(entry, "{" + namespace + "}link", href=absolute(post["url"]))
        return ET.tostring(root, encoding="unicode")

    def build(self):
        self.warnings.clear()
        self.owners.clear()
        self.copied.clear()
        self.written.clear()
        self.dependencies.clear()
        pages, static = self.discover()
        self.entrypoint = pages[0].target if self.single and pages else self.output_root
        # Validate the complete output plan before removing or writing anything.
        if self.options.clean and self.options.site_mode and self.output_root.exists():
            if any(source.is_relative_to(self.output_root) for source in self.options.input):
                raise ValueError("clean output must not contain input")
            shutil.rmtree(self.output_root)
        state = State(self)
        watched = set(self.dependencies)
        for page in pages:
            self.dependencies = {page.source}
            self.products.clear()
            self.collections = {"posts"} if page.paginator else set()
            if not state.current(page):
                # Only dependencies observed for this render belong to the new output.
                self.dependencies = {page.source}
                self.write(page.target, self.render_page(page), str(page.source))
                state.remember(page)
            watched.update(self.dependencies)
        self.dependencies = watched
        for source, target in static:
            self.copy(source, target)
        feed = self.output_root / "feed.xml"
        if self.options.site_mode and feed not in self.owners:
            self.write(feed, self.feed(), "generated feed")
        state.save()
        return self.written
