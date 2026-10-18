import hashlib
import io
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

from md2html import __version__, cli
from md2html import update as updater


@pytest.fixture
def release(monkeypatch, tmp_path):
    target = tmp_path / "installed/md2html"
    target.parent.mkdir()
    target.write_bytes(b"original executable")
    target.chmod(0o751)
    current = updater.version_tuple(__version__)
    version = ".".join(map(str, (*current[:2], current[2] + 1)))
    name = f"md2html-{version}-linux-x86_64"
    prefix = f"https://github.com/{updater.REPOSITORY}/releases/download/v{version}/"
    payload = f"#!/bin/sh\nprintf '%s\\n' 'md2html {version}'\n".encode()
    metadata = dict(
        tag_name="v" + version,
        draft=False,
        prerelease=False,
        assets=[
            dict(name=filename, browser_download_url=prefix + filename) for filename in (name, "SHA256SUMS")
        ],
    )
    responses = {
        f"https://api.github.com/repos/{updater.REPOSITORY}/releases/latest": json.dumps(metadata).encode(),
        prefix + "SHA256SUMS": f"{hashlib.sha256(payload).hexdigest()}  {name}\n".encode(),
        prefix + name: payload,
    }
    requests = []

    def request(url):
        requests.append(url)
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(value) if isinstance(value, bytes) else value

    monkeypatch.setattr(updater, "request", request)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(target))
    monkeypatch.setattr(updater.platform, "system", lambda: "Linux")
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    return target, responses, requests


def test_stable_versions():
    assert updater.version_tuple("v3.10.0") > updater.version_tuple("3.9.9")
    assert updater.version_tuple("v3.0.0") == updater.version_tuple("3.0.0")
    for value in ("3.0", "3.0.1rc1", "v3.0.1-beta", "v03.0.1", "garbage", None):
        with pytest.raises(ValueError):
            updater.version_tuple(value)


@pytest.mark.parametrize("location", ["local/bin", "usr/local/bin", "custom directory"])
def test_update_replaces_real_executable_and_preserves_symlink(release, tmp_path, monkeypatch, location):
    target, responses, requests = release
    destination = tmp_path / location / "renamed-program"
    destination.parent.mkdir(parents=True)
    target.rename(destination)
    target.symlink_to(destination)
    assert updater.update() == 0
    assert target.is_symlink()
    assert destination.read_bytes() == list(responses.values())[-1]
    assert stat.S_IMODE(destination.stat().st_mode) == 0o751
    assert len(requests) == 3
    assert not list(destination.parent.glob(".renamed-program.*"))


@pytest.mark.parametrize(
    "failure",
    ["network", "interrupted", "checksum", "manifest", "permission", "replace", "version", "timeout"],
)
def test_update_failure_preserves_executable(release, monkeypatch, failure):
    target, responses, _ = release
    binary_url = list(responses)[-1]
    if failure == "network":
        responses[binary_url] = URLError("download failed")
    elif failure == "interrupted":

        class Interrupted(io.BytesIO):
            def read(self, count=-1):
                if self.tell():
                    raise URLError("connection lost")
                return super().read(7)

        responses[binary_url] = Interrupted(responses[binary_url])
    elif failure == "checksum":
        responses[binary_url] += b"corrupted"
    elif failure == "manifest":
        responses[list(responses)[1]] = b"not a checksum file"
    elif failure in {"permission", "replace"}:

        def fail(*args, **kwargs):
            raise PermissionError("permission denied")

        monkeypatch.setattr(
            updater.tempfile if failure == "permission" else updater.os,
            "NamedTemporaryFile" if failure == "permission" else "replace",
            fail,
        )
    else:

        def probe(*args, **kwargs):
            if failure == "timeout":
                raise subprocess.TimeoutExpired("download", 30)
            return subprocess.CompletedProcess(args, 0, "md2html 0.0.0", "")

        monkeypatch.setattr(updater.subprocess, "run", probe)
    assert cli.main(["--update"]) == 1
    assert target.read_bytes() == b"original executable"
    assert stat.S_IMODE(target.stat().st_mode) == 0o751
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize("tag", ["v" + __version__, "v0.0.1"])
def test_update_never_downgrades_or_downloads_current_release(release, tag):
    target, responses, requests = release
    url = next(iter(responses))
    metadata = json.loads(responses[url])
    metadata["tag_name"] = tag
    responses[url] = json.dumps(metadata).encode()
    assert updater.update() == 0
    assert len(requests) == 1
    assert target.read_bytes() == b"original executable"


@pytest.mark.parametrize("invalid", ["prerelease", "missing", "foreign-url", "bad-json"])
def test_invalid_release_is_rejected(release, invalid):
    target, responses, _ = release
    url = next(iter(responses))
    metadata = json.loads(responses[url])
    if invalid == "prerelease":
        metadata["prerelease"] = True
    elif invalid == "missing":
        metadata["assets"] = []
    elif invalid == "foreign-url":
        metadata["assets"][0]["browser_download_url"] = "https://example.test/download"
    responses[url] = b"not json" if invalid == "bad-json" else json.dumps(metadata).encode()
    assert cli.main(["-U"]) == 1
    assert target.read_bytes() == b"original executable"


def test_update_bypasses_build_options_and_configuration(release, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "md2html.json").write_text("not json")
    assert cli.main(["--version", "--update", "--config", "missing.json", "--unknown-build-option"]) == 0


def test_non_frozen_and_unsupported_platform_do_not_contact_github(monkeypatch):
    def unexpected(*args):
        pytest.fail("unexpected network request")

    monkeypatch.setattr(updater, "request", unexpected)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert cli.main(["-U"]) == 1
    monkeypatch.setattr(sys, "frozen", True)
    monkeypatch.setattr(updater.platform, "system", lambda: "Darwin")
    assert cli.main(["-U"]) == 1


def test_literal_update_filename_is_not_a_flag(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def unexpected():
        pytest.fail("a filename must not trigger the updater")

    monkeypatch.setattr(cli, "update", unexpected)
    assert cli.main(["--", "--update"]) == 1
    assert "input does not exist" in capsys.readouterr().err


def test_https_downgrade_is_rejected(monkeypatch):
    response = io.BytesIO(b"unsafe")
    response.geturl = lambda: "http://example.test/download"
    monkeypatch.setattr(updater, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match="HTTPS"):
        updater.request("https://example.test/download")
    assert response.closed


def test_global_install_only_copies_existing_binary(tmp_path):
    project = Path(__file__).resolve().parents[1]
    (tmp_path / "makefile").write_text((project / "makefile").read_text())
    destination = tmp_path / "system bin"
    command = ["make", "install-global", "UV=false", "PYTHON=false", f"GLOBAL_BIN={destination}"]
    missing = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert missing.returncode != 0 and "make pyinstaller" in missing.stderr
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/md2html").write_bytes(b"already built")
    subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)
    assert (destination / "md2html").read_bytes() == b"already built"
    assert os.access(destination / "md2html", os.X_OK)
