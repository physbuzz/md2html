.PHONY: run build clean

run:
	python -m md2html.md2html

build: 
	pyinstaller -F main.py -n md2html

clean:
	-rm -r build 
	-rm -r dist 
	-rm md2html.spec
