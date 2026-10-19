"""Dependencies of completed outputs; no intermediate document content is stored."""

import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from liquid import Environment as LiquidEnvironment
from liquid import FileSystemLoader
from liquid.exceptions import LiquidError

from .config import PACKAGE
from .reporting import local_path


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def stamp(path):
    try:
        stat = path.stat()
        return [stat.st_mtime_ns, stat.st_size]
    except OSError:
        return None


class Templates(FileSystemLoader):
    def get_source(self, env, template_name, **kwargs):
        for directory in self.search_path:
            path = directory / template_name
            env.build.dependencies.add(path)
            if path.is_file():
                break
        return super().get_source(env, template_name, **kwargs)


class Environment(LiquidEnvironment):
    def from_string(self, source, *args, **kwargs):
        template = super().from_string(source, *args, **kwargs)
        try:
            analysis = template.analyze(include_partials=False)
            for variable in analysis.globals.get("site", []):
                name = variable.segments[1] if len(variable.segments) > 1 else None
                self.build.collections.update([name] if isinstance(name, str) else self.build.collection_keys)
        except LiquidError:
            # Unknown Liquid syntax must not hide changes to site listings.
            self.build.collections.update(self.build.collection_keys)
        return template


class State:
    def __init__(self, build):
        self.build = build
        self.root = build.output_root
        self.path = self.root / ".md2html-cache/build.json"
        try:
            self.records = json.loads(self.path.read_text())
            if not isinstance(self.records, dict):
                raise ValueError("expected an object")
            if any(not isinstance(record, dict) for record in self.records.values()):
                raise ValueError("expected output records to be objects")
        except FileNotFoundError:
            self.records = {}
        except (OSError, ValueError) as error:
            build.diagnostic(f"cannot read build cache {local_path(self.path)}; rebuilding: {error}")
            self.records = {}
        settings = asdict(build.options)
        for key in ("watch", "serve", "force", "force_execution", "clean", "host", "port"):
            settings.pop(key)
        implementation = {
            str(p.relative_to(PACKAGE)): stamp(p)
            for p in PACKAGE.rglob("*")
            if p.suffix in {".py", ".css", ".html", ".mjs", ".rb"}
        }
        if getattr(sys, "frozen", False):
            implementation = {"executable": stamp(Path(sys.executable))}
        self.settings = signature([settings, build.site_config, implementation])
        self.scope = signature([build.options.input, build.options.output_mode, build.options.output])
        self.collections = {key: signature(build.site[key]) for key in build.collection_keys}

    def relative(self, path):
        return os.path.relpath(path, self.root)

    def current(self, page):
        record = self.records.get(self.relative(page.target), {})
        self.build.dependencies.update(self.root / name for name in record.get("dependencies", {}))
        return (
            not (self.build.options.force or self.build.options.force_execution or self.build.options.clean)
            and page.target.is_file()
            and record.get("settings") == self.settings
            and record.get("collections")
            == {key: self.collections[key] for key in record.get("collections", {})}
            and all(
                stamp(self.root / name) == value for name, value in record.get("dependencies", {}).items()
            )
            and all((self.root / name).is_file() for name in record.get("outputs", []))
        )

    def remember(self, page):
        self.records[self.relative(page.target)] = dict(
            settings=self.settings,
            scope=self.scope,
            stamp=stamp(page.target),
            dependencies={
                self.relative(path): stamp(path)
                for path in self.build.dependencies
                if not path.is_relative_to(PACKAGE.resolve())
            },
            collections={
                key: self.collections[key] for key in self.build.collections & self.collections.keys()
            },
            outputs=[self.relative(path) for path in self.build.products],
        )

    def save(self):
        for name, record in list(self.records.items()):
            target = (self.root / name).resolve()
            if record.get("scope") == self.scope and target not in self.build.owners:
                if target.is_relative_to(self.root) and stamp(target) == record.get("stamp"):
                    target.unlink(missing_ok=True)
                elif target.is_relative_to(self.root) and target.exists():
                    self.build.diagnostic(f"keeping modified obsolete output: {local_path(target)}")
                del self.records[name]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.records, indent=2, sort_keys=True) + "\n")
        temporary.replace(self.path)
