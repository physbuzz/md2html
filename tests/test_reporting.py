"""Progress reflects actual work and diagnostics respect verbosity."""

import json

import pytest

from md2html.cli import report
from md2html.config import resolve
from md2html.project import Build
from md2html.reporting import duration


@pytest.mark.parametrize("verbose", [False, True])
def test_relative_progress_and_silent_unchanged_pages(cli, put, tmp_path, verbose):
    put("notes/a.md", "A")
    put("notes/b.md", "B")
    args = ("notes", "-o", "out", "--math", "raw", *(("-v",) if verbose else ()))
    first = cli(*args)
    assert "Building out/a.html (Done, " in first.stdout
    assert "Building out/b.html (Done, " in first.stdout
    assert "Built 2 pages in out" in first.stdout
    assert str(tmp_path) not in first.stdout + first.stderr
    targets = [tmp_path / "out/a.html", tmp_path / "out/b.html"]
    stamps = [path.stat().st_mtime_ns for path in targets]
    forced = cli(*args, "--force")
    assert forced.stdout.count("(Done, ") == 2
    assert "Built 2 pages in out" in forced.stdout
    assert [path.stat().st_mtime_ns for path in targets] == stamps
    second = cli(*args)
    assert "out/a.html" not in second.stdout + second.stderr
    assert "out/b.html" not in second.stdout + second.stderr
    assert "Built 0 pages" in second.stdout
    assert not second.stderr


def test_page_timing_includes_execution_and_write(put, monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    put("a.md", "@src-begin(python)\npass\n@src-end")
    clock = [0.0]
    monkeypatch.setattr("md2html.reporting.time.perf_counter", lambda: clock[0])

    def execute(*args):
        assert capsys.readouterr().out.endswith("Building a.html")
        clock[0] += 600
        return "result"

    monkeypatch.setattr("md2html.execution.run", execute)
    build = Build(resolve({"input": ["a.md"], "math": "raw"}))
    original_write = build.write

    def write(*args):
        original_write(*args)
        clock[0] += 2

    monkeypatch.setattr(build, "write", write)
    try:
        report(build)
        output = capsys.readouterr().out
        assert "(Done, 10m 2s)" in output
        assert "(10m 2s)" in output
        report(build, initial=False)
        assert capsys.readouterr().out == ""
    finally:
        build.close()


@pytest.mark.parametrize("seconds,expected", [(0.1, "0.1s"), (600, "10m"), (3601, "1h 1s"), (3720, "1h 2m")])
def test_duration(seconds, expected):
    assert duration(seconds) == expected


def test_failed_page_is_not_reported_as_done(cli, put, tmp_path):
    put("a.md", "@src-begin(python)\n")
    result = cli("a.md", "--math", "raw", ok=False)
    assert "Building a.html (Failed, " in result.stdout
    assert "Done" not in result.stdout
    assert "missing @src-end in a.md:1" in result.stderr
    assert str(tmp_path) not in result.stderr


@pytest.mark.parametrize("verbose", [False, True])
def test_subprocess_diagnostics(cli, put, verbose):
    put("a.md", "@src(fail.py)\n@src(success.py)")
    put("fail.py", "import sys\nprint('FULL STDOUT')\nsys.stderr.write('DETAIL\\nFINAL ERROR\\n')\nsys.exit(7)")
    put("success.py", "import sys\nsys.stderr.write('SUCCESS STDERR\\n')\nprint('OK')")
    result = cli("a.md", "--math", "raw", "-e", *(("-v",) if verbose else ()))
    failure = (
        "warning: a.md: execution failed for fail.py (exit 7)\n"
        "stdout:\nFULL STDOUT\nstderr:\nDETAIL\nFINAL ERROR\n"
    )
    assert result.stderr.startswith(failure)
    assert ("SUCCESS STDERR" in result.stderr) == verbose
    assert result.stderr.count("warning: ") == 1 + int(verbose)
    assert "execution output for" not in result.stderr


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("stream", ["stdout", "stderr", "neither"])
def test_failed_program_output_is_preserved(cli, put, tmp_path, verbose, stream):
    put("a.md", "@src(fail.py)")
    detail = f'  error at "{tmp_path}/fail.py": ' + "x" * 400 + "\n\n  context...:\n\tend  \n\n"
    write = f"sys.{stream}.write({detail!r})\n" if stream != "neither" else ""
    put("fail.py", "import sys\n" + write + "sys.exit(1)\n")
    result = cli("a.md", "--math", "raw", "-e", *(("-v",) if verbose else ()))
    expected = "warning: a.md: execution failed for fail.py (exit 1)\n"
    if stream != "neither":
        expected += detail
    assert result.stderr == expected


@pytest.mark.parametrize("cache", ["{bad json", "[]", '{"a.html": 42}'])
@pytest.mark.parametrize("verbose", [False, True])
def test_unusable_cache_diagnostic(cli, put, verbose, cache):
    put("a.md", "A")
    put(".md2html-cache/build.json", cache)
    result = cli("a.md", "--math", "raw", *(("-v",) if verbose else ()))
    assert ("cannot read build cache .md2html-cache/build.json; rebuilding" in result.stderr) == verbose


@pytest.mark.parametrize("verbose", [False, True])
def test_highlighting_fallback_diagnostic(cli, put, verbose):
    put("a.md", "```not-a-real-language\ntext\n```\n```not-a-real-language\nmore\n```\n```\nplain\n```")
    result = cli("a.md", "--math", "raw", *(("-v",) if verbose else ()))
    assert result.stderr.count("unknown highlighting language 'not-a-real-language'") == int(verbose)
    assert "language ''" not in result.stderr


@pytest.mark.parametrize("verbose", [False, True])
def test_modified_obsolete_output_diagnostic(cli, put, tmp_path, verbose):
    source = put("notes/a.md", "A")
    put("notes/b.md", "B")
    args = ("notes", "-o", "out", "--math", "raw", *(("-v",) if verbose else ()))
    cli(*args)
    source.unlink()
    output = put("out/a.html", "User edit")
    result = cli(*args)
    assert ("keeping modified obsolete output: out/a.html" in result.stderr) == verbose
    assert output.read_text() == "User edit"
    assert "a.html" not in json.loads((tmp_path / "out/.md2html-cache/build.json").read_text())


def test_external_missing_include_uses_relative_path(cli, put, tmp_path):
    put("notes/a.md", "@include(../missing file.md)")
    result = cli("a.md", "--math", "raw", cwd=tmp_path / "notes")
    assert "could not read ../missing file.md" in result.stderr
    assert str(tmp_path) not in result.stderr


@pytest.mark.parametrize("verbose", [False, True])
def test_multiline_error_details_require_verbose(cli, put, verbose):
    put("a.md", "---\ntitle: [\n---\nA")
    result = cli("a.md", "--math", "raw", *(("-v",) if verbose else ()), ok=False)
    assert (len(result.stderr.splitlines()) > 1) == verbose
    assert ("use --verbose for details" in result.stderr) != verbose


def test_warnings_before_a_fatal_error_are_reported_once(cli, put):
    put("a.md", "@include(missing.md)\n@src-begin(python)\n")
    result = cli("a.md", "--math", "raw", ok=False)
    assert result.stderr.count("could not read missing.md") == 1
    assert "missing @src-end" in result.stderr
