"""Run with MD2HTML_TEST_COMMAND pointing to an installed wheel or executable."""

import os
import shlex
import subprocess

import pytest
from bs4 import BeautifulSoup


@pytest.mark.skipif(
    not os.environ.get("MD2HTML_TEST_COMMAND"), reason="requires an installed package command"
)
@pytest.mark.parametrize(
    "style,color", [("default", None), ("mathematica", "#353F42"), ("mathematicanotebook", "#000")]
)
def test_installed_wolfram_highlighting_without_ruby(tmp_path, style, color):
    command = shlex.split(os.environ["MD2HTML_TEST_COMMAND"])
    source = tmp_path / "wolfram.md"
    code = 'Integrate[f[x], x]; MyFunction[a.b]; "continued ' + "\\\n" + 'string";\n'
    source.write_text("```mathematica\n" + code + "```\n")
    result = subprocess.run(
        command + ["--math", "raw", "--highlighter-style", style, "--no-minify-css", str(source)],
        cwd=tmp_path,
        env={**os.environ, "PATH": ""},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    doc = BeautifulSoup(source.with_suffix(".html").read_text(), "html.parser")
    assert not result.stderr and not doc.select(".err")
    assert doc.select_one("pre code").text == code
    assert doc.select_one(".nb").text == "Integrate"
    assert any(span.text == "MyFunction" for span in doc.select(".nv"))
    if color:
        assert f".codehilite .nb {{ color: {color}" in doc.style.text


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


@pytest.mark.skipif(
    not os.environ.get("MD2HTML_TEST_COMMAND"), reason="requires an installed package command"
)
def test_installed_incremental_restart_without_toolchain(tmp_path):
    command = shlex.split(os.environ["MD2HTML_TEST_COMMAND"])
    source = tmp_path / "note.md"
    source.write_text("$x^2$\n\n@src(example.h)")
    (tmp_path / "example.h").write_text("int answer = 42;")
    result = subprocess.run(command + [str(source)], cwd=tmp_path, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert BeautifulSoup(source.with_suffix(".html").read_text(), "html.parser").select_one(".codehilite .kt")
    result = subprocess.run(
        command + [str(source)],
        cwd=tmp_path,
        env={**os.environ, "PATH": ""},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Built 0 pages" in result.stdout
