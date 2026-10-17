from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
data = [
    entry
    for package in ('md2html', 'ziamath', 'ziafont', 'latex2mathml')
    for entry in collect_data_files(package)
]
data += [
    (str(root / 'node_modules' / name), 'node_modules/' + name)
    for name in ('mathjax', '@mathjax')
]
data += [(str(root / 'readme.md'), 'md2html')]
analysis = Analysis(
    [str(root / 'src/md2html/__main__.py')],
    pathex=[str(root / 'src')],
    datas=data,
    hiddenimports=['pygments.lexers', 'pygments.styles'],
    excludes=['matplotlib', 'numpy', 'sympy', 'pytest'],
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive, analysis.scripts, analysis.binaries, analysis.datas, [],
    name='md2html', console=True,
)
