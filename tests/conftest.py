import subprocess
import sys

import pytest


@pytest.fixture
def cli(tmp_path):
    def invoke(*args, ok=True, cwd=None):
        result = subprocess.run(
            [sys.executable, "-m", "md2html", *map(str, args)],
            cwd=cwd or tmp_path,
            capture_output=True,
            text=True,
            timeout=40,
        )
        if ok:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0, result.stdout + result.stderr
        return result

    return invoke


@pytest.fixture
def put(tmp_path):
    def write(name, text):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    return write
