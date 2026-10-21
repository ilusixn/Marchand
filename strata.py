import os
import re
import shutil
import subprocess
from pathlib import Path

HOME = "https://github.com/Niko1221/Strata"
DOCS = HOME + "/blob/main/docs/MODELS.md"
RELEASES = HOME + "/releases/latest"
BASE = "http://127.0.0.1:8080/v1"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def S(sid, name, mem, dl, tags, desc):
    return {"id": sid, "name": name, "mem_gb": mem, "dl": dl, "tags": ["strata", "general", "large"] + tags, "desc": desc}


CATALOG = [
    S("q2_0", "Qwen3.8-Flash-Next Q2_0", 37.6, "66-76 GB", ["fast"], "125B-parameter model in 2 bits. The fastest size, good quality."),
    S("iq2_xs", "Qwen3.8-Flash-Next IQ2_XS", 39.2, "66-76 GB", [], "Fast and better quality. Strata's pick for a 40 GB PC."),
    S("iq3_xxs", "Qwen3.8-Flash-Next IQ3_XXS", 47.0, "66-76 GB", [], "Slower, great quality."),
    S("iq3_s", "Qwen3.8-Flash-Next IQ3_S", 54.8, "66-76 GB", [], "The slowest and best: matches the full model on its published tests."),
    S("gyro-s", "Qwen3.8-Flash-Next Gyro-S", 27.6, "58.5 GB", ["small"], "The smallest way to run this model, for PCs with little memory. Lower quality. NVIDIA and AMD (AMD experimental)."),
    S("gyro-m", "Qwen3.8-Flash-Next Gyro-M", 35.0, "92.0 GB", [], "About IQ3_XXS quality with about 20% less graphics memory. NVIDIA and AMD (AMD experimental)."),
    S("coder", "Qwen3.8-Flash-Next Coder", 32.0, "about 30 GB+", ["coding"], "A coding version that keeps half of the experts and fits a 32 GB PC. Weaker outside code."),
    S("swift", "Qwen3.8-Flash-Next Swift 1.5", 39.2, "66-76 GB", ["coding"], "A fine-tune that thinks for a shorter time before it answers. It has its own license."),
    S("qwen36", "Qwen3.6-35B-A3B (UD-Q4_K_XL)", 32.0, "22.9 GB", [], "A smaller, different model that reads pictures and can answer several requests at once."),
]


def entries(hw):
    total = (hw.get("ram_gb") or 0) + (hw.get("vram_gb") or 0)
    out = []
    for m in CATALOG:
        fit = "great" if total >= m["mem_gb"] * 1.25 else "ok" if total >= m["mem_gb"] else "too big" if total else "unknown"
        out.append({"name": m["name"], "id": m["id"], "engine": "strata", "gb": m["mem_gb"], "mem_gb": m["mem_gb"], "dl": m["dl"], "tags": m["tags"],
                    "tools": True, "desc": m["desc"], "fit": fit, "url": DOCS})
    return out


def exe():
    for p in (os.environ.get("MARCHAND_STRATA"), shutil.which("strata")):
        if p and Path(p).is_file():
            return p
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    roots = [Path(os.environ["LOCALAPPDATA"]) / "Strata" / "terminal"] if os.environ.get("LOCALAPPDATA") else []
    roots += [home / "AppData" / "Local" / "Strata" / "terminal", home / ".local" / "share" / "strata" / "terminal", home / ".local" / "bin"]
    names = {"strata.exe", "strata.cmd", "strata"}
    for r in roots:
        if not r.is_dir():
            continue
        base = len(r.parts)
        for dirpath, dirs, files in os.walk(r):
            if len(Path(dirpath).parts) - base >= 3:
                dirs[:] = []
            for f in files:
                if f.lower() in names:
                    return str(Path(dirpath) / f)
    return None


def status():
    e = exe()
    return {"installed": bool(e), "path": e or "", "releases": RELEASES, "home": HOME}


def clean(line):
    return ANSI.sub("", line).replace("\r", "").strip()


def install(model_id, emit):
    e = exe()
    if not e:
        raise RuntimeError("Strata is not installed on this PC. Get it from %s, then press Download again." % RELEASES)
    plan = subprocess.run([e, "launch", "--plan", "--model", model_id], capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    if plan.returncode != 0:
        msg = clean((plan.stdout + "\n" + plan.stderr).strip().splitlines()[-1] if (plan.stdout + plan.stderr).strip() else "")
        raise RuntimeError("Strata does not know this model (%s). Run `strata launch` and pick it there. %s" % (model_id, msg))
    emit({"status": "Strata is preparing %s (large download, it continues if interrupted)..." % model_id})
    proc = subprocess.Popen([e, "launch", "--model", model_id, "--yes", "--no-tui"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1)
    tail = []
    for raw in proc.stdout:
        line = clean(raw)
        if line:
            tail = (tail + [line])[-6:]
            emit({"status": line[:220]})
    rc = proc.wait()
    if rc:
        raise RuntimeError("Strata stopped with code %s: %s" % (rc, " | ".join(tail[-3:])))
