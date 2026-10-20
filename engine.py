import difflib
import fnmatch
import json
import os
import re
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path

import providers

HERE = Path(__file__).resolve().parent
KNOW = HERE / "knowledge"

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", ".idea", ".vscode", "target",
               ".next", ".cache", "out", "bin", "obj", ".mypy_cache", ".pytest_cache"}
BLOCKED = [r"\brm\s+-rf\s+(/|~|\*)", r"\bmkfs\b", r"\bdd\s+if=", r":\(\)\s*\{", r"\bformat\s+[a-z]:",
           r"\bdel\s+/s\s+/q\s+[a-z]:\\", r"git\s+push\s+.*--force", r"git\s+reset\s+--hard\s+origin"]
MAX_OUT = 8000

LANG_EXT = {
    "python": {".py", ".pyw"}, "javascript": {".js", ".jsx", ".mjs", ".cjs", ".vue"}, "typescript": {".ts", ".tsx"},
    "c": {".c", ".h"}, "cpp": {".cpp", ".hpp", ".cc", ".cxx", ".hh"}, "csharp": {".cs"}, "java": {".java"}, "kotlin": {".kt", ".kts"},
    "go": {".go"}, "rust": {".rs"}, "php": {".php"}, "ruby": {".rb"}, "perl": {".pl", ".pm"}, "lua": {".lua"}, "bash": {".sh", ".bash"},
    "sql": {".sql"}, "swift": {".swift"}, "powershell": {".ps1"},
}
SYMBOL_RX = {
    ".py": re.compile(r"^\s*(?:async\s+)?(def|class)\s+(\w+)"),
    ".js": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(function|class)\s+(\w+)"),
    ".ts": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(function|class|interface|type)\s+(\w+)"),
    ".go": re.compile(r"^(func)\s+(?:\([^)]*\)\s*)?(\w+)"),
    ".rs": re.compile(r"^\s*(?:pub\s+)?(fn|struct|enum|trait)\s+(\w+)"),
    ".java": re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(class|interface|enum)\s+(\w+)"),
    ".cs": re.compile(r"^\s*(?:public|private|internal)?\s*(?:static\s+)?(class|interface|enum|struct)\s+(\w+)"),
    ".lua": re.compile(r"^\s*(?:local\s+)?(function)\s+([\w.:]+)"),
}
SYMBOL_RX[".tsx"] = SYMBOL_RX[".jsx"] = SYMBOL_RX[".mjs"] = SYMBOL_RX[".ts"]
SYMBOL_RX[".kt"] = SYMBOL_RX[".java"]


class Cancelled(Exception):
    pass


def read_know(name):
    f = KNOW / (name + ".md")
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def walk_files(root, limit=100000):
    n = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".git"))
        for f in sorted(files):
            yield Path(dirpath) / f
            n += 1
            if n >= limit:
                return


def detect_languages(root):
    c = Counter()
    for p in walk_files(root, 4000):
        c[p.suffix.lower()] += 1
    langs = []
    for lang, exts in LANG_EXT.items():
        n = sum(c[e] for e in exts)
        if n:
            langs.append((n, lang))
    return [l for _, l in sorted(langs, reverse=True)]


