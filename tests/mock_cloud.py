import json, http.server
V = []
SEEN = {"lessons_in_system": False}
STEPS = {"oai": 0, "ant": 0}
SCRIPTS = {
    "pic": [("generate_image", {"prompt": "a red fox", "path": "art/fox.png"}), ("finish", {"summary": "made a fox"})],
    "teachq": [("ask_teacher", {"question": "how do I fix this?"}), ("finish", {"summary": "asked the teacher"})],
    "mcpuse": [("mcp__fake__echo", {"text": "hi connector"}), ("finish", {"summary": "used connector"})],
    "skilluse": [("use_skill", {"name": "review-checklist"}), ("finish", {"summary": "loaded skill"})],
    "plugtool": [("git_status", {}), ("finish", {"summary": "ran git tool"})],
    "gate": [("edit_file", {"path": "calc.py", "old": "a - b", "new": "a + b"}), ("finish", {"summary": "too early"}), ("run_command", {"command": "python3 test_calc.py"}), ("finish", {"summary": "verified now"})],
    "loop": [("read_file", {"path": "calc.py"})] * 4 + [("finish", {"summary": "gave up looping"})],
    "ask": [("ask_user", {"question": "Which file?"})],
    "plan": [("plan", {"items": [{"text": "one", "done": False}, {"text": "two", "done": False}]}), ("plan", {"items": [{"text": "one", "done": True}, {"text": "two", "done": False}]}), ("finish", {"summary": "planned"})],
    "write": [("write_file", {"path": "sub/new.txt", "content": "hello\nworld\n"}), ("read_file", {"path": "sub/new.txt"}), ("search", {"pattern": "world"}), ("list_files", {}), ("finish", {"summary": "wrote"})],
    "badedit": [("edit_file", {"path": "calc.py", "old": "NOT THERE", "new": "x"}), ("edit_file", {"path": "calc.py", "old": "a - b", "new": "a + b"}), ("run_command", {"command": "python3 test_calc.py"}), ("finish", {"summary": "recovered"})],
    "denyme": [("edit_file", {"path": "calc.py", "old": "a - b", "new": "a + b"}), ("finish", {"summary": "after deny"})],
    "slow": [("read_file", {"path": "calc.py"}), ("read_file", {"path": "test_calc.py"}), ("finish", {"summary": "slow done"})],
    "blocked": [("run_command", {"command": "rm -rf /"}), ("finish", {"summary": "tried"})],
}
RUNSTATE = {}
def script_for(msgs):
    first = next((m["content"] for m in msgs if m["role"] == "user"), "") if isinstance(msgs[-1].get("content"), (str, type(None))) else ""
    users = [m for m in msgs if m["role"] == "user"]
    task = users[0]["content"] if users and isinstance(users[0]["content"], str) else ""
    key = next((k for k in SCRIPTS if ("TASK:" + k) in task), None)
    return key
FIX = [
    ("run_command", {"command": "python3 test_calc.py"}),
    ("edit_file", {"path": "calc.py", "old": "a - b", "new": "a + b"}),
    ("run_command", {"command": "python3 test_calc.py"}),
    ("finish", {"summary": "fixed via cloud"}),
]
EVAL = json.dumps({"score": 7, "verdict": "Fixed it but skipped reading first.", "mistakes": ["Edited before reading the file"],
                   "lessons": [{"text": "Always read the file before editing it.", "tags": ["general"]}, {"text": "Run tests after each edit.", "tags": ["python"]}],
                   "better_approach": "Read, then edit."})

