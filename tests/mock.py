import json, http.server
AGENT = [
    {"tool_calls": [{"function": {"name": "plan", "arguments": {"items": [{"text": "Reproduce the failure", "done": False}, {"text": "Fix add()", "done": False}, {"text": "Re-run tests", "done": False}]}}}]},
    {"content": "Let me run the test first.", "tool_calls": [{"function": {"name": "run_command", "arguments": {"command": "python3 test_calc.py"}}}]},
    {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "calc.py"}}}]},
    {"tool_calls": [{"function": {"name": "edit_file", "arguments": {"path": "calc.py", "old": "a - b", "new": "a + b"}}}]},
    {"tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "premature"}}}]},
    {"tool_calls": [{"function": {"name": "run_command", "arguments": {"command": "python3 test_calc.py"}}}]},
    {"tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "Fixed add(): it subtracted instead of adding. test_calc.py now passes."}}}]},
]
st = {"i": 0}
CREATED = []
PULLED = []
BLOBS = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def j(self, o):
        d = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def do_GET(self):
        if self.path == "/created": return self.j({"created": CREATED, "blobs": BLOBS})
        if self.path == "/api/tags":
            made = sorted(set(PULLED) | {c.get("model") or c.get("name") for c in CREATED if c.get("model") or c.get("name")})
            self.j({"models": [{"name": "qwen2.5-coder:14b", "size": 9000000000}, {"name": "llama3.1:8b", "size": 4900000000}] + [{"name": n, "size": 9000000000} for n in made]})
        else: self.j({"version": "0.9.9"})
    def do_DELETE(self):
        self.rfile.read(int(self.headers["Content-Length"])); self.j({})
    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path.startswith("/api/blobs/"):
            BLOBS.append((self.path, len(raw))); return self.j({})
        b = json.loads(raw)
        if self.path == "/api/create": CREATED.append(b)
        if self.path == "/api/pull": PULLED.append(b["model"])
        if self.path in ("/api/create", "/api/pull"):
            self.send_response(200); self.end_headers()
            self.wfile.write((json.dumps({"status": "working", "total": 10, "completed": 5}) + "\n" + json.dumps({"status": "success"}) + "\n").encode()); return
        if self.path == "/api/show": return self.j({"details": {"family": "qwen2", "parameter_size": "14B", "quantization_level": "Q4_K_M"}, "capabilities": ["completion", "vision"] if "vision" in b.get("model", "") else ["completion", "tools"], "parameters": "num_ctx 4096", "template": "tmpl"})
        if self.path.startswith("/api/blobs/"): return self.j({})
        if not b.get("stream", True):
            return self.j({"message": {"content": "LGTM"}})
        if b.get("tools"):
            step = AGENT[min(st["i"], len(AGENT) - 1)]; st["i"] += 1
            msg = {"role": "assistant", "content": step.get("content", ""), "tool_calls": step.get("tool_calls", [])}
        else:
            msg = {"role": "assistant", "content": "A **closure** is a function that remembers its scope.\n\n```js\nconst a = () => 1\n```"}
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson"); self.end_headers()
        self.wfile.write((json.dumps({"message": msg, "done": False}) + "\n").encode())
        self.wfile.write((json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}) + "\n").encode())
http.server.ThreadingHTTPServer(("127.0.0.1", 11555), H).serve_forever()
