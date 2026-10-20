#!/usr/bin/env python3
import json
import os
import sys
import urllib.request

URL = os.environ.get("MARCHAND_URL", "http://127.0.0.1:8765")
TOKEN = os.environ.get("MARCHAND_TOKEN", "")
RUN = os.environ.get("MARCHAND_RUN", "")

TOOL = {"name": "approve", "description": "Asks the Marchand user to allow or deny a tool call.",
        "inputSchema": {"type": "object", "properties": {"tool_name": {"type": "string"}, "input": {"type": "object"}, "tool_use_id": {"type": "string"}},
                        "required": ["tool_name", "input"]}}


def ask(tool_name, tool_input):
    body = json.dumps({"run": RUN, "tool": tool_name, "input": tool_input}).encode()
    req = urllib.request.Request(URL + "/api/cc/permission", body, {"Content-Type": "application/json", "X-Marchand-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=1000) as r:
            allow = json.loads(r.read()).get("allow", False)
    except Exception as ex:
        return {"behavior": "deny", "message": "Marchand could not ask the user: %s" % ex}
    if allow:
        return {"behavior": "allow", "updatedInput": tool_input}
    return {"behavior": "deny", "message": "The user denied this action in Marchand."}


def reply(i, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": i, "result": result}) + "\n")
    sys.stdout.flush()


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
                  "serverInfo": {"name": "marchand-permissions", "version": "1.0"}})
    elif method == "tools/list":
        reply(i, {"tools": [TOOL]})
    elif method == "tools/call":
        a = m.get("params", {}).get("arguments") or {}
        reply(i, {"content": [{"type": "text", "text": json.dumps(ask(a.get("tool_name", ""), a.get("input") or {}))}]})
    else:
        reply(i, {})
