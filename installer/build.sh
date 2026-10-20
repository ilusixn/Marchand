#!/bin/sh
# rebuilds stage/ (bundled Python + app + launcher) and MarchandStudio-Setup.exe
set -e
cd "$(dirname "$0")"
[ -f /tmp/pyw/py.nupkg ] || { mkdir -p /tmp/pyw; curl -sS -o /tmp/pyw/py.nupkg https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg; }
rm -rf stage && mkdir stage
python3 - <<'PY'
import zipfile,os,shutil
z=zipfile.ZipFile('/tmp/pyw/py.nupkg')
skip=('tools/include/','tools/libs/','tools/Doc/','tools/tcl/','tools/Scripts/','tools/Lib/test/','tools/Lib/idlelib/','tools/Lib/tkinter/','tools/Lib/turtledemo/','tools/Lib/site-packages/','tools/Lib/ensurepip/','tools/DLLs/_tkinter','tools/DLLs/tcl','tools/DLLs/tk')
for n in z.namelist():
    if not n.startswith('tools/') or n.endswith('/') or n.startswith(skip) or '__pycache__' in n: continue
    d=os.path.join('stage','python',n[len('tools/'):]); os.makedirs(os.path.dirname(d),exist_ok=True); open(d,'wb').write(z.read(n))
shutil.copytree('..','stage/app',ignore=shutil.ignore_patterns('tests','installer','.git','.github','__pycache__','*.bat','*.sh','make_shortcut.py'))
PY
x86_64-w64-mingw32-windres launcher.rc -O coff -o launcher_res.o
x86_64-w64-mingw32-gcc -municode -mwindows -O2 -o stage/MarchandStudio.exe launcher.c launcher_res.o -static
cp ../assets/icon.ico stage/icon.ico
cp ../LICENSE stage/LICENSE.txt
cp ../NOTICE stage/NOTICE.txt
cp ../TRADEMARK.md stage/TRADEMARK.md
makensis -V2 setup.nsi