def detect_test_command(root):
    r = Path(root)
    if (r / "package.json").is_file():
        try:
            if "test" in json.loads((r / "package.json").read_text(errors="replace")).get("scripts", {}):
                return "npm test"
        except json.JSONDecodeError:
            pass
    if (r / "Cargo.toml").is_file():
        return "cargo test"
    if (r / "go.mod").is_file():
        return "go test ./..."
    if (r / "pom.xml").is_file():
        return "mvn -q test"
    if (r / "CMakeLists.txt").is_file() and (r / "build").is_dir():
        return "ctest --test-dir build"
    if any((r / n).is_file() for n in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")) or (r / "tests").is_dir():
        return "python -m pytest -q"
    tests = sorted(r.glob("test*.py"))
    if tests:
        return "python " + tests[0].name
    if (r / "composer.json").is_file():
        return "composer test"
    if (r / "build.gradle").is_file() or (r / "build.gradle.kts").is_file():
        return "gradle test"
    if any(r.glob("*.csproj")) or any(r.glob("*.sln")):
        return "dotnet test"
    if (r / "Gemfile").is_file():
        return "bundle exec rake test"
    mk = r / "Makefile"
    if mk.is_file() and re.search(r"^test:", mk.read_text(errors="replace"), re.M):
        return "make test"
    return None


def repo_map(root, max_lines=140):
    lines, files = [], 0
    for p in walk_files(root, 3000):
        rx = SYMBOL_RX.get(p.suffix.lower())
        if not rx or p.stat().st_size > 400000:
            continue
        try:
            text = p.read_text(errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        syms = []
        for line in text.splitlines():
            m = rx.match(line)
            if m:
                syms.append("%s %s" % (m.group(1), m.group(2)))
                if len(syms) >= 12:
                    break
        if syms:
            lines.append("%s: %s" % (p.relative_to(root), "; ".join(syms)))
            files += 1
        if len(lines) >= max_lines or files >= 80:
            break
    return lines


def git_info(root):
    def run(cmd):
        try:
            r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if not branch:
        return ""
    status = run(["git", "status", "--short"])[:800]
    log = run(["git", "log", "--oneline", "-5"])
    return "Git branch: %s\nRecent commits:\n%s\nUncommitted changes:\n%s" % (branch, log, status or "(clean)")


def tree_lines(root, depth, limit):
    out = []
    root = Path(root)
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= depth:
            dirs[:] = []
        for f in sorted(files):
            out.append(str(rel / f) if str(rel) != "." else f)
            if len(out) >= limit:
                out.append("... (more files: use list_files)")
                return out
    return out


def build_system(root, mode, num_ctx, extra="", extra_dirs=()):
    budget = int(num_ctx * 1.1)
    parts = [read_know("core")]
    if mode == "code":
        parts.append(read_know("tools"))
    langs = detect_languages(root) if root else []
    guides = ["lang_" + l for l in langs[:3]] + ["debugging", "reverse", "testing", "review", "git", "security", "refactoring"]
    used = sum(len(p) for p in parts)
    for g in guides:
        text = read_know(g)
        if text and used + len(text) < budget:
            parts.append(text)
            used += len(text)
    if extra.strip():
        parts.append("# User's own instructions\n" + extra.strip())
    if mode == "code" and root:
        facts = ["# This project", "Root folder: " + str(root)]
        if langs:
            facts.append("Main languages: " + ", ".join(langs))
        tc = detect_test_command(root)
        facts.append("Likely test command: " + (tc or "none detected (look for how tests are run)"))
        g = git_info(root)
        if g:
            facts.append(g)
        facts.append("Files:\n" + "\n".join(tree_lines(root, 3, 150)))
        for d in extra_dirs or []:
            if Path(d).is_dir():
                facts.append("Extra folder you may READ (use its absolute path with read_file, list_files and search): %s\nFiles:\n%s" % (d, "\n".join(tree_lines(d, 2, 60))))
        rm = repo_map(root)
        if rm:
            facts.append("Code map (symbols per file):\n" + "\n".join(rm))
        for name in ("MARCHAND.md", "CODER.md", "AGENTS.md", "CLAUDE.md"):
            f = Path(root) / name
            if f.is_file():
                facts.append("Project instructions from %s (follow them):\n%s" % (name, f.read_text(errors="replace")[:4000]))
        parts.append("\n".join(facts))
    return "\n\n".join(parts)


TOOL_SPECS = [
    ("list_files", "List files under a directory (recursive, ignores build folders).",
     {"path": "string", "max_depth": "integer"}, []),
    ("read_file", "Read a text file with line numbers. Use start/end for large files.",
     {"path": "string", "start": "integer", "end": "integer"}, ["path"]),
    ("search", "Regex search in file contents. Returns path:line:text. Optional path: a folder to search (the project by default, or an extra folder).",
     {"pattern": "string", "glob": "string", "path": "string"}, ["pattern"]),
    ("edit_file", "Replace exact text `old` with `new` in a file. `old` must appear exactly once.",
     {"path": "string", "old": "string", "new": "string"}, ["path", "old", "new"]),
    ("write_file", "Create a new file or overwrite a file with full content.",
     {"path": "string", "content": "string"}, ["path", "content"]),
    ("run_command", "Run a shell command in the project root (tests, build, lint). 120 second limit.",
     {"command": "string"}, ["command"]),
    ("plan", "Set or update the task checklist shown to the user. items: list of {text, done}.",
     {"items": "array"}, ["items"]),
    ("ask_user", "Ask the user one short clarifying question and stop.", {"question": "string"}, ["question"]),
    ("finish", "Call when the task is complete and verified.", {"summary": "string"}, ["summary"]),
]


def tool_schemas():
    out = []
    for name, desc, props, req in TOOL_SPECS:
        p = {}
        for k, t in props.items():
            p[k] = {"type": t}
            if t == "array":
                p[k]["items"] = {"type": "object"}
        out.append({"type": "function", "function": {"name": name, "description": desc,
                                                       "parameters": {"type": "object", "properties": p, "required": req}}})
    return out


def diff_text(old, new, path):
    d = difflib.unified_diff((old or "").splitlines(), new.splitlines(), "a/" + path, "b/" + path, lineterm="", n=2)
    return "\n".join(d)


class Tools:
    def __init__(self, root, approve, emit, cancel, extra=None, extra_dirs=()):
        self.extra = extra
        self.extra_dirs = [Path(d).resolve() for d in extra_dirs or [] if Path(d).is_dir()]
        self.root = Path(root).resolve()
        self.approve = approve
        self.emit = emit
        self.cancel = cancel
        self.orig = {}
        self.dirty = False
        self.verified = True
        self.ask = None

    def safe(self, p):
        full = (self.root / (p or ".")).resolve()
        if full != self.root and self.root not in full.parents:
            raise ValueError("path is outside the project: %s" % p)
        return full

    def safe_read(self, p):
        try:
            return self.safe(p)
        except ValueError:
            full = Path(p).expanduser().resolve() if p and Path(p).is_absolute() else None
            if full is not None and any(full == d or d in full.parents for d in self.extra_dirs):
                return full
            raise

    def t_list_files(self, path=".", max_depth=3):
        base = self.safe_read(path)
        if not base.is_dir():
            return "error: not a directory: %s" % path
        return "\n".join(tree_lines(base, int(max_depth or 3), 400)) or "(empty)"

    def t_read_file(self, path, start=1, end=None):
        f = self.safe_read(path)
        if not f.is_file():
            return "error: file not found: %s" % path
        lines = f.read_text(errors="replace").splitlines()
        s = max(int(start or 1), 1)
        e = min(int(end or s + 399), len(lines))
        body = "\n".join("%d\t%s" % (i + 1, lines[i]) for i in range(s - 1, e))
        more = "" if e >= len(lines) else "\n... file has %d lines; use start/end to read more" % len(lines)
        return body + more

    def t_search(self, pattern, glob="*", path="."):
        try:
            rx = re.compile(pattern)
        except re.error as ex:
            return "error: bad regex: %s" % ex
        hits = []
        base = self.safe_read(path)
        for f in walk_files(base, 8000):
            if not fnmatch.fnmatch(f.name, glob or "*"):
                continue
            try:
                for i, line in enumerate(f.read_text(errors="strict").splitlines(), 1):
                    if rx.search(line):
                        hits.append("%s:%d:%s" % (f.relative_to(base) if base == self.root else f, i, line.strip()[:160]))
                        if len(hits) >= 80:
                            return "\n".join(hits) + "\n... (truncated)"
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(hits) or "no matches"

    def t_edit_file(self, path, old, new):
        f = self.safe(path)
        if not f.is_file():
            return "error: file not found: %s" % path
        text = f.read_text(errors="replace")
        n = text.count(old)
        if n == 0:
            return "error: `old` text not found. Read the file again and copy the exact text, including indentation."
        if n > 1:
            return "error: `old` appears %d times. Include more surrounding lines so it is unique." % n
        updated = text.replace(old, new, 1)
        d = diff_text(text, updated, path)
        if not self.approve("edit", path, d):
            return "denied by user"
        self.orig.setdefault(path, text)
        f.write_text(updated)
        self.dirty, self.verified = True, False
        self.emit({"type": "diff", "path": path, "diff": d})
        return "edited %s" % path

    def t_write_file(self, path, content):
        f = self.safe(path)
        before = f.read_text(errors="replace") if f.is_file() else None
        d = diff_text(before, content, path)
        if not self.approve("write", "%s (%d bytes)" % (path, len(content)), d):
            return "denied by user"
        self.orig.setdefault(path, before)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        self.dirty, self.verified = True, False
        self.emit({"type": "diff", "path": path, "diff": d})
        return "wrote %s (%d lines)" % (path, content.count("\n") + 1)

    def t_run_command(self, command):
        for pat in BLOCKED:
            if re.search(pat, command):
                return "error: command blocked for safety"
        if not self.approve("command", command, None):
            return "denied by user"
        try:
            proc = subprocess.Popen(command, shell=True, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace")
            try:
                out, _ = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                return "error: command timed out after 120 seconds"
        except OSError as ex:
            return "error: %s" % ex
        if proc.returncode == 0 and self.dirty:
            self.verified = True
        return "exit code %d\n%s" % (proc.returncode, out)

    def t_plan(self, items):
        if isinstance(items, str):
            items = [{"text": s.strip("- ").strip(), "done": False} for s in items.splitlines() if s.strip()]
        clean = []
        for it in items or []:
            if isinstance(it, str):
                it = {"text": it, "done": False}
            clean.append({"text": str(it.get("text", "")), "done": bool(it.get("done"))})
        self.emit({"type": "plan", "items": clean})
        return "plan updated (%d items)" % len(clean)

    def t_ask_user(self, question):
        self.ask = question
        return question

    def t_finish(self, summary):
        return summary

    def call(self, name, args):
        if self.extra and name in self.extra["names"]:
            try:
                out = str(self.extra["handle"](name, args, self))
            except Exception as ex:
                out = "error: %s" % ex
            return out if len(out) <= MAX_OUT else out[:MAX_OUT] + "\n... (output truncated)"
        fn = getattr(self, "t_" + name, None)
        if fn is None:
            return "error: unknown tool `%s`. Available: %s" % (name, ", ".join(s[0] for s in TOOL_SPECS))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return "error: arguments must be a JSON object"
        try:
            out = fn(**(args or {}))
        except TypeError as ex:
            return "error: bad arguments for %s: %s" % (name, ex)
        except Exception as ex:
            return "error: %s" % ex
        out = str(out)
        return out if len(out) <= MAX_OUT else out[:MAX_OUT] + "\n... (output truncated)"


def ollama_stream(host, body, on_piece, cancel):
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    content, thinking, calls = "", "", []
    with urllib.request.urlopen(req, timeout=900) as resp:
        for raw in resp:
            if cancel.is_set():
                raise Cancelled()
            if not raw.strip():
                continue
            chunk = json.loads(raw)
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            msg = chunk.get("message", {})
            if msg.get("thinking"):
                thinking += msg["thinking"]
                on_piece("thinking", msg["thinking"])
            if msg.get("content"):
                content += msg["content"]
                on_piece("token", msg["content"])
            calls += msg.get("tool_calls") or []
    return content, calls


def ollama_once(host, body):
    body = dict(body, stream=False)
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read()).get("message", {}).get("content", "")


def calls_from_text(text):
    for m in re.finditer(r"\{.*\}", text, re.S):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "name" in obj and ("arguments" in obj or "parameters" in obj):
            return [{"function": {"name": obj["name"], "arguments": obj.get("arguments", obj.get("parameters"))}}]
    return []


def trim(messages, num_ctx):
    total = sum(len(m.get("content") or "") for m in messages)
    if total <= num_ctx * 3:
        return
    for m in messages[1:-8]:
        if m["role"] == "tool" and len(m["content"]) > 400:
            m["content"] = m["content"][:300] + "\n... (old output trimmed)"
    total = sum(len(m.get("content") or "") for m in messages)
    while total > num_ctx * 3.4 and len(messages) > 12:
        total -= len(messages[1].get("content") or "")
        del messages[1]


def llm_opts(cfg, temperature=None):
    return {"num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"] if temperature is None else temperature}


def run_chat(cfg, messages, emit, cancel):
    content, _ = providers.chat_stream(cfg["settings"], cfg["model"], messages, None, llm_opts(cfg),
                                       lambda k, t: emit({"type": k, "text": t}), cancel)
    messages.append({"role": "assistant", "content": content})


def run_code(cfg, messages, root, emit, cancel, approve, extra=None):
    tools = Tools(root, approve, emit, cancel, extra, cfg.get("extra_dirs"))
    schemas = tool_schemas() + (extra["schemas"] if extra else [])
    last_calls, repeats, nags, review_rounds = [], 0, 0, 0
    test_cmd = detect_test_command(root)
    for step in range(cfg["max_steps"]):
        if cancel.is_set():
            raise Cancelled()
        trim(messages, cfg["num_ctx"])
        emit({"type": "turn"})
        content, calls = providers.chat_stream(cfg["settings"], cfg["model"], messages, schemas, llm_opts(cfg),
                                               lambda k, t: emit({"type": k, "text": t}), cancel)
        if cancel.is_set():
            raise Cancelled()
        if not calls:
            calls = calls_from_text(content)
        msg = {"role": "assistant", "content": content}
        if calls:
            msg["tool_calls"] = calls
        messages.append(msg)
        if not calls:
            if tools.dirty and not tools.verified and nags < 2 and test_cmd:
                nags += 1
                messages.append({"role": "user", "content": "You changed files but have not verified them. Run `%s` (or a narrower check) now, then finish." % test_cmd})
                continue
            return
        for c in calls:
            if cancel.is_set():
                raise Cancelled()
            fn = c.get("function", {})
            name, args = fn.get("name", ""), fn.get("arguments", {})
            sig = (name, json.dumps(args, sort_keys=True) if not isinstance(args, str) else args)
            repeats = repeats + 1 if sig == last_calls else 0
            last_calls = sig
            emit({"type": "tool", "name": name, "args": args})
            if name != "finish" and repeats >= 2:
                result = "error: you repeated the same call 3 times with no progress. Re-read the relevant code and try a different approach, or ask_user."
            elif name == "finish":
                result = None
                if tools.dirty and not tools.verified and nags < 2 and test_cmd:
                    nags += 1
                    result = "Not finished: you changed files but did not run a passing check since. Run `%s` (or a narrower check), fix failures, then call finish again." % test_cmd
                elif tools.dirty and cfg.get("critic") and review_rounds < 2:
                    review_rounds += 1
                    diffs = "\n\n".join(diff_text(tools.orig[p], (tools.root / p).read_text(errors="replace"), p) for p in tools.orig)
                    emit({"type": "status", "text": "Reviewing the changes..."})
                    verdict = providers.chat_once(cfg["settings"], cfg.get("critic_model") or cfg["model"], [
                        {"role": "system", "content": "You are a strict code reviewer. Read the user's request and the diff. Reply exactly `LGTM` if the change is correct, complete and matches the request. Otherwise list the concrete problems (bugs, missing requirements, missing edge cases, style mismatches) as short bullets. No praise."},
                        {"role": "user", "content": "Request:\n%s\n\nDiff:\n%s" % (cfg.get("task", ""), diffs[:12000])}], llm_opts(cfg, 0.1))
                    if not verdict.strip().upper().startswith("LGTM"):
                        emit({"type": "review", "text": verdict.strip()})
                        result = "Reviewer found problems. Fix them, verify again, then finish:\n" + verdict.strip()
                if result is None:
                    result = tools.call(name, args)
                    messages.append({"role": "tool", "tool_name": name, "content": result})
                    emit({"type": "tool_result", "name": name, "text": result})
                    return
            else:
                result = tools.call(name, args)
            messages.append({"role": "tool", "tool_name": name, "content": result})
            emit({"type": "tool_result", "name": name, "text": result})
            if tools.ask:
                emit({"type": "question", "text": tools.ask})
                return
    emit({"type": "status", "text": "Stopped after %d steps. Say 'continue' to go on." % cfg["max_steps"]})
