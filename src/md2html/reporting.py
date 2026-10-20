"""Plain-text build status and diagnostics, independent of generated content."""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path


def local_path(path):
    return os.path.relpath(path)


def local_message(message):
    text = str(message)
    if isinstance(message, OSError):
        for path in (message.filename, message.filename2):
            if path:
                text = text.replace(str(path), local_path(path))
    return text.replace(str(Path.cwd()) + os.sep, "")


def diagnostic_message(message, verbose=False):
    message = local_message(message)
    if verbose or not message:
        return message
    lines = message.splitlines()
    message = lines[0] + (" … " + lines[-1] if len(lines) > 1 else "")
    if len(lines) > 1 or len(message) > 300:
        message = message[:297] + " … (use --verbose for details)"
    return message


def duration(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m" + (f" {seconds}s" if seconds else "")
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h" + (f" {minutes}m" if minutes else "") + (f" {seconds}s" if seconds else "")


class Reporter:
    def __init__(self, build):
        self.build = build
        self.reported = 0
        self.pages = 0

    def warnings(self):
        for message in self.build.warnings[self.reported:]:
            message = diagnostic_message(message, self.build.options.verbose)
            print("warning: " + message, end="" if message.endswith("\n") else "\n", file=sys.stderr, flush=True)
        self.reported = len(self.build.warnings)
        for message in self.build.diagnostics:
            print("warning: " + local_message(message), file=sys.stderr, flush=True)
        self.build.diagnostics.clear()

    @contextmanager
    def page(self, target):
        started = time.perf_counter()
        print(f"Building {local_path(target)}", end="", flush=True)
        status = "Done"
        try:
            yield
        except KeyboardInterrupt:
            status = "Interrupted"
            raise
        except Exception:
            status = "Failed"
            raise
        else:
            self.pages += 1
        finally:
            print(f" ({status}, {duration(time.perf_counter() - started)})", flush=True)
            self.warnings()
