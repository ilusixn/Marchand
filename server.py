#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import winquiet

winquiet.install()

import agents
import claude_code
import claude_desktop
import engine
import extract
import finetune
import images
import ollama_mgr
import plugins
import providers
import software
import teacher
import trainer

WEB = Path(__file__).resolve().parent / "web"


def _build():
    if os.environ.get("MARCHAND_BUILD"):
        return os.environ["MARCHAND_BUILD"]
    try:
        return (WEB.parent / "BUILD.txt").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


BUILD = _build()
DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
CONVOS = DATA / "conversations"
SETTINGS = DATA / "settings.json"
DEFAULTS = {"host": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"), "num_ctx": 16384, "temperature": 0.2,
            "max_steps": 40, "auto_approve": False, "critic": True, "system_extra": "", "project": str(Path.cwd()),
            "providers": {}, "images": {}, "teacher_model": "", "critic_with_teacher": False, "check_updates": True,
            "vision_model": "", "cc_effort": "high", "claude_path": ""}
FILES = DATA / "files"
VISION = {}
TOKEN = secrets.token_hex(16)
PORT = {"n": 8765}
MODEL_CACHE = {}
RUNS = {}


def load_settings():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS.read_text()))
    except (OSError, json.JSONDecodeError):
        pass
    if not s["host"].startswith("http"):
        s["host"] = "http://" + s["host"]
    return s


def mask(key):
    return "\u2022\u2022\u2022\u2022" + key[-4:] if key else ""


def public_settings():
    s = load_settings()
    s["providers"] = {p: dict(v, key=mask(v.get("key", ""))) for p, v in s.get("providers", {}).items()}
    s["app_build"] = BUILD
    return s


def save_settings(new):
    DATA.mkdir(parents=True, exist_ok=True)
    s = load_settings()
    new = dict(new)
    if "providers" in new:
        merged = {}
        for p, v in (new["providers"] or {}).items():
            old = s.get("providers", {}).get(p, {})
            key = v.get("key", "")
            if key.startswith("\u2022"):
                key = old.get("key", "")
            merged[p] = dict(v, key=key.strip())
        new["providers"] = merged
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    SETTINGS.write_text(json.dumps(s, indent=2))
    return public_settings()


class Run:
    def __init__(self):
        self.cancel = threading.Event()
        self.pending = {}
        self.always = False
        self.approve = None


