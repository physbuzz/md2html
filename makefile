PYTHON ?= .venv/bin/python
LOCAL_BIN ?= $(HOME)/.local/bin

.PHONY: test pyinstaller install clean

test:
	$(PYTHON) -m pytest -q

pyinstaller:
	$(PYTHON) -m pip install -e '.[build]'
	npm ci
	$(PYTHON) -m PyInstaller --clean --noconfirm md2html.spec

install: pyinstaller
	mkdir -p "$(LOCAL_BIN)"
	install -m 755 dist/md2html "$(LOCAL_BIN)/md2html"

clean:
	rm -rf build dist .pytest_cache
