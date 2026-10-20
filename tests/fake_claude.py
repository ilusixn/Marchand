#!/usr/bin/env python3
import json, os, subprocess, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import curriculum

args = sys.argv[1:]
def opt(name, default=None):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default
model, effort, resume = opt("--model", "opus"), opt("--effort", ""), opt("--resume")
tools_off = "--tools" in args and opt("--tools") == ""
def text_opt(name):
    path = opt(name + "-file")
    return open(path, encoding="utf-8").read() if path else opt(name, "")
system, append, perm_mode = text_opt("--system-prompt"), text_opt("--append-system-prompt"), opt("--permission-mode", "default")
perm_tool, mcp_cfg = opt("--permission-prompt-tool"), opt("--mcp-config")
if os.environ.get("FAKE_CC_FLOOD"):
    for _ in range(3000):
        sys.stdout.write(json.dumps({"type": "noise", "pad": "x" * 200}) + "\n")
    sys.stdout.flush()
msg = json.loads(sys.stdin.readline())
content = msg["message"]["content"]
text = "".join(c.get("text", "") for c in content if c["type"] == "text")
nimg = sum(1 for c in content if c["type"] == "image")
sid = resume or str(uuid.uuid4())
log = open(os.path.join(HERE, "fake_claude_calls.jsonl"), "a")
log.write(json.dumps({"model": model, "effort": effort, "resume": resume, "tools_off": tools_off, "perm_mode": perm_mode, "perm_tool": perm_tool,
                      "images": nimg, "add_dirs": [args[i+1] for i,a in enumerate(args) if a=="--add-dir"], "cwd": os.getcwd(), "append": append[:200], "system": system[:120]}) + "\n"); log.close()
if resume == "bad-session":
    sys.stderr.write("No conversation found with session ID: bad-session\n"); sys.exit(1)
def out(o): sys.stdout.write(json.dumps(o) + "\n"); sys.stdout.flush()
out({"type": "system", "subtype": "init", "session_id": sid, "model": "claude-" + model, "cwd": os.getcwd()})
out({"type": "autocompact_state", "value": {"effective_window": 200000}})
def say(t):
    out({"type": "stream_event", "event": {"type": "message_start", "message": {}}})
    for i in range(0, len(t), 40):
        out({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t[i:i + 40]}}})
    out({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}})
mcp = None
def ask_perm(tool, inp):
    global mcp
    if perm_mode == "bypassPermissions" or not perm_tool: return True
    if mcp is None:
        cfg = json.loads(open(mcp_cfg, encoding="utf-8").read() if os.path.isfile(mcp_cfg) else mcp_cfg)["mcpServers"]["marchand"]
        mcp = subprocess.Popen([cfg["command"]] + cfg["args"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=dict(os.environ, **cfg["env"]))
        mcp.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"); mcp.stdin.flush(); mcp.stdout.readline()
    mcp.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "approve", "arguments": {"tool_name": tool, "input": inp}}}) + "\n"); mcp.stdin.flush()
    res = json.loads(json.loads(mcp.stdout.readline())["result"]["content"][0]["text"])
    return res["behavior"] == "allow"
n = [0]
def tool(name, inp, run):
    n[0] += 1; tid = "toolu_%d" % n[0]
    out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
    if name in ("Write", "Edit", "Bash") and not ask_perm(name, inp):
        out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": True, "content": "The user denied this action in Marchand."}]}})
        return False
    res = run()
    out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": res}]}})
    return True
def think(t):
    out({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": t}}})
def bash(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return "exit %d\n%s" % (r.returncode, r.stdout + r.stderr)
if tools_off:
    if "TEACHER inside Marchand" in system and "judge" in system:
        say(json.dumps({"score": 3, "verdict": "It finished without changing anything.", "mistakes": ["Claimed success without running the tests"],
                        "lessons": [{"text": "Run the tests before calling finish and read the exit code.", "tags": ["general"]},
                                    {"text": "Read the file you must fix, then edit the exact lines.", "tags": ["general"]}], "better_approach": "Reproduce, read, fix, verify."}))
    elif "TEACHER inside Marchand" in system and "merge" in system:
        say(json.dumps(["Run the tests before finishing.", "Read before editing.", "Make the smallest change.", "Fix the root cause.", "Handle edge cases."]))
    elif "TASK:think" in text:
        think("Let me consider the request. "); think("Plan: answer briefly and carefully.")
        say("answer after thinking")
    elif "TASK:slow" in text:
        import time
        time.sleep(3.5); say("slow reply done")
    elif "TASK:limit" in text:
        out({"type": "result", "subtype": "success", "is_error": True, "result": "You've hit your limit. It resets at 11pm.", "session_id": sid}); sys.exit(1)
    else:
        say("hello from fake claude (model=%s effort=%s images=%d resumed=%s)" % (model, effort, nimg, resume or "no"))
else:
    t = next((t for t in curriculum.TASKS if text.startswith(t["prompt"])), None)
    if t:
        cmd = text.split("Run the tests with: ")[1].strip()
        tool("Bash", {"command": cmd}, lambda: bash(cmd))
        for name, c in t["solution"].items():
            tool("Read", {"file_path": os.path.join(os.getcwd(), name)}, lambda name=name: open(name).read())
            tool("Write", {"file_path": os.path.join(os.getcwd(), name), "content": c}, lambda name=name, c=c: (open(name, "w").write(c), "ok")[1])
        tool("Bash", {"command": cmd}, lambda: bash(cmd))
        say("Fixed it and the tests pass.")
    elif "TASK:ccedit" in text:
        p = os.path.join(os.getcwd(), "calc.py")
        tool("Read", {"file_path": p}, lambda: open(p).read())
        def do_edit():
            src = open(p).read().replace("a - b", "a + b")
            open(p, "w").write(src)
            return "edited"
        ok = tool("Edit", {"file_path": p, "old_string": "a - b", "new_string": "a + b"}, do_edit)
        if ok: tool("Bash", {"command": "python3 test_calc.py"}, lambda: bash("python3 test_calc.py"))
        say("Done: " + ("fixed calc.py" if ok else "you denied the edit, so nothing changed"))
    else:
        say("code mode reply (model=%s effort=%s)" % (model, effort))
out({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning", "rateLimitType": "seven_day", "utilization": 0.42, "overageStatus": "rejected",
     "overageDisabledReason": "org_level_disabled_until", "isUsingOverage": False, "unifiedWindows": {"five_hour": {"utilization": 0.12, "resetsAt": 4102444800}, "seven_day": {"utilization": 0.42, "resetsAt": 4102531200}}}})
out({"type": "result", "subtype": "success", "is_error": False, "session_id": sid, "total_cost_usd": 0.0123, "duration_ms": 900,
     "usage": {"input_tokens": 1200, "cache_read_input_tokens": 3000, "cache_creation_input_tokens": 0, "output_tokens": 300}})
if mcp: mcp.kill()
