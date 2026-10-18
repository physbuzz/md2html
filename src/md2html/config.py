"""Resolve configuration paths and command-line precedence once."""

import json
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

MODES = ("pages", "site", "jekyll", "jekyll-markdown")
BACKENDS = ("mathjax-chtml", "mathjax", "svg", "mathml", "raw")
FONTS = ("auto", "inline", "local", "remote", "none")
ASSETS = ("standalone", "shared", "cdn")
PACKAGE = Path(__file__).parent
MARKDOWN = {".md", ".markdown"}
DOCUMENTS = MARKDOWN | {".html", ".htm", ".xml"}


def values(value):
    return [value] if isinstance(value, str) else list(value or [])


@dataclass
class Options:
    input: list[Path] = field(default_factory=list)
    output: Path | None = None
    root: Path = field(default_factory=Path.cwd)
    output_mode: str = "pages"
    recursive: bool = False
    verbose: bool = False
    execute: bool = False
    force: bool = False
    force_execution: bool = False
    timeout: float = 120
    clean: bool = False
    watch: bool = False
    serve: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    assets: str = "auto"
    math: str = "mathjax-chtml"
    math_fonts: str = "auto"
    template: str = "page.html"
    templates: list[Path] = field(default_factory=list)
    css: list[str] | None = None
    stylesheets: list[str] = field(default_factory=list)
    feature_css: bool = True
    minify_css: bool = True
    parse_liquid: bool = True
    highlighter: str = "pygments"
    highlighter_style: str | None = None
    highlighter_dark_style: str | None = None
    exclude: list[str] = field(default_factory=list)
    images: dict = field(default_factory=dict)
    frontmatter: dict = field(default_factory=dict)
    commands: dict = field(default_factory=dict)
    site: dict = field(default_factory=dict)

    @property
    def site_mode(self):
        return self.output_mode in {"site", "jekyll"}

    @property
    def markdown_mode(self):
        return self.output_mode == "jekyll-markdown"


def resolve(cli):
    cli = dict(cli)
    config = cli.pop("config", None)
    if config is None:
        config = next(
            (p / "md2html.json" for p in (Path.cwd(), *Path.cwd().parents) if (p / "md2html.json").is_file()),
            None,
        )
    raw = {}
    root = Path.cwd()
    if config:
        config = Path(config).resolve()
        if config.suffix != ".json":
            raise ValueError("configuration must be a JSON file")
        raw = json.loads(config.read_text())
        if not isinstance(raw, dict):
            raise ValueError("configuration must contain an object")
        root = config.parent
    for name in ("images", "frontmatter", "commands", "site"):
        if name in raw and not isinstance(raw[name], dict):
            raise ValueError(f"{name} must contain an object")
    math = raw.get("math", "mathjax-chtml")
    if isinstance(math, dict):
        raw["math_fonts"] = math.get("chtml_fonts", "auto")
        raw["math"] = math.get("backend", "mathjax-chtml")
    elif not isinstance(math, str):
        raise ValueError("math must be a backend name or object")
    for source, base in ((raw, root), (cli, Path.cwd())):
        for name in ("input", "templates", "css", "stylesheets", "exclude"):
            if name in source and source[name] is not None:
                if not isinstance(source[name], (str, list, tuple)):
                    raise ValueError(f"{name} must be a string or list")
                source[name] = values(source[name])
        for name in ("input", "templates", "css"):
            if source.get(name) is not None:
                source[name] = [str((base / Path(p).expanduser()).resolve()) for p in source[name]]
        if source.get("stylesheets"):
            source["stylesheets"] = [
                str((base / name).resolve()) if not re.match(r"[\w+.-]+:|/", name) else name
                for name in source["stylesheets"]
            ]
        if source.get("output"):
            source["output"] = (base / Path(source["output"]).expanduser()).resolve()
    data = raw | {key: value for key, value in cli.items() if value is not None}
    known = {item.name for item in fields(Options)}
    data["site"] = data.get("site", {}) | {key: value for key, value in data.items() if key not in known}
    options = Options(**{key: value for key, value in data.items() if key in known})
    options.root = root
    options.input = [Path(p) for p in options.input] or [root]
    if "output_mode" not in data:
        options.output_mode = "site" if any(path.is_dir() for path in options.input) else "pages"
    options.templates = [Path(p) for p in options.templates]
    if not config and len(options.input) == 1:
        options.root = options.input[0] if options.input[0].is_dir() else options.input[0].parent
    if options.output is None and (len(options.input) > 1 or options.input[0].is_dir()):
        options.output = root / (
            "_site" if options.site_mode else "markdown" if options.markdown_mode else "html"
        )
    if options.output_mode != "pages":
        options.recursive = True
    if options.assets == "auto":
        options.assets = "shared" if options.site_mode or options.markdown_mode else "standalone"
    if options.site_mode and options.assets == "standalone":
        options.assets = "shared"
    for name, choices in (
        ("output_mode", MODES),
        ("math", BACKENDS),
        ("math_fonts", FONTS),
        ("assets", ASSETS),
        ("highlighter", ("pygments", "rouge")),
    ):
        if getattr(options, name) not in choices:
            raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    if options.force_execution and not options.execute:
        raise ValueError("--force-execution requires --execute")
    for item in fields(Options):
        if item.type is bool and not isinstance(getattr(options, item.name), bool):
            raise ValueError(f"{item.name} must be true or false")
    if not isinstance(options.timeout, (int, float)):
        raise ValueError("timeout must be a number")
    if not isinstance(options.port, int) or not 0 <= options.port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    if options.timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if not all(isinstance(command, str) for command in options.commands.values()):
        raise ValueError("commands must map languages to command strings")
    return options
