PYTHON ?= .venv/bin/python
UV ?= uv
LOCAL_BIN ?= $(HOME)/.local/bin
GLOBAL_BIN ?= /usr/local/bin
MD2HTML ?= $(CURDIR)/.venv/bin/md2html

.PHONY: sync check test test-browser test-packaged pyinstaller install install-global clean

sync:
	@test "$$(id -u)" != 0 || { echo "Build as a regular user; use sudo only for make install-global." >&2; exit 1; }
	$(UV) sync --locked --all-extras

test: sync
	$(PYTHON) -m pytest -q

check: sync
	.venv/bin/ruff check src tests

test-browser: sync
	npm ci --ignore-scripts
	node tests/markdown_browser.cjs browser-artifacts/markdown "$(MD2HTML)"

test-packaged: sync
	MD2HTML_TEST_COMMAND="$(CURDIR)/dist/md2html" $(PYTHON) -m pytest -q \
		tests/test_packaged.py \
		tests/test_markdown.py::test_footnotes_number_references_and_preserve_rich_definitions \
		tests/test_markdown.py::test_new_feature_assets_are_conditional_and_shared \
		tests/test_markdown.py::test_footnotes_and_alerts_leave_literals_and_export_intact \
		tests/test_build.py::test_directives_liquid_code_and_includes \
		tests/test_build.py::test_site_layouts_listing_pagination_and_feed

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