def sse(w, obj): w.write(("data: " + json.dumps(obj) + "\n\n").encode()); w.flush()

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def j(self, o):
        d = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def do_GET(self):
        if self.path == "/violations": return self.j(V + [SEEN])
        if self.path.startswith("/v1/models"): return self.j({"data": [{"id": "claude-test"}, {"id": "claude-other"}]})
        if self.path == "/oai/models": return self.j({"data": [{"id": "mock-model"}]})
        self.j({})
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/oai/chat/completions": return self.oai(b)
        if self.path.endswith("/images/generations"):
            import io, base64
            from PIL import Image
            bio = io.BytesIO(); Image.new("RGB", (32, 32), (200, 50, 50)).save(bio, "PNG")
            V.append({"image_request": b})
            return self.j({"data": [{"b64_json": base64.b64encode(bio.getvalue()).decode()} for _ in range(b.get("n", 1))]})
        if self.path == "/v1/messages": return self.ant(b)
        self.j({})
    def start(self):
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
    def oai(self, b):
        msgs = b["messages"]; pend = []
        for m in msgs:
            if m["role"] == "assistant" and m.get("tool_calls"):
                pend = [c["id"] for c in m["tool_calls"]]
                for c in m["tool_calls"]:
                    if not isinstance(c["function"]["arguments"], str): V.append("oai args not string")
            if m["role"] == "tool":
                if not pend or pend.pop(0) != m["tool_call_id"]: V.append("oai tool id mismatch")
        sys_ = msgs[0]["content"] if msgs[0]["role"] == "system" else ""
        if "Lessons learned" in sys_: SEEN["lessons_in_system"] = True
        for k, needle in (("instr", "Project instructions"), ("code_map", "Code map"), ("img_hint", "generate_image")):
            if needle in sys_: SEEN[k] = True
        for mm in msgs:
            if isinstance(mm.get("content"), list) and any(x.get("type") == "image_url" for x in mm["content"]): SEEN["image_part"] = True
            if isinstance(mm.get("content"), str) and mm["role"] == "user" and "described by" in mm["content"]: SEEN["described"] = True
        self.start()
        if "strict code reviewer" in sys_:
            sse(self.wfile, {"choices": [{"delta": {"content": "LGTM"}}]}); self.wfile.write(b"data: [DONE]\n\n"); return
        if not b.get("tools"):
            sse(self.wfile, {"choices": [{"delta": {"content": "hello from oai"}}]}); self.wfile.write(b"data: [DONE]\n\n"); return
        key = script_for(msgs)
        users_ = [x for x in msgs if x["role"] == "user"]
        task_txt = users_[0]["content"] if users_ and isinstance(users_[0]["content"], str) else ""
        if "described by" in task_txt: SEEN["described"] = True
        if "Run the tests with:" in task_txt and not key:
            import sys as _s, os as _o
            _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))))
            import curriculum
            t = next((t for t in curriculum.TASKS if task_txt.startswith(t["prompt"])), None)
            cmd = task_txt.split("Run the tests with: ")[1].strip()
            nmsg = sum(1 for x in msgs if x["role"] != "system")
            st = RUNSTATE.setdefault("train:" + (t["id"] if t else "?"), {"n": 0, "last": 0})
            if nmsg <= st["last"] or nmsg <= 1: st["n"] = 0
            st["last"] = nmsg
            if t and "Lessons learned" in sys_:
                seq = [("write_file", {"path": k, "content": v}) for k, v in t["solution"].items()] + [("run_command", {"command": cmd}), ("finish", {"summary": "fixed and verified"})]
            else:
                seq = [("finish", {"summary": "I think it is done"})]
            name, args = seq[min(st["n"], len(seq) - 1)]; st["n"] += 1
        elif key:
            nmsg = sum(1 for x in msgs if x["role"] != "system")
            st = RUNSTATE.setdefault(key, {"n": 0, "last": 0})
            if nmsg <= st["last"] or nmsg <= 1: st["n"] = 0
            st["last"] = nmsg
            if key == "slow": import time; time.sleep(2.5)
            seq = SCRIPTS[key]; name, args = seq[min(st["n"], len(seq) - 1)]; st["n"] += 1
        else:
            name, args = FIX[min(STEPS["oai"], len(FIX) - 1)]; STEPS["oai"] += 1
        sse(self.wfile, {"choices": [{"delta": {"content": "step. "}}]})
        a = json.dumps(args)
        sse(self.wfile, {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "x", "function": {"name": name, "arguments": a[:6]}}]}}]})
        sse(self.wfile, {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": a[6:]}}]}}]})
        self.wfile.write(b"data: [DONE]\n\n")
    def ant(self, b):
        if self.headers.get("x-api-key") != "k" or self.headers.get("anthropic-version") != "2023-06-01": V.append("anthropic headers")
        prev = None; pend = []
        for m in b["messages"]:
            if prev and m["role"] == prev: V.append("anthropic roles not alternating")
            prev = m["role"]
            if isinstance(m["content"], list):
                for blk in m["content"]:
                    if blk["type"] == "tool_use": pend.append(blk["id"])
                    if blk["type"] == "tool_result":
                        if not pend or pend.pop(0) != blk["tool_use_id"]: V.append("anthropic tool_result id mismatch")
        if b["messages"][0]["role"] != "user": V.append("anthropic first not user")
        sys_ = b.get("system", "")
        if "Lessons learned" in sys_: SEEN["lessons_in_system"] = True
        self.start()
        def blk(text): 
            sse(self.wfile, {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            sse(self.wfile, {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}})
        if "TEACHER inside Marchand" in sys_ and "judge" in sys_: blk(EVAL); return
        if "strict code reviewer" in sys_: blk("LGTM"); return
        if not b.get("tools"): blk("hello from claude"); return
        name, args = FIX[min(STEPS["ant"], len(FIX) - 1)]; STEPS["ant"] += 1
        sse(self.wfile, {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
        sse(self.wfile, {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "step. "}})
        sse(self.wfile, {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "toolu_x", "name": name}})
        a = json.dumps(args)
        sse(self.wfile, {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": a[:5]}})
        sse(self.wfile, {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": a[5:]}})
        sse(self.wfile, {"type": "message_stop"})
http.server.ThreadingHTTPServer(("127.0.0.1", 11556), H).serve_forever()
