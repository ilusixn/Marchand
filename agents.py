import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import claude_code

AGENTS = [
    {"id": "claude", "name": "Claude Code", "names": ["claude"], "usable": True, "url": "https://claude.ai/code",
     "what": "Claude on your subscription. Marchand can drive it."},
    {"id": "codex", "name": "OpenAI Codex CLI", "names": ["codex"], "usable": False, "url": "https://github.com/openai/codex",
     "what": "OpenAI's coding agent. Found on this PC; use OpenAI models through a key in the model picker."},
    {"id": "gemini", "name": "Gemini CLI", "names": ["gemini"], "usable": False, "url": "https://github.com/google-gemini/gemini-cli",
     "what": "Google's coding agent. Use Gemini models through a key in the model picker."},
    {"id": "aider", "name": "Aider", "names": ["aider"], "usable": False, "url": "https://aider.chat", "what": "Open-source pair-programming agent."},
    {"id": "goose", "name": "Goose", "names": ["goose"], "usable": False, "url": "https://block.github.io/goose", "what": "Open-source agent from Block."},
    {"id": "opencode", "name": "opencode", "names": ["opencode"], "usable": False, "url": "https://opencode.ai", "what": "Open-source terminal agent."},
]
SKIP = {"node_modules", ".git", "__pycache__", "Windows", "Temp", "Cache", "Code Cache", "GPUCache", "site-packages", "proc", "sys"}


def exts(name):
    return [name + e for e in (".exe", ".cmd", ".bat")] if sys.platform.startswith("win") else [name]


def version(path):
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8)
        return (r.stdout or r.stderr).strip().splitlines()[0][:80] if (r.stdout or r.stderr).strip() else ""
    except Exception:
        return ""


def search_roots():
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    roots = [home / ".local", home / ".claude", home / ".npm-global", home / ".vscode" / "extensions", home / ".cursor" / "extensions", home / ".cargo" / "bin",
             home / "AppData" / "Roaming", home / "AppData" / "Local", home / "Library" / "Application Support", home / ".config",
             Path("/usr/local/bin"), Path("/opt/homebrew/bin"), Path("/opt")]
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]))
    return [r for r in roots if r.is_dir()]


def walk(roots, wanted, deadline, max_depth=7):
    hits = {}
    for root in roots:
        base = len(root.parts)
        for dirpath, dirs, files in os.walk(root):
            if time.time() > deadline:
                return hits
            if len(Path(dirpath).parts) - base >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if d not in SKIP]
            for f in files:
                if f.lower() in wanted:
                    hits.setdefault(wanted[f.lower()], []).append(str(Path(dirpath) / f))
    return hits


def scan(deep=True, seconds=8):
    deadline = time.time() + seconds
    wanted = {}
    for a in AGENTS:
        for n in a["names"]:
            for e in exts(n):
                wanted[e.lower()] = a["id"]
    found = {a["id"]: [] for a in AGENTS}
    for a in AGENTS:
        for n in a["names"]:
            p = shutil.which(n)
            if p:
                found[a["id"]].append(p)
    for p in claude_code.candidates():
        if p.is_file():
            found["claude"].append(str(p))
    if deep:
        for aid, paths in walk(search_roots(), wanted, deadline).items():
            found[aid] += paths
    current = claude_code.exe()
    out = []
    for a in AGENTS:
        seen, paths = set(), []
        for p in found[a["id"]]:
            try:
                key = str(Path(p).resolve())
            except OSError:
                key = p
            if key not in seen and Path(p).is_file():
                seen.add(key)
                paths.append(p)
        best = paths[0] if paths else ""
        if a["id"] == "claude" and current:
            best = current
            if current not in paths:
                paths.insert(0, current)
        out.append({"id": a["id"], "name": a["name"], "usable": a["usable"], "url": a["url"], "what": a["what"], "found": bool(paths), "path": best,
                    "paths": paths[:5], "version": version(best) if best else "", "active": a["id"] == "claude" and bool(current) and best == current})
    return out
