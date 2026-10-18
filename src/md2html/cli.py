"""Command-line entry point and dependency-aware watch loop."""

import argparse
import json
import sys
import threading
import time
from functools import partial
from http.client import HTTPException
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from yaml import YAMLError

from . import __version__
from .config import ASSETS, BACKENDS, FONTS, MODES, PACKAGE, resolve
from .project import Build
from .update import update

EXAMPLE = {
    "input": ".",
    "output": "html",
    "output_mode": "site",
    "math": {"backend": "mathjax-chtml"},
    "execute": False,
    "exclude": ["node_modules"],
    "templates": ["_templates"],
    "host": "127.0.0.1",
    "port": 8000,
}


def parser():
    result = argparse.ArgumentParser(
        description="Build Markdown pages with Liquid, math, and executable snippets.", allow_abbrev=False
    )
    result.add_argument("input", nargs="*", default=None)
    result.add_argument("-o", "--output")
    result.add_argument("--config")
    for short, name, help_text in (
        ("v", "verbose", "report additional build diagnostics"),
        ("e", "execute", "execute snippets (successful output is cached)"),
        ("r", "recursive", "include nested source directories"),
        ("f", "force", "render every page even when its inputs are unchanged"),
        ("F", "force-execution", "rerun cached snippets; requires --execute"),
        ("s", "serve", "serve output and watch for changes"),
        ("w", "watch", "watch for changes without starting a server"),
    ):
        result.add_argument("-" + short, "--" + name, action="store_true", default=None, help=help_text)
    result.add_argument(
        "--no-execute",
        dest="execute",
        action="store_false",
        default=None,
        help="disable snippet execution even when configured; reuse saved output",
    )
    result.add_argument("--host", help="preview bind address (default: 127.0.0.1)")
    result.add_argument("-p", "--port", type=int, help="preview port (default: 8000)")
    result.add_argument("--timeout", type=float)
    result.add_argument("--clean", action="store_true", default=None)
    result.add_argument(
        "--output-mode", choices=MODES, help="default: site for directory inputs, pages for listed files"
    )
    result.add_argument(
        "--jekyll",
        dest="output_mode",
        action="store_const",
        const="jekyll",
        help="shortcut for --output-mode jekyll",
    )
    result.add_argument(
        "--jekyll-markdown",
        dest="output_mode",
        action="store_const",
        const="jekyll-markdown",
        help="shortcut for --output-mode jekyll-markdown",
    )
    result.add_argument("--assets", choices=ASSETS)
    result.add_argument(
        "--standalone",
        dest="assets",
        action="store_const",
        const="standalone",
        help="shortcut for --assets standalone",
    )
    result.add_argument("--math", choices=BACKENDS)
    result.add_argument("--math-fonts", choices=FONTS)
    result.add_argument("--template")
    result.add_argument(
        "--template-dir",
        dest="templates",
        action="append",
        metavar="DIR",
        help="add a template search directory; repeat in lookup order",
    )
    for flag, dest in (("css", "css"), ("stylesheet", "stylesheets")):
        result.add_argument("--" + flag, dest=dest, action="append")
    for flag, dest in (
        ("no-feature-css", "feature_css"),
        ("no-minify-css", "minify_css"),
        ("no-liquid", "parse_liquid"),
    ):
        result.add_argument("--" + flag, dest=dest, action="store_false", default=None)
    result.add_argument(
        "--no-default-css",
        action="store_true",
        help="omit base and feature styling; retain authored stylesheets and math-renderer styles",
    )
    result.add_argument("--highlighter", choices=("pygments", "rouge"))
    result.add_argument("--highlighter-style")
    result.add_argument("--highlighter-dark-style")
    for name in ("config", "template", "css"):
        result.add_argument("--example-" + name, metavar="PATH", help="write example, or - for stdout")
    result.add_argument("--readme", action="store_true")
    result.add_argument("-U", "--update", action="store_true", help="update the release executable and exit")
    result.add_argument("--version", action="version", version="md2html " + __version__)
    return result


def report(build):
    paths = build.build()
    for warning in build.warnings:
        print("warning: " + warning, file=sys.stderr, flush=True)
    print(f"Built {len(paths)} files in {build.output_root}", flush=True)


class Changes(FileSystemEventHandler):
    def __init__(self, build):
        self.build = build
        self.changed = threading.Event()

    def on_any_event(self, event):
        if event.event_type not in {"modified", "created", "deleted", "moved"} or event.is_directory:
            return
        for name in (event.src_path, getattr(event, "dest_path", "")):
            if not name:
                continue
            path = Path(name).resolve()
            if any(part.startswith(".") for part in path.parts) and path not in self.build.dependencies:
                continue
            if path in self.build.owners or (
                not self.build.output_file and path.is_relative_to(self.build.output_root)
            ):
                continue
            self.changed.set()


def watch(build):
    events = Changes(build)
    observer = Observer()
    watched = set()

    def subscribe():
        paths = [*build.options.input, *build.template_dirs, *build.dependencies]
        for path in paths:
            root = path if path.is_dir() else path.parent
            while not root.exists():
                root = root.parent
            if not any(root.is_relative_to(previous) for previous in watched):
                observer.schedule(events, str(root), recursive=True)
                watched.add(root)

    subscribe()
    observer.start()
    server = None
    try:
        if build.options.serve:
            server = ThreadingHTTPServer(
                (build.options.host, build.options.port),
                partial(SimpleHTTPRequestHandler, directory=str(build.output_root)),
            )
            threading.Thread(target=server.serve_forever, daemon=True).start()
            path = (
                build.url(build.entrypoint, build.output_root)
                if build.entrypoint != build.output_root
                else ""
            )
            print(f"Serving http://{build.options.host}:{server.server_port}/{path}", flush=True)
        while True:
            if events.changed.wait(0.3):
                time.sleep(0.1)
                events.changed.clear()
                try:
                    report(build)
                    subscribe()
                except (OSError, ValueError, YAMLError) as error:
                    print(f"error: {error}", file=sys.stderr, flush=True)
    finally:
        observer.stop()
        observer.join()
        if server:
            server.shutdown()
            server.server_close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        options = argv[: argv.index("--")] if "--" in argv else argv
        if "-U" in options or "--update" in options:
            return update()
        args = vars(parser().parse_args(argv))
        if args.pop("update"):
            return update()
        if args.pop("readme"):
            path = PACKAGE / "readme.md"
            if not path.exists():
                path = PACKAGE.parent.parent / "readme.md"
            if not path.exists():
                path = Path(sys.prefix) / "share/md2html/readme.md"
            print(path.read_text())
            return 0
        examples = {
            "config": json.dumps(EXAMPLE, indent=2) + "\n",
            "template": (PACKAGE / "default_templates/page.html").read_text(),
            "css": (PACKAGE / "assets/page-base.css").read_text(),
        }
        for name, text in examples.items():
            destination = args.pop("example_" + name)
            if destination:
                if destination == "-":
                    print(text, end="")
                else:
                    if Path(destination).exists() and not args.get("force"):
                        raise ValueError(f"file exists: {destination}; use --force to overwrite")
                    Path(destination).write_text(text)
                return 0
        if args.pop("no_default_css"):
            args.update(css=[], feature_css=False)
        if not args["input"]:
            args["input"] = None
        options = resolve(args)
        build = Build(options)
        try:
            report(build)
            if options.watch or options.serve:
                watch(build)
        finally:
            build.close()
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, HTTPException, YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
