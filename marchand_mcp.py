#!/usr/bin/env python3
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine

HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not HOST.startswith("http"):
    HOST = "http://" + HOST

TOOLS = [
    {"name": "list_local_models", "description": "List the models installed in the local Ollama.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ask_local_model", "description": "Ask a local Ollama model a question and return its answer. Use for cheap drafts, summaries, second opinions or private data that must not leave this computer.",
     "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}, "system": {"type": "string"}},
                     "required": ["prompt"]}},
    {"name": "run_local_coding_agent", "description": "Delegate a coding task to the local Marchand agent (reads, edits, tests files in a project folder using a local model). Returns a summary and the diffs.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}, "project": {"type": "string", "description": "absolute path of the project folder"},
                                                    "model": {"type": "string"}, "max_steps": {"type": "integer"}},
                     "required": ["task", "project"]}},
]


def default_model():
    with urllib.request.urlopen(HOST + "/api/tags", timeout=10) as r:
        models = json.loads(r.read()).get("models", [])
    if not models:
        raise RuntimeError("no models installed in Ollama")
    return models[0]["name"]


def call(name, a):
    if name == "list_local_models":
        with urllib.request.urlopen(HOST + "/api/tags", timeout=10) as r:
            return "\n".join("%s (%.1f GB)" % (m["name"], m["size"] / 1e9) for m in json.loads(r.read()).get("models", [])) or "no models"
    model = a.get("model") or default_model()
    if name == "ask_local_model":
        msgs = ([{"role": "system", "content": a["system"]}] if a.get("system") else []) + [{"role": "user", "content": a["prompt"]}]
        return engine.ollama_once(HOST, {"model": model, "messages": msgs, "options": {"num_ctx": 16384}})
    if name == "run_local_coding_agent":
        root = a["project"]
        if not Path(root).is_dir():
            return "error: project folder not found: " + root
        cfg = {"settings": {"host": HOST, "providers": {}}, "host": HOST, "model": model, "num_ctx": 16384, "temperature": 0.2, "max_steps": int(a.get("max_steps") or 30),
               "critic": True, "task": a["task"]}
        diffs, finish = [], []

        def emit(ev):
            if ev["type"] == "diff":
                diffs.append(ev["diff"])
            elif ev["type"] == "tool_result" and ev["name"] == "finish":
                finish.append(ev["text"])
        system = engine.build_system(root, "code", cfg["num_ctx"], "")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": a["task"]}]
        engine.run_code(cfg, messages, root, emit, threading.Event(), lambda *x: True)
        return "%s\n\nDiffs:\n%s" % (finish[-1] if finish else "(agent stopped without finishing)", "\n\n".join(diffs)[:12000] or "(no file changes)")
    raise ValueError("unknown tool " + name)


def reply(i, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": i}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        i, method = m.get("id"), m.get("method")
        if i is None:
            continue
        if method == "initialize":
            reply(i, {"protocolVersion": m.get("params", {}).get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "marchand", "version": "1.0"}})
        elif method == "tools/list":
            reply(i, {"tools": TOOLS})
        elif method == "tools/call":
            p = m.get("params", {})
            try:
                reply(i, {"content": [{"type": "text", "text": call(p.get("name"), p.get("arguments") or {})}]})
            except Exception as ex:
                reply(i, {"content": [{"type": "text", "text": "error: %s" % ex}], "isError": True})
        elif method == "ping":
            reply(i, {})
        else:
            reply(i, error={"code": -32601, "message": "method not found"})


if __name__ == "__main__":
    main()