def has_vision(s, model_id):
    prov, m = providers.split_model(model_id)
    if prov != "ollama":
        return True
    if m not in VISION:
        try:
            req = urllib.request.Request(s["host"] + "/api/show", json.dumps({"model": m}).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                VISION[m] = "vision" in (json.loads(r.read()).get("capabilities") or [])
        except Exception:
            VISION[m] = False
    return VISION[m]


def describe_images(s, images, question):
    prompt = ("Describe these images in detail for another AI that cannot see them: visible text (copy it exactly), UI elements, "
              "errors, numbers, colours, layout and anything relevant to this request: " + (question or "(none)"))
    return providers.chat_once(s, s["vision_model"], [{"role": "user", "content": prompt, "images": images}], {"temperature": 0.1})


def git(root, *args):
    try:
        r = subprocess.run(["git"] + list(args), cwd=root, capture_output=True, text=True, timeout=30)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as ex:
        return 1, str(ex)


def safe_name(name):
    name = os.path.basename(str(name or "")).strip().replace("\x00", "")
    return name if name not in ("", ".", "..") else "file"


def video_frames(path, count=6):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Video needs ffmpeg. On Windows run: winget install ffmpeg  (then restart Marchand), or download it from https://ffmpeg.org/download.html")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True, timeout=60)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        raise RuntimeError("Could not read this video (ffprobe: %s)" % (r.stderr.strip()[:200] or "unknown format"))
    count = max(1, min(12, int(count)))
    out, tmp = [], Path(tempfile.mkdtemp())
    for i in range(count):
        t = dur * (i + 0.5) / count
        f = tmp / ("f%02d.jpg" % i)
        subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % t, "-i", str(path), "-frames:v", "1", "-vf", "scale=768:-2", "-y", str(f)],
                       capture_output=True, timeout=120)
        if f.is_file():
            out.append({"t": round(t, 1), "b64": base64.b64encode(f.read_bytes()).decode()})
    shutil.rmtree(tmp, ignore_errors=True)
    if not out:
        raise RuntimeError("ffmpeg could not extract frames from this video.")
    return {"duration": round(dur, 1), "frames": out}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def allowed(self, path):
        host = (self.headers.get("Host") or "").lower()
        ok_hosts = ("127.0.0.1:%d" % PORT["n"], "localhost:%d" % PORT["n"])
        if host not in ok_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin.lower() not in ("http://" + h for h in ok_hosts):
            return False
        if path in ("/", "/index.html", "/pages.js", "/help.js", "/images.js", "/panel.js", "/training.js", "/icon.png", "/favicon.ico"):
            return True
        return self.headers.get("X-Marchand-Token") == TOKEN

    def send_json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if not self.allowed(p):
            return self.send_json({"error": "forbidden"}, 403)
        if p in ("/", "/index.html"):
            data = (WEB / "index.html").read_bytes().replace(b"__TOKEN__", TOKEN.encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p in ("/icon.png", "/favicon.ico"):
            data = (WEB.parent / "assets" / "icon.png").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p in ("/pages.js", "/help.js", "/images.js", "/panel.js", "/training.js"):
            data = (WEB / p[1:]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p == "/api/settings":
            self.send_json(public_settings())
        elif p == "/api/models":
            self.send_json(self.model_groups(q.get("refresh")))
        elif p == "/api/ollama/check":
            self.send_json(ollama_mgr.check(load_settings()["host"]))
        elif p == "/api/ollama/catalog":
            self.send_json(ollama_mgr.catalog())
        elif p == "/api/model/show":
            self.ollama_post("/api/show", {"model": q.get("name", [""])[0]})
        elif p == "/api/cc/status":
            self.send_json(claude_code.status())
        elif p == "/api/git":
            root = q.get("root", [""])[0]
            if not root or not Path(root).is_dir():
                return self.send_json({"git": False})
            code, branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
            if code:
                return self.send_json({"git": False})
            _, st = git(root, "status", "--porcelain")
            _, stat = git(root, "diff", "--shortstat")
            self.send_json({"git": True, "branch": branch, "changed": len([l for l in st.splitlines() if l.strip()]), "stat": stat})
        elif p == "/api/git/diff":
            root = q.get("root", [""])[0]
            code, out = git(root, "diff") if root and Path(root).is_dir() else (1, "")
            self.send_json({"diff": out[:400000]})
        elif p == "/api/files":
            d = FILES / safe_name(q.get("convo", [""])[0])
            items = [{"name": f.name, "size": f.stat().st_size, "type": mimetypes.guess_type(f.name)[0] or "application/octet-stream", "time": int(f.stat().st_mtime)}
                     for f in sorted(d.iterdir())] if d.is_dir() else []
            self.send_json(items)
        elif p == "/api/stored":
            f = FILES / safe_name(q.get("convo", [""])[0]) / safe_name(q.get("name", [""])[0])
            if not f.is_file():
                return self.send_json({"error": "not found"}, 404)
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p == "/api/extract":
            f = FILES / safe_name(q.get("convo", [""])[0]) / safe_name(q.get("name", [""])[0])
            if not f.is_file():
                return self.send_json({"error": "not found"}, 404)
            self.send_json({"text": extract.extract(f)})
        elif p == "/api/training/tasks":
            self.send_json([{k: t.get(k) for k in ("id", "title", "topic", "level", "prompt", "builtin", "folder", "test_cmd", "lang", "available", "why")}
                            for t in trainer.all_tasks()] + [])
        elif p == "/api/training/languages":
            import curriculum
            out = {}
            for t in trainer.all_tasks():
                if t.get("builtin"):
                    e = out.setdefault(t["lang"], {"name": curriculum.LANG_NAMES.get(t["lang"], t["lang"]), "tasks": 0, "available": 0, "why": ""})
                    e["tasks"] += 1
                    e["available"] += 1 if t["available"] else 0
                    e["why"] = e["why"] or t["why"]
            self.send_json(out)
        elif p == "/api/training/sessions":
            self.send_json(trainer.sessions())
        elif p == "/api/training/session":
            ses = trainer.get_session(q.get("id", [""])[0])
            self.send_json(ses or {"error": "not found"}, 200 if ses else 404)
        elif p == "/api/training/recommend":
            self.send_json({"base": trainer.recommend_base(), "hardware": ollama_mgr.hardware()})
        elif p == "/api/finetune/check":
            self.send_json(finetune.check())
        elif p == "/api/finetune/job":
            job = finetune.JOBS.get(q.get("id", [""])[0])
            self.send_json(job or {"error": "not found"}, 200 if job else 404)
        elif p == "/api/images/status":
            self.send_json(images.status(load_settings()))
        elif p == "/api/images":
            self.send_json(images.index())
        elif p == "/api/image":
            data = images.read_image(q.get("name", [""])[0])
            if data is None:
                return self.send_json({"error": "not found"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/" + ("jpeg" if images.ext_of(data) == "jpg" else images.ext_of(data)))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p == "/api/software/scan":
            self.send_json({"found": software.scan()})
        elif p == "/api/agents/scan":
            self.send_json({"agents": agents.scan(q.get("deep", ["1"])[0] != "0")})
        elif p == "/api/links":
            hw = ollama_mgr.hardware_cached()
            have = {"ollama": bool(shutil.which("ollama")), "ffmpeg": bool(shutil.which("ffmpeg")), "git": bool(shutil.which("git")),
                    "python": True, "claude-code": bool(claude_code.exe())}
            self.send_json({"links": software.links(hw.get("vendor", "")), "have": have, "hardware": hw})
        elif p == "/api/ais":
            self.send_json(teacher.ais())
        elif p == "/api/teach/lessons":
            self.send_json(teacher.lessons())
        elif p == "/api/teach/examples":
            self.send_json([{k: v for k, v in e.items() if k != "messages"} | {"steps": len(e["messages"])} for e in teacher.examples()])
        elif p == "/api/teach/export":
            body, n = teacher.export_dataset(int(q.get("min", ["4"])[0]), q.get("cloud", ["0"])[0] == "1")
            self.send_json({"jsonl": body, "count": n, "train_script": teacher.TRAIN_SCRIPT})
        elif p == "/api/status":
            s = load_settings()
            try:
                with urllib.request.urlopen(s["host"] + "/api/version", timeout=3) as r:
                    self.send_json({"ok": True, "version": json.loads(r.read()).get("version")})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)})
        elif p == "/api/plugins":
            self.send_json({"installed": plugins.installed(), "available": plugins.available(), "mcp": plugins.mcp_servers()})
        elif p == "/api/commands":
            self.send_json(plugins.commands())
        elif p == "/api/claude-desktop":
            self.send_json(claude_desktop.status((q.get("path") or [None])[0]))
        elif p == "/api/convos":
            CONVOS.mkdir(parents=True, exist_ok=True)
            items = []
            for f in CONVOS.glob("*.json"):
                try:
                    c = json.loads(f.read_text())
                    items.append({"id": c["id"], "title": c.get("title", "Untitled"), "mode": c.get("mode", "chat"),
                                  "updated": c.get("updated", 0)})
                except (OSError, json.JSONDecodeError, KeyError):
                    continue
            self.send_json(sorted(items, key=lambda c: -c["updated"]))
        elif p == "/api/convo":
            f = CONVOS / (os.path.basename(q.get("id", [""])[0]) + ".json")
            self.send_json(json.loads(f.read_text()) if f.is_file() else {}, 200 if f.is_file() else 404)
        elif p == "/api/tree":
            root = Path(q.get("path", ["."])[0])
            if not root.is_dir():
                return self.send_json({"error": "not a folder"}, 400)
            self.send_json({"files": engine.tree_lines(root, 4, 400)})
        elif p == "/api/file":
            root = Path(q.get("root", ["."])[0]).resolve()
            f = (root / q.get("path", [""])[0]).resolve()
            if root not in f.parents:
                return self.send_json({"error": "not found"}, 404)
            if not f.is_file():
                return self.send_json({"text": "", "missing": True})
            self.send_json({"text": f.read_text(errors="replace")[:200000]})
        elif p == "/api/browse":
            d = Path(q.get("path", [""])[0] or Path.home()).expanduser()
            if not d.is_dir():
                d = Path.home()
            try:
                dirs = sorted(x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith("."))
            except OSError:
                dirs = []
            self.send_json({"path": str(d.resolve()), "parent": str(d.resolve().parent), "dirs": dirs})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if not self.allowed(p):
            return self.send_json({"error": "forbidden"}, 403)
        if p == "/api/upload":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            n = int(self.headers.get("Content-Length") or 0)
            if n > 500 * 2 ** 20:
                return self.send_json({"error": "file larger than 500 MB"}, 400)
            d = FILES / safe_name(q.get("convo", [""])[0])
            d.mkdir(parents=True, exist_ok=True)
            name = safe_name(q.get("name", ["file"])[0])
            with open(d / name, "wb") as f:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            return self.send_json({"ok": True, "name": name, "size": n})
        try:
            data = self.body()
        except json.JSONDecodeError:
            return self.send_json({"error": "bad json"}, 400)
        if p == "/api/settings":
            self.send_json(save_settings(data))
        elif p == "/api/convo":
            CONVOS.mkdir(parents=True, exist_ok=True)
            cid = os.path.basename(str(data.get("id", "")))
            if not cid:
                return self.send_json({"error": "no id"}, 400)
            (CONVOS / (cid + ".json")).write_text(json.dumps(data))
            self.send_json({"ok": True})
        elif p == "/api/delete":
            f = CONVOS / (os.path.basename(str(data.get("id", ""))) + ".json")
            if f.is_file():
                f.unlink()
            self.send_json({"ok": True})
        elif p == "/api/run":
            self.run_stream(data)
        elif p.startswith("/api/plugins/") or p.startswith("/api/mcp/") or p.startswith("/api/claude-desktop/") or p == "/api/writefile":
            try:
                self.send_json(self.admin(p, data))
            except Exception as ex:
                self.send_json({"error": str(ex)}, 400)
        elif p == "/api/pull":
            self.pull_stream(data)
        elif p == "/api/ollama/update":
            self.sse_start()
            try:
                ollama_mgr.update_stream(lambda t, pct=None: self.sse({"status": t, "pct": pct}))
                self.sse({"done": True})
            except Exception as ex:
                self.sse({"error": str(ex)})
        elif p == "/api/ollama/start":
            try:
                ollama_mgr.start_ollama()
                self.send_json({"ok": True})
            except Exception as ex:
                self.send_json({"error": str(ex)}, 400)
        elif p == "/api/model/delete":
            self.ollama_post("/api/delete", {"model": data.get("name")}, method="DELETE")
        elif p == "/api/providers/test":
            prov = data.get("provider")
            ids = providers.list_models(load_settings(), prov)
            self.send_json({"ok": bool(ids), "models": ids[:200]})
        elif p == "/api/teach/evaluate":
            self.teach_evaluate(data)
        elif p == "/api/teach/lesson":
            if data.get("add"):
                teacher.add_lessons([{"text": data["add"], "tags": data.get("tags") or ["general"]}], "you")
            else:
                teacher.update_lesson(data.get("id"), data.get("enabled"), data.get("delete", False), data.get("text"))
            self.send_json({"ok": True})
        elif p == "/api/teach/save-example":
            self.send_json({"ok": True, "id": teacher.save_example(data["convo"], data.get("rating", 5))})
        elif p == "/api/teach/delete-example":
            teacher.delete_example(data.get("id"))
            self.send_json({"ok": True})
        elif p == "/api/teach/build-model":
            self.build_model_stream(data)
        elif p == "/api/cc/permission":
            run = RUNS.get(data.get("run"))
            if not run or not run.approve:
                return self.send_json({"allow": False})
            tool, inp = data.get("tool", ""), data.get("input") or {}
            if tool in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
                path = inp.get("file_path") or inp.get("notebook_path") or ""
                allow = run.approve("edit", path, claude_code.edit_preview(tool, inp))
            elif tool == "Bash":
                allow = run.approve("command", inp.get("command", ""), None)
            else:
                allow = run.approve("tool", "%s %s" % (tool, json.dumps(inp)[:200]), None)
            self.send_json({"allow": bool(allow)})
        elif p == "/api/cc/refresh":
            try:
                claude_code.chat_stream("haiku", [{"role": "user", "content": "Reply with: ok"}], lambda k, t: None, threading.Event(), effort="low")
                self.send_json(claude_code.status())
            except Exception as ex:
                self.send_json({"error": str(ex)}, 502)
        elif p == "/api/git/commit":
            root = data.get("root", "")
            msg = str(data.get("message", "")).strip()
            if not msg or not root or not Path(root).is_dir():
                return self.send_json({"error": "need a project folder and a message"}, 400)
            git(root, "add", "-A")
            code, out = git(root, "commit", "-m", msg)
            self.send_json({"ok": code == 0, "output": out[-800:]}, 200 if code == 0 else 400)
        elif p == "/api/files/delete":
            f = FILES / safe_name(data.get("convo")) / safe_name(data.get("name"))
            if f.is_file():
                f.unlink()
            self.send_json({"ok": True})
        elif p == "/api/video/frames":
            f = FILES / safe_name(data.get("convo")) / safe_name(data.get("name"))
            try:
                self.send_json(video_frames(f, data.get("count", 6)))
            except Exception as ex:
                self.send_json({"error": str(ex)}, 400)
        elif p.startswith("/api/training/") or p.startswith("/api/finetune/"):
            try:
                self.training_post(p, data)
            except Exception as ex:
                self.send_json({"error": providers.err_text(ex)}, 400)
        elif p == "/api/images/generate":
            self.image_stream(data)
        elif p == "/api/images/delete":
            images.delete_image(data.get("name", ""))
            self.send_json({"ok": True})
        elif p == "/api/images/enhance":
            try:
                self.send_json({"prompt": images.enhance_prompt(load_settings(), data["model"], data["prompt"])})
            except Exception as ex:
                self.send_json({"error": providers.err_text(ex)}, 502)
        elif p == "/api/agents/use":
            path = Path(str(data.get("path", "")))
            if not path.is_file() or not path.name.lower().startswith("claude"):
                self.send_json({"error": "That is not the Claude Code program."}, 400)
            else:
                save_settings({"claude_path": str(path)})
                MODEL_CACHE.clear()
                self.send_json({"ok": True, "path": str(path)})
        elif p == "/api/open-url":
            try:
                software.open_url(str(data.get("url", "")))
                self.send_json({"ok": True})
            except ValueError as ex:
                self.send_json({"error": str(ex)}, 400)
        elif p == "/api/software/apply":
            self.send_json(self.apply_software(data))
        elif p == "/api/ais/delete":
            teacher.delete_ai(data.get("name"))
            if data.get("remove_model"):
                self.ollama_post("/api/delete", {"model": data.get("name")}, method="DELETE")
            else:
                self.send_json({"ok": True})
        elif p == "/api/approve":
            run = RUNS.get(data.get("run"))
            slot = run.pending.get(data.get("id")) if run else None
            if slot:
                if data.get("always"):
                    run.always = True
                slot["allow"] = bool(data.get("allow"))
                slot["event"].set()
            self.send_json({"ok": True})
        elif p == "/api/stop":
            run = RUNS.get(data.get("run"))
            if run:
                run.cancel.set()
                for slot in run.pending.values():
                    slot["event"].set()
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "not found"}, 404)

    def admin(self, p, d):
        if p == "/api/plugins/install":
            if d.get("bundled"):
                name = plugins.install_bundled(d["bundled"])
            elif d.get("path"):
                name = plugins.install_dir(d["path"])
            elif d.get("zip_b64"):
                import base64
                name = plugins.install_zip(base64.b64decode(d["zip_b64"]))
            else:
                raise ValueError("nothing to install")
            return {"ok": True, "name": name}
        if p == "/api/plugins/toggle":
            plugins.set_enabled(d["name"], d["enabled"])
        elif p == "/api/plugins/uninstall":
            plugins.uninstall(d["name"])
        elif p == "/api/plugins/create":
            return {"ok": True, "name": plugins.create(d)}
        elif p == "/api/mcp/save":
            plugins.save_mcp(d.get("servers", []))
        elif p == "/api/mcp/test":
            return {"ok": True, "tools": plugins.mcp_test(d["name"])}
        elif p == "/api/claude-desktop/connect":
            return {"ok": True, "path": claude_desktop.connect(d.get("path") or None, load_settings()["host"])}
        elif p == "/api/claude-desktop/disconnect":
            return {"ok": True, "path": claude_desktop.disconnect(d.get("path") or None)}
        elif p == "/api/claude-desktop/import":
            st = claude_desktop.status(d.get("path") or None)
            have = {x["name"] for x in plugins.mcp_servers()}
            pick = set(d.get("names") or [x["name"] for x in st["servers"]])
            merged = plugins.mcp_servers() + [{"name": x["name"], "command": x["command"], "env": x["env"], "enabled": True}
                                              for x in st["servers"] if x["name"] in pick and x["name"] not in have]
            plugins.save_mcp(merged)
            return {"ok": True, "imported": len(merged) - len(have)}
        elif p == "/api/writefile":
            root = Path(d["root"]).resolve()
            f = (root / d["path"]).resolve()
            if f.name not in ("CODER.md", "MARCHAND.md") or f.parent != root:
                raise ValueError("only MARCHAND.md / CODER.md can be written here")
            f.write_text(d["text"], encoding="utf-8")
        return {"ok": True}

    def training_post(self, p, d):
        s = load_settings()
        if p == "/api/training/start":
            self.send_json({"id": trainer.start(s, d)})
        elif p == "/api/training/stop":
            trainer.stop(d.get("id"))
            self.send_json({"ok": True})
        elif p == "/api/training/delete":
            trainer.delete_session(d.get("id"))
            self.send_json({"ok": True})
        elif p == "/api/training/custom":
            self.send_json(trainer.add_custom(d))
        elif p == "/api/training/custom/delete":
            trainer.save_custom([t for t in trainer.custom_tasks() if t["id"] != d.get("id")])
            self.send_json({"ok": True})
        elif p == "/api/training/coder":
            self.sse_start()
            try:
                base = d.get("base") or trainer.recommend_base()
                kind = "reverser" if d.get("kind") == "reverser" else "coder"
                name = d.get("name") or ("marchand-reverser" if kind == "reverser" else "marchand-coder")
                with urllib.request.urlopen(s["host"] + "/api/tags", timeout=10) as r:
                    have = {m["name"] for m in json.loads(r.read()).get("models", [])}
                if base not in have:
                    self.sse({"status": "Downloading %s (one time)..." % base, "pct": 1})
                    req = urllib.request.Request(s["host"] + "/api/pull", json.dumps({"model": base, "stream": True}).encode(), {"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=7200) as r:
                        for raw in r:
                            if raw.strip():
                                ev = json.loads(raw)
                                if ev.get("error"):
                                    raise RuntimeError(ev["error"])
                                pct = int(60 * (ev.get("completed") or 0) / ev["total"]) if ev.get("total") else None
                                self.sse({"status": "Downloading %s: %s" % (base, ev.get("status", "")), "pct": pct})
                trainer.install_coder_pack(s, base, name, self.sse, kind)
            except Exception as ex:
                self.sse({"error": providers.err_text(ex)})
        elif p == "/api/training/save-ai":
            ses = trainer.get_session(d.get("id", "")) or {}
            student = (ses.get("config") or {}).get("student", "")
            prov, base = providers.split_model(student)
            if prov != "ollama":
                raise ValueError("Only local (Ollama) students can be saved as a new AI.")
            name = re.sub(r"[^a-z0-9._-]", "-", str(d.get("name", "")).lower()).strip("-") or "my-trained-ai"
            for _ in teacher.build_model(s, base, name, ["python", "general"], {"persona": trainer.pack.PERSONA, "include_lessons": True, "examples": 3,
                                                                                "temperature": 0.2, "num_ctx": int(s["num_ctx"])}):
                pass
            teacher.save_ai({"name": name, "base": base, "persona": trainer.pack.PERSONA, "include_lessons": True, "examples": 3, "temperature": 0.2,
                             "num_ctx": int(s["num_ctx"]), "created": int(time.time()), "lessons": len(teacher.lessons()), "training": d.get("id")})
            self.send_json({"ok": True, "name": name})
        elif p == "/api/training/import-model":
            path = Path(str(d.get("path", "")).strip().strip('"'))
            name = re.sub(r"[^a-z0-9._-]", "-", str(d.get("name", "")).strip().lower()).strip("-")
            if not path.is_file() or path.suffix.lower() != ".gguf":
                self.send_json({"error": "Choose an existing .gguf model file."}, 400)
            elif not name:
                self.send_json({"error": "Give the model a name."}, 400)
            else:
                try:
                    finetune.import_gguf(s, str(path), name, str(d.get("system", "")))
                    self.send_json({"ok": True, "name": name})
                except Exception as ex:
                    self.send_json({"error": providers.err_text(ex)}, 502)
        elif p == "/api/finetune/start":
            self.send_json({"id": finetune.start(s, d)})
        elif p == "/api/finetune/stop":
            finetune.stop(d.get("id"))
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "not found"}, 404)

    def apply_software(self, d):
        s = load_settings()
        for r in software.scan():
            if r["app"] != d.get("app"):
                continue
            if r["kind"] == "llm-openai":
                provs = dict(s.get("providers") or {})
                provs[r["app"]] = {"enabled": True, "base": r["base"], "key": (provs.get(r["app"]) or {}).get("key", "")}
                save_settings({"providers": provs})
                MODEL_CACHE.clear()
                return {"ok": True, "message": "%s added. Its models are in the model picker." % r["name"]}
            if r.get("image") and r.get("api"):
                imgs = dict(s.get("images") or {})
                imgs["forge_url" if r["image"] == "forge" else "comfy_url"] = r["url"]
                save_settings({"images": imgs})
                return {"ok": True, "message": "%s will be used for images (Images tab)." % r["name"]}
            return {"ok": False, "message": r.get("hint") or "Nothing to set up for this app."}
        return {"ok": False, "message": "That app is no longer running."}

    def image_stream(self, data):
        s = load_settings()
        run_id = uuid.uuid4().hex[:10]
        run = Run()
        RUNS[run_id] = run
        self.sse_start()
        alive = {"ok": True}

        def emit(ev):
            if not alive["ok"]:
                run.cancel.set()
                return
            try:
                self.sse(ev)
            except (BrokenPipeError, ConnectionResetError, OSError):
                alive["ok"] = False
                run.cancel.set()
        emit({"type": "start", "run": run_id})
        try:
            images.generate(s, data, emit, run.cancel)
            emit({"type": "done"})
        except images.Cancelled:
            emit({"type": "done", "cancelled": True})
        except Exception as ex:
            emit({"type": "error", "text": providers.err_text(ex)})
        finally:
            RUNS.pop(run_id, None)

    def cc_run(self, data, s, run, run_id, emit, mode, root):
        model = providers.split_model(data["model"])[1]
        effort = data.get("effort") or s.get("cc_effort") or "high"
        if mode == "code":
            if not Path(root).is_dir():
                raise RuntimeError("Project folder not found: %s" % root)
            if s["auto_approve"]:
                perm = ["--permission-mode", "bypassPermissions"]
            else:
                perm = ["--permission-mode", "default", "--permission-prompt-tool", "mcp__marchand__approve",
                        "--mcp-config", claude_code.perm_config("http://127.0.0.1:%d" % PORT["n"], TOKEN, run_id)]
            extra = s.get("system_extra", "")
            mf = Path(root) / "MARCHAND.md"
            if mf.is_file():
                extra += "\n\nProject instructions (MARCHAND.md):\n" + mf.read_text(errors="replace")[:6000]
            cwd, tools = root, True
        else:
            perm, extra, tools = None, s.get("system_extra", ""), False
            cwd = DATA / "cc-chat"
            cwd.mkdir(parents=True, exist_ok=True)
        resume = data.get("cc_session")
        add_dirs = [d for d in (data.get("extra_dirs") or []) if isinstance(d, str) and Path(d).is_dir()] if mode == "code" else []
        try:
            try:
                st = claude_code.stream(claude_code.build_args(model, effort, tools=tools, resume=resume, append=extra.strip() or None, perm=perm, add_dirs=add_dirs),
                                        cwd, data.get("user", ""), data.get("images"), emit, run.cancel)
            except RuntimeError as ex:
                if not resume or "conversation" not in str(ex).lower():
                    raise
                emit({"type": "status", "text": "Could not continue the previous Claude session here; starting a fresh one."})
                st = claude_code.stream(claude_code.build_args(model, effort, tools=tools, append=extra.strip() or None, perm=perm, add_dirs=add_dirs),
                                        cwd, data.get("user", ""), data.get("images"), emit, run.cancel)
        except claude_code.Cancelled:
            emit({"type": "done", "history": data.get("history", []), "cancelled": True, "cc_session": resume})
            return
        hist = data.get("history", []) + [{"role": "user", "content": data.get("user", "")}, {"role": "assistant", "content": st["text"]}]
        emit({"type": "done", "history": hist, "cc_session": st["session"]})

    def ollama_post(self, path, body, method="POST"):
        s = load_settings()
        req = urllib.request.Request(s["host"] + path, json.dumps(body).encode(), {"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                res = json.loads(raw) if raw.strip().startswith(b"{") else {}
                if "error" not in res:
                    res.setdefault("ok", True)
                self.send_json(res)
        except Exception as ex:
            self.send_json({"error": providers.err_text(ex)}, 502)

    def model_groups(self, refresh=None):
        s = load_settings()
        groups, err = [], ""
        try:
            with urllib.request.urlopen(s["host"] + "/api/tags", timeout=5) as r:
                tags = json.loads(r.read()).get("models", [])
            mine = {x["name"].split(":")[0] for x in teacher.ais()}
            groups.append({"provider": "ollama", "label": providers.LABELS["ollama"], "kind": "local",
                           "models": [{"id": m["name"], "name": m["name"], "size": m.get("size", 0), "mine": m["name"].split(":")[0] in mine} for m in tags]})
        except Exception as ex:
            err = "Cannot reach Ollama at %s (%s)" % (s["host"], ex)
            groups.append({"provider": "ollama", "label": providers.LABELS["ollama"], "kind": "local", "models": []})
        if claude_code.exe():
            groups.append({"provider": "claude-code", "label": providers.LABELS["claude-code"], "kind": "claude",
                           "models": [{"id": "claude-code" + providers.SEP + m, "name": label} for m, label in claude_code.MODELS]})
        for prov, conf in (s.get("providers") or {}).items():
            if prov in providers.LOCAL_SERVERS:
                if not conf.get("enabled"):
                    continue
            elif not conf.get("key") and prov != "custom":
                continue
            ck = (prov, conf.get("key"), conf.get("base"))
            hit = MODEL_CACHE.get(ck)
            if not hit or time.time() - hit[0] > 300 or refresh:
                hit = (time.time(), providers.list_models(s, prov))
                MODEL_CACHE[ck] = hit
            if hit[1]:
                groups.append({"provider": prov, "label": providers.LABELS.get(prov, prov),
                               "kind": "claude" if prov == "anthropic" else ("local" if prov in providers.LOCAL_SERVERS else "cloud"),
                               "models": [{"id": prov + providers.SEP + m, "name": m} for m in hit[1]]})
        return {"groups": groups, "ollama_error": err}

    def teach_evaluate(self, data):
        s = load_settings()
        tm = s.get("teacher_model")
        if not tm:
            return self.send_json({"error": "Choose a teacher model first (Teach tab)."}, 400)
        try:
            langs = engine.detect_languages(data["project"]) if data.get("project") and Path(data["project"]).is_dir() else []
            res = teacher.evaluate(s, tm, data.get("history", []), langs)
            self.send_json(res)
        except Exception as ex:
            self.send_json({"error": providers.err_text(ex)}, 502)

    def build_model_stream(self, data):
        s = load_settings()
        self.sse_start()
        try:
            name = re.sub(r"[^a-z0-9._-]", "-", str(data["name"]).strip().lower()).strip("-")
            if not name:
                raise ValueError("Give your AI a name.")
            profile = {"name": name, "base": data["base"], "persona": data.get("persona", ""), "include_lessons": bool(data.get("include_lessons", True)),
                       "examples": int(data.get("examples", 0)), "temperature": float(data.get("temperature", 0.2)),
                       "num_ctx": int(data.get("num_ctx", 16384)), "created": int(time.time()),
                       "lessons": len([l for l in teacher.lessons() if l.get("enabled", True)])}
            for ev in teacher.build_model(s, data["base"], name, data.get("langs") or [], profile):
                self.sse(ev)
            teacher.save_ai(profile)
            self.sse({"status": "success", "done": True, "name": name})
        except Exception as ex:
            self.sse({"error": providers.err_text(ex)})

    def proxy_get(self, path):
        s = load_settings()
        try:
            with urllib.request.urlopen(s["host"] + path, timeout=10) as r:
                self.send_json(json.loads(r.read()))
        except Exception as ex:
            self.send_json({"error": "Cannot reach Ollama at %s (%s)" % (s["host"], ex)}, 502)

    def sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def sse(self, obj):
        self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
        self.wfile.flush()

    def pull_stream(self, data):
        s = load_settings()
        self.sse_start()
        req = urllib.request.Request(s["host"] + "/api/pull", json.dumps({"model": data.get("model"), "stream": True}).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                for raw in r:
                    if raw.strip():
                        self.sse(json.loads(raw))
        except Exception as ex:
            self.sse({"error": str(ex)})

    def run_stream(self, data):
        s = load_settings()
        run_id = uuid.uuid4().hex[:10]
        run = Run()
        RUNS[run_id] = run
        mode = data.get("mode", "chat")
        root = data.get("project") or s["project"]
        extra_dirs = [d for d in (data.get("extra_dirs") or []) if isinstance(d, str) and Path(d).is_dir()]
        cfg = {"settings": s, "host": s["host"], "model": data.get("model"), "extra_dirs": extra_dirs, "num_ctx": int(s["num_ctx"]),
               "temperature": float(s["temperature"]), "max_steps": int(s["max_steps"]),
               "critic": bool(s["critic"]), "task": data.get("user", ""),
               "critic_model": s.get("teacher_model") if s.get("critic_with_teacher") and s.get("teacher_model") else None}
        self.sse_start()
        alive = {"ok": True}

        def emit(ev):
            if not alive["ok"]:
                run.cancel.set()
                return
            try:
                self.sse(ev)
            except (BrokenPipeError, ConnectionResetError, OSError):
                alive["ok"] = False
                run.cancel.set()

        def approve(kind, detail, diff):
            if s["auto_approve"] or run.always:
                return True
            aid = uuid.uuid4().hex[:8]
            slot = {"event": threading.Event(), "allow": False}
            run.pending[aid] = slot
            emit({"type": "approval", "id": aid, "kind": kind, "detail": detail, "diff": diff})
            slot["event"].wait(900)
            run.pending.pop(aid, None)
            return slot["allow"] and not run.cancel.is_set()

        emit({"type": "start", "run": run_id})
        run.approve = approve
        messages = []
        try:
            if providers.split_model(cfg["model"] or "")[0] == "claude-code":
                return self.cc_run(data, s, run, run_id, emit, mode, root)
            if data.get("images") and not has_vision(s, cfg["model"] or ""):
                if s.get("vision_model"):
                    emit({"type": "status", "text": "%s cannot see images, so %s describes them first." % (cfg["model"], s["vision_model"])})
                    desc = describe_images(s, data["images"], data.get("user", ""))
                    data["user"] = data.get("user", "") + "\n\n[What the attached image(s) show, described by %s]\n%s" % (s["vision_model"], desc)
                else:
                    emit({"type": "status", "text": "%s cannot see images. Pick a vision model in Settings so Marchand can describe them for it." % cfg["model"]})
                data["images"] = []
            extra = plugins.runtime(root, approve) if mode == "code" else None
            plug_sys = (extra or {}).get("system", "")
            langs = engine.detect_languages(root) if mode == "code" and Path(root).is_dir() else []
            plug_sys += "\n\n" + teacher.lessons_prompt(langs or ["general"])
            tm = s.get("teacher_model")

            def add_tool(name, description, props, required, fn):
                extra["schemas"].append({"type": "function", "function": {"name": name, "description": description,
                                                                          "parameters": {"type": "object", "properties": props, "required": required}}})
                extra["names"].add(name)
                prev = extra["handle"]

                def handle(n, args, tools, _p=prev, _n=name, _f=fn):
                    if n != _n:
                        return _p(n, args, tools)
                    return _f(args if isinstance(args, dict) else json.loads(args or "{}"), tools)
                extra["handle"] = handle
            if extra is not None and tm:
                def ask(a, tools):
                    q = a.get("question", "")
                    if not approve("teacher", "Ask %s: %s" % (tm, q[:200]), None):
                        return "denied by user"
                    return teacher.ask_teacher(s, tm, q, teacher.transcript(messages[1:]))
                add_tool("ask_teacher", "Ask the teacher AI (a stronger cloud model) when you are stuck after two failed attempts. Costs money and sends code to the cloud, so use sparingly.",
                         {"question": {"type": "string"}}, ["question"], ask)
                plug_sys += "\n\nYou can call ask_teacher(question) if you are stuck after two failed attempts."
            img_backend = None
            if extra is not None:
                try:
                    img_backend = images.default_backend(s)
                except Exception:
                    img_backend = None
            if extra is not None and img_backend:
                def make_image(a, tools):
                    if not approve("tool", "generate_image: " + str(a.get("prompt", ""))[:160], None):
                        return "denied by user"
                    recs = images.generate(s, {"prompt": a.get("prompt", ""), "width": a.get("width", 1024), "height": a.get("height", 1024)}, lambda e: None, threading.Event())
                    rel = a.get("path") or "generated/" + recs[0]["name"]
                    target = tools.safe(rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(images.read_image(recs[0]["name"]))
                    return "Saved the image to %s (made with %s)." % (rel, img_backend)
                add_tool("generate_image", "Generate a picture with the local image generator and save it in the project (for example a game asset or icon).",
                         {"prompt": {"type": "string"}, "path": {"type": "string", "description": "relative output path, e.g. assets/icon.png"},
                          "width": {"type": "integer"}, "height": {"type": "integer"}}, ["prompt"], make_image)
                plug_sys += "\n\nYou can create pictures with generate_image(prompt, path)."
            if mode == "code":
                if not Path(root).is_dir():
                    raise RuntimeError("Project folder not found: %s" % root)
                for err in extra["errors"]:
                    emit({"type": "status", "text": err})
                system = engine.build_system(root, "code", cfg["num_ctx"], s["system_extra"] + "\n\n" + plug_sys, extra_dirs)
            else:
                system = engine.build_system(None, "chat", cfg["num_ctx"], s["system_extra"])
            history = data.get("history", [])
            umsg = {"role": "user", "content": data.get("user", "")}
            if data.get("images"):
                umsg["images"] = data["images"]
            messages = [{"role": "system", "content": system}] + history + [umsg]
            if mode == "code":
                engine.run_code(cfg, messages, root, emit, run.cancel, approve, extra)
            else:
                engine.run_chat(cfg, messages, emit, run.cancel)
            emit({"type": "done", "history": messages[1:]})
        except engine.Cancelled:
            emit({"type": "done", "history": messages[1:], "cancelled": True})
        except urllib.error.URLError as ex:
            emit({"type": "error", "text": "Cannot reach Ollama at %s. Is it running? (%s)" % (cfg["host"], ex)})
        except Exception as ex:
            emit({"type": "error", "text": str(ex)})
        finally:
            RUNS.pop(run_id, None)


def make_server(port=8765):
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    PORT["n"] = srv.server_address[1]
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = make_server(a.port)
    url = "http://127.0.0.1:%d" % PORT["n"]
    print("Marchand running at " + url + "  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
