.PHONY: run build clean

run:
	python -m md2html.md2html

build: 
	pyinstaller -F main.py

clean:
	rm -r build dist md2html.spec
