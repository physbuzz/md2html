"""Verified, atomic replacement of a packaged executable from stable releases."""

import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from . import __version__

REPOSITORY = "physbuzz/md2html"


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError(f"expected a stable version such as v3.0.1, got {value!r}")
    return tuple(map(int, value.removeprefix("v").split(".")))


def request(url):
    response = urlopen(Request(url, headers={"User-Agent": "md2html/" + __version__}), timeout=30)
    if not response.geturl().startswith("https://"):
        response.close()
        raise ValueError("update download redirected away from HTTPS")
    return response


def update():
    if not getattr(sys, "frozen", False):
        raise ValueError(
            "self-update requires a release executable; update this Python installation with its package manager"
        )
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValueError("release updates currently support only Linux x86-64")
    target = Path(sys.executable).resolve(strict=True)
    with request(f"https://api.github.com/repos/{REPOSITORY}/releases/latest") as response:
        release = json.loads(response.read(2 * 1024 * 1024))
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise ValueError("GitHub did not return a stable release")
    tag = release.get("tag_name")
    latest = version_tuple(tag)
    if not tag.startswith("v"):
        raise ValueError("release tags must start with v")
    if latest <= version_tuple(__version__):
        print(f"md2html {__version__} is up to date.")
        return 0
    name = f"md2html-{tag[1:]}-linux-x86_64"
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("release asset list is invalid")

    def asset_url(filename):
        matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == filename]
        url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}"
        if len(matches) != 1 or matches[0].get("browser_download_url") != url:
            raise ValueError(f"release is missing its expected asset: {filename}")
        return url

    binary_url = asset_url(name)
    with request(asset_url("SHA256SUMS")) as response:
        checksums = response.read(65536).decode("utf-8")
    expected = re.findall(r"^([a-fA-F0-9]{64})  " + re.escape(name) + r"$", checksums, re.M)
    if len(expected) != 1:
        raise ValueError(f"release has no unique SHA-256 checksum for {name}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix="." + target.name + ".", delete=False
        ) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            with request(binary_url) as response:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(block)
                    if size > 512 * 1024 * 1024:
                        raise ValueError("update exceeds the executable size limit")
                    output.write(block)
                    digest.update(block)
            if not size or digest.hexdigest() != expected[0].lower():
                raise ValueError("update checksum mismatch; executable left unchanged")
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), stat.S_IMODE(target.stat().st_mode))
        result = subprocess.run(
            [str(temporary), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            env=os.environ | {"PYINSTALLER_RESET_ENVIRONMENT": "1"},
        )
        if result.returncode or result.stdout.strip() != "md2html " + tag[1:]:
            raise ValueError("downloaded executable failed its version check; executable left unchanged")
        os.replace(temporary, target)
    except subprocess.TimeoutExpired as error:
        raise ValueError("downloaded executable timed out; executable left unchanged") from error
    except PermissionError as error:
        raise PermissionError(
            f"cannot update {target}; have an administrator install the release, or use a user-writable installation"
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Updated md2html to {tag[1:]} at {target}.")
    return 0
