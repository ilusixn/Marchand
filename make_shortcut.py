#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def windows():
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    target = str(pyw if pyw.exists() else py)
    ps = r'''
$s = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  $l = $s.CreateShortcut((Join-Path $dir 'Marchand.lnk'))
  $l.TargetPath = '%s'
  $l.Arguments = '"%s"'
  $l.WorkingDirectory = '%s'
  $l.IconLocation = '%s'
  $l.Description = 'Marchand - local AI desktop app'
  $l.Save()
}
''' % (target, HERE / "app.py", HERE, HERE / "assets" / "icon.ico")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print("Shortcut created on your Desktop and in the Start menu: Marchand")


def linux():
    d = Path.home() / ".local/share/applications"
    d.mkdir(parents=True, exist_ok=True)
    (d / "marchand.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Marchand\nComment=Local AI desktop app\nExec=%s %s\nIcon=%s\nTerminal=false\nCategories=Development;\n"
        % (sys.executable, HERE / "app.py", HERE / "assets" / "icon.png"))
    print("Added Marchand to your applications menu.")


if sys.platform.startswith("win"):
    windows()
elif sys.platform == "darwin":
    print("On macOS: open Terminal in this folder and run  python3 app.py  (or drag app.py to Automator > Run Shell Script).")
else:
    linux()
