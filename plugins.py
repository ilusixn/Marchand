import base64
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLED = HERE / "bundled"
DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
PLUG_DIR = DATA / "plugins"
STATE = DATA / "plugins_state.json"
NAME_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def load_state():
    try:
        s = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        s = {}
    s.setdefault("enabled", {})
    s.setdefault("mcp", [])
    return s


def save_state(s):
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def read_manifest(folder):
    f = Path(folder) / "plugin.json"
    m = json.loads(f.read_text(encoding="utf-8"))
    if not NAME_RX.match(str(m.get("name", ""))):
        raise ValueError("plugin name must be lowercase letters, digits, - or _")
    m.setdefault("version", "1.0.0")
    m.setdefault("description", "")
    m.setdefault("commands", [])
    m.setdefault("skills", [])
    m.setdefault("tools", [])
    m.setdefault("system", "")
    return m


def skill_text(folder, skill):
    f = Path(folder) / skill.get("file", "")
    if f.is_file() and Path(folder).resolve() in f.resolve().parents:
        return f.read_text(encoding="utf-8")
    return skill.get("text", "")


def installed():
    out = []
    state = load_state()
    if PLUG_DIR.is_dir():
        for d in sorted(PLUG_DIR.iterdir()):
            if (d / "plugin.json").is_file():
                try:
                    m = read_manifest(d)
                except (ValueError, json.JSONDecodeError, OSError):
                    continue
                m["enabled"] = bool(state["enabled"].get(m["name"], True))
                m["path"] = str(d)
                out.append(m)
    return out


def available():
    have = {m["name"] for m in installed()}
    out = []
    if BUNDLED.is_dir():
        for d in sorted(BUNDLED.iterdir()):
            if (d / "plugin.json").is_file():
                m = read_manifest(d)
                m["installed"] = m["name"] in have
                out.append(m)
    return out


def install_dir(src):
    src = Path(src).expanduser()
    m = read_manifest(src)
    dst = PLUG_DIR / m["name"]
    PLUG_DIR.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    s = load_state()
    s["enabled"][m["name"]] = True
    save_state(s)
    return m["name"]


def install_bundled(name):
    if not NAME_RX.match(name):
        raise ValueError("bad name")
    return install_dir(BUNDLED / name)


def install_zip(data):
    tmp = DATA / "_unzip"
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            target = (tmp / n).resolve()
            if tmp.resolve() not in target.parents and target != tmp.resolve():
                raise ValueError("unsafe path in zip")
        z.extractall(tmp)
    root = tmp
    if not (root / "plugin.json").is_file():
        subs = [d for d in tmp.iterdir() if d.is_dir() and (d / "plugin.json").is_file()]
        if not subs:
            raise ValueError("no plugin.json found in the zip")
        root = subs[0]
    name = install_dir(root)
    shutil.rmtree(tmp, ignore_errors=True)
    return name


def uninstall(name):
    if not NAME_RX.match(name):
        raise ValueError("bad name")
    shutil.rmtree(PLUG_DIR / name, ignore_errors=True)
    s = load_state()
    s["enabled"].pop(name, None)
    save_state(s)


def set_enabled(name, on):
    s = load_state()
    s["enabled"][name] = bool(on)
    save_state(s)


def create(data):
    name = str(data.get("name", "")).strip().lower().replace(" ", "-")
    if not NAME_RX.match(name):
        raise ValueError("name must be lowercase letters, digits, - or _")
    m = {"name": name, "version": "1.0.0", "description": data.get("description", ""), "author": "me",
         "system": data.get("system", ""), "commands": [], "skills": [], "tools": []}
    if data.get("command_name") and data.get("command_prompt"):
        m["commands"].append({"name": data["command_name"].strip().lstrip("/"), "description": data.get("command_desc", ""),
                              "prompt": data["command_prompt"]})
    d = PLUG_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    set_enabled(name, True)
    return name


def commands():
    out = []
    for m in installed():
        if m["enabled"]:
            for c in m["commands"]:
                out.append({"name": c["name"], "description": c.get("description", ""), "prompt": c["prompt"], "plugin": m["name"]})
    return out


class McpClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None
        self.next_id = 0
        self.waiting = {}
        self.lock = threading.Lock()
        self.tools = []
        self.dead = False

    def start(self):
        env = dict(os.environ)
        env.update({str(k): str(v) for k, v in (self.cfg.get("env") or {}).items()})
        self.proc = subprocess.Popen(self.cfg["command"], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)
        threading.Thread(target=self.reader, daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                "clientInfo": {"name": "marchand", "version": "1.0"}}, 30)
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.tools = (self.rpc("tools/list", {}, 30) or {}).get("tools", [])

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def reader(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            slot = self.waiting.get(msg.get("id"))
            if slot is not None:
                slot["msg"] = msg
                slot["event"].set()
        self.dead = True
        for slot in list(self.waiting.values()):
            slot["msg"] = {"error": {"message": "connector process exited"}}
            slot["event"].set()

    def rpc(self, method, params, timeout=60):
        with self.lock:
            self.next_id += 1
            rid = self.next_id
        slot = {"event": threading.Event(), "msg": None}
        if self.dead:
            raise RuntimeError("connector process exited")
        self.waiting[rid] = slot
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        if not slot["event"].wait(timeout):
            self.waiting.pop(rid, None)
            raise TimeoutError("MCP server did not answer %s" % method)
        self.waiting.pop(rid, None)
        msg = slot["msg"]
        if "error" in msg:
            raise RuntimeError(msg["error"].get("message", "MCP error"))
        return msg.get("result")

    def call(self, name, args):
        res = self.rpc("tools/call", {"name": name, "arguments": args or {}}, 120) or {}
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return ("error: " + text) if res.get("isError") else text

    def stop(self):
        if self.proc:
            self.proc.kill()


MCP_LIVE = {}


MCP_FAIL = {}


def mcp_client(cfg, timeout=15):
    key = json.dumps(cfg, sort_keys=True)
    c = MCP_LIVE.get(key)
    if c and c.proc and c.proc.poll() is None and not c.dead:
        return c
    failed = MCP_FAIL.get(key)
    if failed and time.time() - failed[0] < 60:
        raise RuntimeError(failed[1])
    c = McpClient(cfg)
    box = {}

    def go():
        try:
            c.start()
            box["ok"] = True
        except Exception as ex:
            box["err"] = str(ex)
    t = threading.Thread(target=go, daemon=True)
    t.start()
    t.join(timeout)
    if not box.get("ok"):
        c.stop()
        msg = box.get("err") or "did not start within %d seconds" % timeout
        MCP_FAIL[key] = (time.time(), msg)
        raise RuntimeError(msg)
    MCP_LIVE[key] = c
    return c


def mcp_servers():
    return load_state()["mcp"]


def save_mcp(servers):
    s = load_state()
    s["mcp"] = [{"name": re.sub(r"[^a-z0-9_]", "_", str(x.get("name", "")).lower()), "command": str(x.get("command", "")),
                 "env": x.get("env") or {}, "enabled": bool(x.get("enabled", True))} for x in servers if x.get("name") and x.get("command")]
    save_state(s)


def mcp_test(name):
    cfg = next((x for x in mcp_servers() if x["name"] == name), None)
    if not cfg:
        raise ValueError("unknown connector")
    c = mcp_client(cfg)
    return [{"name": t["name"], "description": t.get("description", "")} for t in c.tools]


def runtime(root, approve):
    system, schemas, handlers, skills = [], [], {}, {}
    for m in installed():
        if not m["enabled"]:
            continue
        if m["system"].strip():
            system.append("## Plugin %s\n%s" % (m["name"], m["system"].strip()))
        for sk in m["skills"]:
            skills[sk["name"]] = (sk.get("description", ""), skill_text(m["path"], sk))
        for t in m["tools"]:
            handlers[t["name"]] = ("shell", t)
            props = {k: {"type": v} for k, v in (t.get("parameters") or {}).items()}
            schemas.append({"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                             "parameters": {"type": "object", "properties": props,
                                                                            "required": t.get("required", list(props))}}})
    errors, started = [], []
    pending = [cfg for cfg in mcp_servers() if cfg.get("enabled", True)]
    results = {}

    def boot(cfg):
        try:
            results[cfg["name"]] = mcp_client(cfg)
        except Exception as ex:
            results[cfg["name"]] = ex
    threads = [threading.Thread(target=boot, args=(cfg,), daemon=True) for cfg in pending]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    for cfg in pending:
        c = results.get(cfg["name"])
        if not isinstance(c, McpClient):
            errors.append("Connector %s unavailable: %s" % (cfg["name"], c or "timed out"))
            continue
        for t in c.tools:
            full = "mcp__%s__%s" % (cfg["name"], t["name"])
            handlers[full] = ("mcp", (c, t["name"]))
            schemas.append({"type": "function", "function": {"name": full, "description": t.get("description", "")[:400],
                                                             "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}})
    if skills:
        system.append("## Skills\nCall use_skill(name) to load detailed instructions before a matching task.\n" +
                      "\n".join("- %s: %s" % (n, d) for n, (d, _) in skills.items()))
        schemas.append({"type": "function", "function": {"name": "use_skill", "description": "Load a skill's full instructions.",
                                                         "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                                                                        "required": ["name"]}}})
        handlers["use_skill"] = ("skill", skills)

    def handle(name, args, tools):
        kind, obj = handlers[name]
        if isinstance(args, str):
            args = json.loads(args or "{}")
        args = args or {}
        if kind == "skill":
            sk = obj.get(args.get("name"))
            return sk[1] if sk else "error: unknown skill. Available: " + ", ".join(obj)
        if kind == "mcp":
            c, real = obj
            if not approve("tool", "%s %s" % (name, json.dumps(args)[:200]), None):
                return "denied by user"
            return c.call(real, args)
        t = obj
        cmd = t["command"]
        quote = (lambda v: subprocess.list2cmdline([v])) if os.name == "nt" else shlex.quote
        for k in re.findall(r"\{(\w+)\}", cmd):
            cmd = cmd.replace("{%s}" % k, quote(str(args.get(k, ""))))
        return tools.t_run_command(cmd)

    return {"system": "\n\n".join(system), "schemas": schemas, "handle": handle, "names": set(handlers), "errors": errors}
