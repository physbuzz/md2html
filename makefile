PYTHON ?= .venv/bin/python
UV ?= uv
LOCAL_BIN ?= $(HOME)/.local/bin
GLOBAL_BIN ?= /usr/local/bin

.PHONY: sync test pyinstaller install install-global clean

sync:
	@test "$$(id -u)" != 0 || { echo "Build as a regular user; use sudo only for make install-global." >&2; exit 1; }
	$(UV) sync --locked --all-extras

test: sync
	$(PYTHON) -m pytest -q

pyinstaller: sync
	npm ci --ignore-scripts
	$(PYTHON) -m PyInstaller --clean --noconfirm md2html.spec

install: pyinstaller
	mkdir -p "$(LOCAL_BIN)"
	install -m 755 dist/md2html "$(LOCAL_BIN)/md2html"

install-global:
	@test -f dist/md2html || { echo "Run make pyinstaller as a regular user first." >&2; exit 1; }
	mkdir -p "$(GLOBAL_BIN)"
	install -m 755 dist/md2html "$(GLOBAL_BIN)/md2html"

clean:
	rm -rf build dist .pytest_cache
