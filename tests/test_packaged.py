"""Run with MD2HTML_TEST_COMMAND pointing to an installed wheel or executable."""

import os
import shlex
import subprocess

import pytest
from bs4 import BeautifulSoup


@pytest.mark.skipif(
    not os.environ.get("MD2HTML_TEST_COMMAND"), reason="requires an installed package command"
)
@pytest.mark.parametrize("backend", ["mathjax-chtml", "svg", "mathml"])
def test_installed_command_outside_checkout(tmp_path, backend):
    command = shlex.split(os.environ["MD2HTML_TEST_COMMAND"])
    source = tmp_path / "installed.md"
    source.write_text(
        "# Installed\n$x^2+1$\n"
        "@src-begin(python)\nprint('INSTALLED-PYTHON')\n@src-end\n"
        '@src-begin(racket)\n#lang racket\n(displayln "INSTALLED-RACKET")\n@src-end\n'
    )
    result = subprocess.run(
        command + ["-e", "--math", backend, str(source)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    doc = BeautifulSoup(source.with_suffix(".html").read_text(), "html.parser")
    assert [box.get_text(strip=True) for box in doc.select(".code-output")] == [
        "Output:INSTALLED-PYTHON",
        "Output:INSTALLED-RACKET",
    ]
    assert doc.select(".math-rendered")
    assert not doc.select(".warning")
    if backend == "mathjax-chtml":
        assert "data:font/woff2;base64," in str(doc)
    readme = subprocess.run(command + ["--readme"], cwd=tmp_path, text=True, capture_output=True, timeout=30)
    assert readme.returncode == 0 and "Yet Another" in readme.stdout
