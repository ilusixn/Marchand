import html
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

LIMIT = 60000
OFFICE = {".docx": ("word/document.xml",), ".odt": ("content.xml",), ".ods": ("content.xml",), ".odp": ("content.xml",),
          ".pptx": (), ".xlsx": ("xl/sharedStrings.xml",)}


def xml_text(raw):
    raw = re.sub(r"</(w:p|a:p|text:p|text:h|row|si)>", "\n", raw)
    raw = re.sub(r"</(w:tc|a:tc|text:tab|c)>", "\t", raw)
    return html.unescape(re.sub(r"<[^>]+>", "", raw))


def extract(path):
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in OFFICE:
            with zipfile.ZipFile(p) as z:
                names = list(OFFICE[ext])
                if ext == ".pptx":
                    names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
                parts = []
                for n in names:
                    if n in z.namelist():
                        parts.append(xml_text(z.read(n).decode("utf-8", "replace")))
                return "\n\n".join(parts).strip()[:LIMIT]
        if ext in (".zip", ".jar", ".apk"):
            with zipfile.ZipFile(p) as z:
                infos = z.infolist()
                lines = ["%s  (%d bytes)" % (i.filename, i.file_size) for i in infos[:300]]
                return ("Archive with %d entries:\n" % len(infos) + "\n".join(lines))[:LIMIT]
        if ext == ".pdf" and shutil.which("pdftotext"):
            out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, timeout=60)
            return out.stdout.decode("utf-8", "replace").strip()[:LIMIT]
    except Exception:
        return ""
    return ""
