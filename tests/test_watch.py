import json
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from urllib.request import urlopen

import pytest


def until(check, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (OSError, ConnectionError):
            pass
        time.sleep(0.08)
    raise AssertionError("watch output did not update before the deadline")


@contextmanager
def watching(tmp_path, *arguments):
    with (tmp_path / ".watch.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "md2html", *map(str, arguments)],
            cwd=tmp_path,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            yield process
        finally:
            process.terminate()
            process.wait(timeout=10)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize(
    "destination,target",
    [
        ("default", "notes/my note.html"),
        ("file", "html/custom page.html"),
        ("directory", "html/nested/published/index.html"),
        ("config", "configured/custom page.html"),
    ],
)
def test_single_file_serve_uses_build_destination(put, tmp_path, destination, target):
    put("notes/my note.md", "---\npermalink: /nested/published/\n---\n@include(part.md)\n@src(counter.py)")
    put("notes/part.md", "FIRST")
    put(
        "notes/counter.py",
        'from pathlib import Path\np = Path("counter")\n'
        'p.write_text(str(int(p.read_text()) + 1) if p.exists() else "1")\nprint("RESULT")\n',
    )
    output_args = ()
    if destination == "config":
        put("md2html.json", json.dumps({"output": target}))
    elif destination != "default":
        output_args = ("-o", "html" if destination == "directory" else target)
    with watching(tmp_path, "-es", "notes/my note.md", "--math", "raw", "--port", 0, *output_args):
        log = tmp_path / ".watch.log"
        until(lambda: "Serving http" in log.read_text())
        url = re.search(r"Serving (http://\S+)", log.read_text())[1]
        assert url.endswith(
            "/nested/published/index.html"
            if destination == "directory"
            else "/my%20note.html"
            if destination == "default"
            else "/custom%20page.html"
        )

        def page():
            with urlopen(url, timeout=1) as response:
                return response.read().decode()

        assert "FIRST" in page() and "RESULT" in page()
        assert (tmp_path / target).is_file()
        assert not list(tmp_path.rglob(".md2html-preview"))
        put("notes/part.md", "SECOND")
        until(lambda: "SECOND" in page())
        assert (tmp_path / "notes/counter").read_text() == "1"
        time.sleep(0.5)
        builds = log.read_text().count("Built ")
        with (tmp_path / target).open("a") as output:
            output.write("<!-- output edit -->")
        time.sleep(0.7)
        assert log.read_text().count("Built ") == builds


@pytest.mark.parametrize("directory", [False, True])
def test_restart_serve_racket_cache_and_source_updates(cli, put, tmp_path, directory):
    put("notes/a.md", "@src(example.rkt)\n@src(counter.py)\n")
    put("notes/example.rkt", '#lang racket\n(displayln "RACKET-FIRST")\n')
    put(
        "notes/counter.py",
        'from pathlib import Path\np=Path("counter")\np.write_text(str(int(p.read_text())+1) if p.exists() else "1")\nprint("counter done")\n',
    )
    source = "notes" if directory else "notes/a.md"
    cli("-er", source, "-o", "public", "--math", "raw")
    port = free_port()
    with watching(
        tmp_path, "-ers", source, "-o", "public", "--math", "raw", "--host", "0.0.0.0", "--port", port
    ) as process:

        def page():
            with urlopen(f"http://127.0.0.1:{port}/a.html", timeout=1) as response:
                return response.read().decode()

        until(lambda: "RACKET-FIRST" in page())
        assert (tmp_path / "notes/counter").read_text() == "1"
        put("notes/example.rkt", '#lang racket\n(displayln "RACKET-SECOND")\n')
        until(lambda: "RACKET-SECOND" in page())
        assert (tmp_path / "notes/counter").read_text() == "1"
        assert process.poll() is None


def test_watch_without_server_external_include_and_recovery(cli, put, tmp_path):
    put("external/part.md", "# FIRST")
    put("notes/a.md", "@include(../external/part.md)\n")
    port = free_port()
    with watching(tmp_path, "-w", "notes/a.md", "-o", "public/a.html", "--math", "raw", "--port", port):
        target = tmp_path / "public/a.html"
        until(lambda: target.exists() and "FIRST" in target.read_text())
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
        put("external/part.md", "@src-begin(python)\n")
        until(lambda: "missing @src-end" in (tmp_path / ".watch.log").read_text())
        put("external/part.md", "# RECOVERED")
        until(lambda: "RECOVERED" in target.read_text())


def test_watch_site_listings_rebuild_with_raw_math(put, tmp_path):
    put("notes/index.html", "{% for post in site.posts %}{{post.title}}{% endfor %}")
    put("notes/_posts/2025-01-01-post.md", "---\ntitle: FIRST\n---\npost")
    with watching(tmp_path, "-w", "notes", "-o", "public", "--output-mode", "site", "--math", "raw"):
        target = tmp_path / "public/index.html"
        until(lambda: target.exists() and "FIRST" in target.read_text())
        put("notes/_posts/2025-01-01-post.md", "---\ntitle: SECOND\n---\npost")
        until(lambda: "SECOND" in target.read_text())


def test_watch_pagination_moves_deletes_and_static_assets(cli, put, tmp_path):
    import json

    put("site/blog/index.html", "{% for p in paginator.posts %}{{p.title}};{% endfor %}")
    put("site/unrelated.md", "Independent")
    put("site/_posts/2026-01-01-one.md", "---\ntitle: ONE\n---\nPost")
    put("md2html.json", json.dumps({"site": {"paginate": 1, "paginate_path": "/blog/page:num/"}}))
    args = ("site", "-o", "html", "--output-mode", "site", "--math", "raw")
    cli(*args)
    independent = tmp_path / "html/unrelated.html"
    before = independent.stat().st_mtime_ns
    with watching(tmp_path, *args, "-w"):
        index = tmp_path / "html/blog/index.html"
        second = tmp_path / "html/blog/page2/index.html"
        until(lambda: "Built 0 files" in (tmp_path / ".watch.log").read_text())
        put("site/_posts/2026-01-02-two.md", "---\ntitle: TWO\n---\nPost")
        until(lambda: "TWO" in index.read_text() and "ONE" in second.read_text())
        (tmp_path / "site/_posts/2026-01-01-one.md").rename(tmp_path / "site/_posts/2026-01-03-one.md")
        until(lambda: "ONE" in index.read_text() and "TWO" in second.read_text())
        (tmp_path / "site/_posts/2026-01-03-one.md").unlink()
        until(lambda: "TWO" in index.read_text() and not second.exists())
        put("site/img/share.gif", "UNREFERENCED")
        until(lambda: (tmp_path / "html/img/share.gif").read_text() == "UNREFERENCED")
        assert independent.stat().st_mtime_ns == before


@pytest.mark.parametrize("flag", ["-rw", "-rs"])
def test_recursive_current_directory_ignores_output_events(put, tmp_path, flag):
    put("index.md", "![image](picture.svg)")
    put("picture.svg", "<svg/>")
    put("nested/page.md", "FIRST")
    with watching(tmp_path, flag, ".", "-o", "html", "--math", "raw", "--port", free_port()) as process:
        target = tmp_path / "html/nested/page.html"
        log = tmp_path / ".watch.log"
        until(lambda: "Built " in log.read_text())
        if flag == "-rs":
            until(lambda: "Serving http" in log.read_text())
        else:
            time.sleep(0.3)
        assert 'src="picture.svg"' in (tmp_path / "html/index.html").read_text()
        put("nested/page.md", "SECOND")
        until(lambda: "SECOND" in target.read_text())
        put("node_modules/example/file.js", "UNREFERENCED")
        copied = tmp_path / "html/node_modules/example/file.js"
        until(lambda: copied.read_text() == "UNREFERENCED")
        put("node_modules/example/file.js", "UPDATED")
        until(lambda: copied.read_text() == "UPDATED")
        time.sleep(0.5)
        builds = log.read_text().count("Built ")
        put("html/manual/nested/file.md", "OUTPUT ONLY")
        target.write_text(target.read_text() + "<!-- output edit -->")
        time.sleep(1)
        assert log.read_text().count("Built ") == builds
        assert not (tmp_path / "html/html").exists()
        assert not (tmp_path / "html/manual/nested/file.html").exists()
        assert process.poll() is None
