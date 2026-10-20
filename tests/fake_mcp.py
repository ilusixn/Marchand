import sys, json
for line in sys.stdin:
    m = json.loads(line); i = m.get("id")
    if i is None: continue
    if m["method"] == "initialize": r = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
    elif m["method"] == "tools/list": r = {"tools": [{"name": "echo", "description": "Echo text", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}]}
    elif m["method"] == "tools/call": r = {"content": [{"type": "text", "text": "echo:" + m["params"]["arguments"].get("text", "")}]}
    else: r = {}
    print(json.dumps({"jsonrpc": "2.0", "id": i, "result": r}), flush=True)
