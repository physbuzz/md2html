.PHONY: run build clean test

run:
	python -m md2html.md2html

build: 
	pyinstaller -F main.py -n md2html

# PYTHONPATH=~/dev/md2html python -m md2html.md2html file\ with\ space.md
test:
	python -m md2html.test

clean:
	-rm -r build 
	-rm main.spec
