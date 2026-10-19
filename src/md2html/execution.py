"""Source-text caching and bounded execution in the page's working directory."""

import ctypes
import hashlib
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

import psutil

from .incremental import stamp
from .reporting import ExecutionWarning, local_path

ALIASES = {
    "py": "python",
    "js": "javascript",
    "rkt": "racket",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "sh": "bash",
    "shell": "bash",
    "m": "wl",
    "mathematica": "wl",
}
SUFFIXES = {"python": ".py", "javascript": ".js", "racket": ".rkt", "cpp": ".cpp", "bash": ".sh", "wl": ".wl"}
COMMANDS = {
    "python": "{python} {source}",
    "javascript": "node {source}",
    "racket": "racket {source}",
    "bash": "bash {source}",
    "wl": "wolframscript -file {source}",
    "c": "cc {source} -o {executable} && {executable}",
    "cpp": "c++ {source} -o {executable} && {executable}",
}


def slug(value):
    return re.sub(r"[^\w.-]+", "-", value).strip(".-") or "source"


def terminate(process, existing):
    """Kill the process group and any descendants that started new sessions."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
    deadline = time.monotonic() + 5
    while True:
        children = [
            child
            for child in psutil.Process().children(recursive=True)
            if child.pid not in existing and child.pid != process.pid
        ]
        if not children:
            break
        for child in children:
            try:
                child.kill()
                os.waitpid(child.pid, os.WNOHANG)
            except (psutil.NoSuchProcess, ChildProcessError, ProcessLookupError):
                pass
        if time.monotonic() > deadline:
            raise RuntimeError("could not stop and reap all execution descendants")
        time.sleep(0.01)
    try:
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("execution output remained open after descendant cleanup") from error


def run(build, page, source, code, language, flags, warn):
    if "noexecute" in flags:
        return None
    options = build.options
    language = ALIASES.get(language.lower(), language.lower())
    inline = source is None
    label = slug(source.stem) if source else "inline"
    digest = hashlib.sha256(code.encode()).hexdigest()[:12]
    builddir = page.parent / ".md2html-cache" / slug(page.stem) / f"{language}-{label}-{digest}"
    output = builddir / "output.txt"
    complete = builddir / ".complete"
    build.dependencies.update([output, complete])
    if complete.exists() and output.exists() and not options.force_execution:
        return output.read_text()
    if not options.execute:
        if options.verbose:
            warn(
                f"cached output unavailable for {local_path(source) if source else language + ' inline snippet'}; use --execute to generate it"
            )
        return None
    suffix = SUFFIXES.get(language, "." + language) if inline else source.suffix
    command = (
        options.commands.get(language)
        or options.commands.get(suffix.lstrip("."))
        or options.commands.get(suffix)
        or COMMANDS.get(language)
    )
    if command is None:
        warn(f"no execution command for {language}")
        return None
    if sys.platform == "linux":
        # Adopt orphaned grandchildren so timeout cleanup can reap them.
        if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError("could not enable execution descendant reaping")
    builddir.mkdir(parents=True, exist_ok=True)
    complete.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    name = slug(language if inline else source.stem)
    if inline:
        source = builddir / (name + suffix)
        source.write_text(code)
    python = (
        (shutil.which("python3") or shutil.which("python"))
        if getattr(sys, "frozen", False)
        else sys.executable
    )
    if not python and language == "python":
        warn("Python snippets require python3 or python on PATH")
        return None
    paths = dict(
        source=source,
        filename=source,
        sourcedir=source.parent,
        builddir=builddir,
        executable=builddir / (name + ".md2html-out"),
        output=output,
    )
    substitutions = {key: shlex.quote(os.path.relpath(path, page.parent)) for key, path in paths.items()}
    substitutions.update(python=shlex.quote(python or "python3"), slug=shlex.quote(name))
    try:
        command = command.format_map(substitutions)
        existing = {child.pid for child in psutil.Process().children(recursive=True)}
        with subprocess.Popen(
            ["sh", "-c", command],
            cwd=page.parent,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=options.timeout)
            except subprocess.TimeoutExpired:
                try:
                    terminate(process, existing)
                except (OSError, psutil.Error, subprocess.TimeoutExpired) as error:
                    raise RuntimeError(f"could not complete execution cleanup: {error}") from error
                warn(f"execution timed out after {options.timeout:g}s: {local_path(source)}")
                return None
        if process.returncode:
            warn(
                ExecutionWarning(
                    f"execution failed for {local_path(source)} (exit {process.returncode})",
                    stdout,
                    stderr,
                )
            )
            return None
        if stderr.strip():
            build.diagnostic(f"execution stderr for {local_path(source)}:\n{stderr.rstrip()}")
        if not output.exists():
            output.write_text(stdout)
        complete.touch()
        return output.read_text()
    except (OSError, KeyError, ValueError) as error:
        warn(f"could not execute {local_path(source)}: {error}")
        return None
    finally:
        build.execution_writes.update({path: stamp(path) for path in (output, complete)})
