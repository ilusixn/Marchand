import difflib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
USAGE = DATA / "claude_usage.json"
MODELS = [("opus", "Opus (latest)"), ("sonnet", "Sonnet (latest)"), ("fable", "Fable (latest)"), ("haiku", "Haiku (latest)"),
          ("claude-opus-5-5", "claude-opus-5-5"), ("claude-sonnet-5-5", "claude-sonnet-5-5"), ("claude-fable-5-1", "claude-fable-5-1"),
          ("claude-haiku-5-5", "claude-haiku-5-5")]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
TOOL_MAP = {"Read": "read_file", "Edit": "edit_file", "MultiEdit": "edit_file", "Write": "write_file", "Bash": "run_command",
            "Grep": "search", "Glob": "list_files", "TodoWrite": "plan", "NotebookEdit": "edit_file"}


class Cancelled(Exception):
    pass


def candidates():
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    appdata = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    win = sys.platform.startswith("win")
    names = ["claude.exe", "claude.cmd"] if win else ["claude"]
    fixed = [home / ".local" / "bin", home / ".claude" / "local", appdata / "npm", home / ".npm-global" / "bin", Path("/usr/local/bin"), Path("/opt/homebrew/bin")]
    out = [d / n for d in fixed for n in names]
    bundles = [appdata / "Claude" / "claude-code", local / "AnthropicClaude", home / "Library" / "Application Support" / "Claude" / "claude-code",
               home / ".config" / "Claude" / "claude-code"]
    for b in bundles:
        if b.is_dir():
            found = [p for n in names for p in b.glob("**/" + n) if p.is_file()]
            out += sorted(found, key=lambda p: [int(x) if x.isdigit() else 0 for x in __import__("re").split(r"(\d+)", str(p))], reverse=True)
    for ext in sorted((home / ".vscode" / "extensions").glob("anthropic.claude-code-*"), reverse=True) if (home / ".vscode" / "extensions").is_dir() else []:
        out += [p for n in names for p in ext.glob("**/" + n) if p.is_file()]
    return out


def saved_path():
    try:
        return json.loads((DATA / "settings.json").read_text(encoding="utf-8")).get("claude_path") or ""
    except (OSError, json.JSONDecodeError):
        return ""


def exe():
    for p in (os.environ.get("MARCHAND_CLAUDE"), saved_path(), shutil.which("claude")):
        if p and Path(p).is_file():
            return p
    for p in candidates():
        if p.is_file():
            return str(p)
    return None


def status():
    e = exe()
    if not e:
        return {"installed": False}
    try:
        v = subprocess.run([e, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        v = ""
    return {"installed": True, "path": e, "version": v, "usage": usage()}


def usage():
    try:
        return json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_usage(info=None, cost=None, window=None):
    u = usage()
    if info:
        u["rate"] = info
        u["rate_time"] = int(time.time())
    if cost is not None:
        u["last_cost"] = cost
        day = time.strftime("%Y-%m-%d")
        if u.get("day") != day:
            u["day"], u["today_cost"], u["today_runs"] = day, 0.0, 0
        u["today_cost"] = round(u.get("today_cost", 0) + cost, 6)
        u["today_runs"] = u.get("today_runs", 0) + 1
    if window:
        u["window"] = window
    DATA.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(u), encoding="utf-8")
    return u


def file_diff(path, old, new):
    d = difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), "a/" + path, "b/" + path, lineterm="", n=2)
    return "\n".join(d)


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def edit_preview(tool, inp):
    path = inp.get("file_path") or inp.get("notebook_path") or ""
    cur = read_text(path) if path else None
    name = os.path.basename(path)
    if tool == "Write":
        return file_diff(name, cur or "", inp.get("content", ""))
    edits = [inp] if tool == "Edit" else inp.get("edits", [])
    if cur is None:
        return "\n\n".join(file_diff(name, e.get("old_string", ""), e.get("new_string", "")) for e in edits)
    new = cur
    for e in edits:
        old_s, new_s = e.get("old_string", ""), e.get("new_string", "")
        new = new.replace(old_s, new_s) if e.get("replace_all") else new.replace(old_s, new_s, 1)
    return file_diff(name, cur, new)


def edit_result_diff(tool, inp):
    path = inp.get("file_path", "")
    cur = read_text(path) if path else None
    name = os.path.basename(path)
    if tool == "Write" or cur is None:
        return file_diff(name, "", inp.get("content", "")) if tool == "Write" else file_diff(name, inp.get("old_string", ""), inp.get("new_string", ""))
    edits = [inp] if tool == "Edit" else inp.get("edits", [])
    old = cur
    for e in reversed(edits):
        if e.get("new_string", "") in old:
            old = old.replace(e.get("new_string", ""), e.get("old_string", ""), 1)
    return file_diff(name, old, cur)


