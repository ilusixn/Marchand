import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def config_path(override=None):
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Claude" / "claude_desktop_config.json"
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        store = sorted((local / "Packages").glob("Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json")) if (local / "Packages").is_dir() else []
        for cand in [roaming] + store:
            if cand.is_file():
                return cand
        return store[0] if store and not roaming.parent.is_dir() else roaming
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def read_config(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def join_command(command, args):
    parts = [command] + [str(a) for a in (args or [])]
    return subprocess.list2cmdline(parts) if sys.platform.startswith("win") else " ".join(shlex.quote(p) for p in parts)


def status(override=None):
    p = config_path(override)
    cfg = read_config(p) if p.is_file() else None
    servers = (cfg or {}).get("mcpServers", {})
    return {"path": str(p), "found": p.is_file(), "readable": cfg is not None or not p.is_file(),
            "connected": "marchand" in servers,
            "servers": [{"name": n, "command": join_command(s.get("command", ""), s.get("args")), "env": s.get("env") or {}}
                        for n, s in servers.items() if n != "marchand"]}


def backup(p):
    if p.is_file():
        shutil.copy2(p, p.with_name(p.name + ".marchand-backup-" + time.strftime("%Y%m%d-%H%M%S")))


def connect(override=None, host="http://127.0.0.1:11434"):
    p = config_path(override)
    cfg = read_config(p) if p.is_file() else {}
    if cfg is None:
        raise ValueError("Claude Desktop's config file is not valid JSON; fix it first: %s" % p)
    backup(p)
    cfg.setdefault("mcpServers", {})["marchand"] = {
        "command": sys.executable, "args": [str(HERE / "marchand_mcp.py")], "env": {"OLLAMA_HOST": host}}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return str(p)


def disconnect(override=None):
    p = config_path(override)
    cfg = read_config(p) if p.is_file() else None
    if cfg and "marchand" in cfg.get("mcpServers", {}):
        backup(p)
        del cfg["mcpServers"]["marchand"]
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return str(p)