def user_line(text, images):
    content = [{"type": "text", "text": text}]
    for b64 in images or []:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png" if b64.startswith("iVBOR") else "image/jpeg", "data": b64}})
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"


def perm_config(server_url, token, run_id):
    return json.dumps({"mcpServers": {"marchand": {"command": sys.executable, "args": [str(HERE / "cc_perm_mcp.py")],
                                                   "env": {"MARCHAND_URL": server_url, "MARCHAND_TOKEN": token, "MARCHAND_RUN": run_id}}}})


def build_args(model, effort=None, tools=True, resume=None, system=None, append=None, perm=None, persist=True, max_turns=None, add_dirs=()):
    e = exe()
    if not e:
        raise RuntimeError("Claude Code is not installed. Install it from claude.ai/code and log in once with `claude`, then restart Marchand.")
    a = [e, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--input-format", "stream-json", "--model", model]
    if effort in EFFORTS:
        a += ["--effort", effort]
    if not tools:
        a += ["--tools", ""]
    if resume:
        a += ["--resume", resume]
    if system:
        a += ["--system-prompt", system]
    if append:
        a += ["--append-system-prompt", append]
    if perm:
        a += perm
    for d in add_dirs or []:
        a += ["--add-dir", str(d)]
    if not persist:
        a += ["--no-session-persistence"]
    if max_turns:
        a += ["--max-turns", str(max_turns)]
    return a


def stream(args, cwd, text, images, on_event, cancel):
    proc = subprocess.Popen(args, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    proc.stdin.write(user_line(text, images))
    proc.stdin.close()
    err_lines = []
    err_reader = threading.Thread(target=lambda: err_lines.extend(proc.stderr.readlines()), daemon=True)
    err_reader.start()
    stopper = threading.Thread(target=lambda: (cancel.wait(), proc.poll() is None and proc.kill()), daemon=True)
    stopper.start()
    st = {"session": None, "text": "", "result": None, "tools": {}, "model": None, "is_error": False}
    for line in proc.stdout:
        if cancel.is_set():
            break
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            st["session"], st["model"] = e.get("session_id"), e.get("model")
            on_event({"type": "cc_init", "session": st["session"], "model": st["model"]})
        elif t == "autocompact_state":
            w = (e.get("value") or {}).get("effective_window")
            if w:
                save_usage(window=w)
        elif t == "stream_event":
            ev = e.get("event", {})
            if ev.get("type") == "content_block_delta" and not e.get("parent_tool_use_id"):
                d = ev.get("delta", {})
                if d.get("type") == "text_delta":
                    st["text"] += d.get("text", "")
                    on_event({"type": "token", "text": d.get("text", "")})
                elif d.get("type") == "thinking_delta":
                    on_event({"type": "thinking", "text": d.get("thinking", "")})
            elif ev.get("type") == "message_start" and not e.get("parent_tool_use_id"):
                on_event({"type": "turn"})
        elif t == "assistant" and not e.get("parent_tool_use_id"):
            for blk in e.get("message", {}).get("content", []):
                if blk.get("type") == "tool_use":
                    st["tools"][blk["id"]] = (blk.get("name"), blk.get("input") or {})
                    on_event({"type": "tool", "name": blk.get("name"), "args": blk.get("input") or {}, "id": blk["id"]})
        elif t == "user" and not e.get("parent_tool_use_id"):
            content = e.get("message", {}).get("content", [])
            for blk in content if isinstance(content, list) else []:
                if blk.get("type") != "tool_result":
                    continue
                name, inp = st["tools"].get(blk.get("tool_use_id"), ("tool", {}))
                c = blk.get("content")
                text = c if isinstance(c, str) else "\n".join(x.get("text", "") for x in (c or []) if isinstance(x, dict))
                if name in ("Edit", "MultiEdit", "Write") and not blk.get("is_error"):
                    on_event({"type": "diff", "path": inp.get("file_path", ""), "diff": edit_result_diff(name, inp)})
                on_event({"type": "tool_result", "name": name, "text": ("error: " if blk.get("is_error") else "") + text[:6000]})
        elif t == "rate_limit_event":
            info = e.get("rate_limit_info") or {}
            save_usage(info=info)
            on_event({"type": "usage", "rate": info})
        elif t == "result":
            st["result"] = e
            st["is_error"] = bool(e.get("is_error"))
            cost = e.get("total_cost_usd")
            u = save_usage(cost=cost if isinstance(cost, (int, float)) else None)
            on_event({"type": "cc_result", "cost": cost, "usage": e.get("usage"), "duration_ms": e.get("duration_ms"),
                      "session": e.get("session_id"), "error": st["is_error"], "subtype": e.get("subtype"), "today_cost": u.get("today_cost")})
    proc.wait()
    err_reader.join(10)
    if cancel.is_set():
        raise Cancelled()
    if st["result"] is None and proc.returncode:
        msg = "".join(err_lines).strip()[-600:] or "Claude Code exited with code %s" % proc.returncode
        if "login" in msg.lower() or "auth" in msg.lower():
            msg += "\nOpen a terminal, run `claude` once and log in with your Claude account."
        raise RuntimeError(msg)
    if st["is_error"]:
        r = st["result"]
        raise RuntimeError("Claude Code: %s" % (r.get("result") or r.get("subtype") or "error"))
    return st


def chat_stream(model, messages, on_piece, cancel, effort=None):
    system = "\n\n".join(m.get("content") or "" for m in messages if m["role"] == "system").strip()
    convo = [m for m in messages if m["role"] in ("user", "assistant", "tool")]
    images = []
    if len(convo) == 1 and convo[0]["role"] == "user":
        text = convo[0].get("content") or ""
        images = convo[0].get("images") or []
    else:
        parts = []
        for m in convo:
            who = {"user": "User", "assistant": "Assistant", "tool": "Tool result"}[m["role"]]
            parts.append("%s: %s" % (who, m.get("content") or ""))
            images += m.get("images") or []
        text = "Continue this conversation. Reply as the Assistant to the last User message.\n\n" + "\n\n".join(parts)
    args = build_args(model, effort, tools=False, system=system or "You are a helpful assistant.", persist=False, max_turns=1)
    cwd = DATA / "cc-chat"
    cwd.mkdir(parents=True, exist_ok=True)
    st = stream(args, cwd, text, images, lambda e: e["type"] in ("token", "thinking") and on_piece(e["type"], e["text"]), cancel)
    return st["text"], []


def to_marchand(tool, inp, root):
    def rel(p):
        try:
            return os.path.relpath(p, root) if p and os.path.isabs(p) else p
        except ValueError:
            return p
    if tool == "Read":
        a = {"path": rel(inp.get("file_path"))}
        if inp.get("offset"):
            a["start"] = inp["offset"]
            if inp.get("limit"):
                a["end"] = inp["offset"] + inp["limit"]
        return [("read_file", a)]
    if tool == "Edit":
        return [("edit_file", {"path": rel(inp.get("file_path")), "old": inp.get("old_string", ""), "new": inp.get("new_string", "")})]
    if tool == "MultiEdit":
        return [("edit_file", {"path": rel(inp.get("file_path")), "old": x.get("old_string", ""), "new": x.get("new_string", "")}) for x in inp.get("edits", [])]
    if tool == "Write":
        return [("write_file", {"path": rel(inp.get("file_path")), "content": inp.get("content", "")})]
    if tool == "Bash":
        return [("run_command", {"command": inp.get("command", "")})]
    if tool == "Grep":
        return [("search", {"pattern": inp.get("pattern", ""), "glob": inp.get("glob") or "*"})]
    if tool == "Glob":
        return [("list_files", {"path": "."})]
    if tool == "TodoWrite":
        return [("plan", {"items": [{"text": t.get("content", ""), "done": t.get("status") == "completed"} for t in inp.get("todos", [])]})]
    return []


def run_agent_capture(model, effort, cwd, prompt, cancel, on_log, max_turns=40, append=None):
    args = build_args(model, effort, tools=True, append=append, persist=False, max_turns=max_turns,
                      perm=["--permission-mode", "bypassPermissions"])
    hist = [{"role": "user", "content": prompt}]
    pending = {}

    def on(e):
        if e["type"] == "tool":
            on_log("  %s %s" % (e["name"], str((e.get("args") or {}).get("file_path") or (e.get("args") or {}).get("command") or "")[:80]))
            mapped = to_marchand(e["name"], e.get("args") or {}, str(cwd))
            if mapped:
                hist.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": n, "arguments": a}} for n, a in mapped]})
                pending[e["id"]] = [n for n, _ in mapped]
        elif e["type"] == "tool_result":
            for key in list(pending):
                names = pending.pop(key)
                for n in names:
                    hist.append({"role": "tool", "tool_name": n, "content": e["text"][:4000]})
                break
    st = stream(args, cwd, prompt, [], on, cancel)
    final = st["text"].strip() or "Done."
    hist.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "finish", "arguments": {"summary": final[:1500]}}}]})
    hist.append({"role": "tool", "tool_name": "finish", "content": final[:1500]})
    return hist
