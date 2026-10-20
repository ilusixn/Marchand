import json, re, sys, urllib.request, urllib.error, os, shutil
BASE = "http://127.0.0.1:8765"
html = urllib.request.urlopen(BASE + "/").read().decode()
TOKEN = re.search(r"TOKEN='([0-9a-f]+)'", html).group(1)
def call(path, body=None, token=TOKEN, host=None):
    h = {"X-Marchand-Token": token, "Content-Type": "application/json"}
    if host: h["Host"] = host
    req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, h)
    try:
        with urllib.request.urlopen(req) as r: raw = r.read()
        return r.status, raw
    except urllib.error.HTTPError as e: return e.code, e.read()
def J(path, body=None, **kw):
    c, raw = call(path, body, **kw); return json.loads(raw) if raw else {}
def stream(path, body):
    c, raw = call(path, body); evs = []
    for l in raw.decode().split("\n\n"):
        if l.startswith("data: "): evs.append(json.loads(l[6:]))
    return evs
ok = lambda name, cond: print(("PASS " if cond else "FAIL ") + name) or (sys.exit(1) if not cond else None)

ok("no token -> 403", call("/api/settings", token="bad")[0] == 403)
ok("wrong host -> 403", call("/api/settings", host="evil.com")[0] == 403)
ok("index public", urllib.request.urlopen(BASE + "/").status == 200)

J("/api/settings", {"auto_approve": True, "project": sys.argv[1], "providers": {"custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}, "anthropic": {"key": "k", "base": "http://127.0.0.1:11556"}}})
s = J("/api/settings")
ok("key masked", s["providers"]["anthropic"]["key"].startswith("\u2022") and s["providers"]["anthropic"]["key"].endswith("k"))
g = J("/api/models")
labels = [x["label"] for x in g["groups"]]
ok("model groups", {"ollama", "custom", "anthropic"} <= {x["provider"] for x in g["groups"]} and any("Claude" in l for l in labels))
def fresh(p):
    shutil.rmtree(p, ignore_errors=True); os.makedirs(p)
    open(p + "/calc.py", "w").write("def add(a, b):\n    return a - b\n")
    open(p + "/test_calc.py", "w").write("from calc import add\nassert add(2, 3) == 5\nprint('ok')\n")
for model, tag in (("custom::mock-model", "openai-style"), ("anthropic::claude-test", "anthropic")):
    p = sys.argv[1] + "/proj_" + tag.split("-")[0]; fresh(p)
    ev = stream("/api/run", {"mode": "code", "model": model, "project": p, "history": [], "user": "fix the test"})
    types = [e["type"] for e in ev]
    ok(tag + " run finished", "done" in types and "error" not in types and any(e.get("name") == "finish" for e in ev if e["type"] == "tool_result"))
    ok(tag + " bug fixed", "a + b" in open(p + "/calc.py").read())
    last_hist = [e for e in ev if e["type"] == "done"][0]["history"]
v = json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read())
ok("protocol conversion valid " + str(v), v[:-1] == [])
chat = stream("/api/run", {"mode": "chat", "model": "custom::mock-model", "history": [], "user": "hi"})
ok("chat via openai-style", "".join(e.get("text", "") for e in chat if e["type"] == "token") == "hello from oai")

J("/api/settings", {"teacher_model": "anthropic::claude-test"})
r = J("/api/teach/evaluate", {"history": last_hist, "project": sys.argv[1] + "/proj_anthropic"})
ok("teacher evaluate", r.get("score") == 7 and r.get("added") == 2)
ls = J("/api/teach/lessons")
ok("lessons stored", len(ls) == 2)
p = sys.argv[1] + "/proj_x"; fresh(p)
stream("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "fix"})
v = json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read())
ok("lessons injected into prompt", v[-1]["lessons_in_system"])
J("/api/teach/save-example", {"convo": {"title": "t", "model": "anthropic::claude-test", "mode": "code", "history": last_hist}, "rating": 5})
ex = J("/api/teach/examples"); ok("example saved", len(ex) == 1)
exp = J("/api/teach/export?min=4&cloud=1")
ok("dataset export", exp["count"] == 1 and json.loads(exp["jsonl"].splitlines()[0])["messages"][0]["role"] == "system")
bm = stream("/api/teach/build-model", {"base": "qwen2.5-coder:14b", "name": "marchand-coder", "langs": ["python"]})
ok("bake model", any(e.get("status") == "success" for e in bm))
bm2 = stream("/api/teach/build-model", {"base": "qwen2.5-coder:14b", "name": "My Cpp Coder!", "persona": "C++ server helper", "include_lessons": True, "examples": 1, "temperature": 0.3, "num_ctx": 8192})
ok("create AI profile saved", any(e.get("name") == "my-cpp-coder" for e in bm2))
ais = {a["name"]: a for a in J("/api/ais")}; ok("my AIs listed", ais["my-cpp-coder"]["persona"] == "C++ server helper" and ais["my-cpp-coder"]["lessons"] == 2 and "marchand-coder" in ais)
J("/api/ais/delete", {"name": "my-cpp-coder", "remove_model": True}); ok("AI deleted", "my-cpp-coder" not in [a["name"] for a in J("/api/ais")])
ok("show model", J("/api/model/show?name=x")["details"]["family"] == "qwen2")
ok("catalog", len(J("/api/ollama/catalog")["models"]) > 10)
c = J("/api/ollama/check"); ok("ollama check", c["current"] == "0.9.9")
# plugins & MCP & Claude Desktop
ok("bundled listed", len(J("/api/plugins")["available"]) >= 8)
J("/api/plugins/install", {"bundled": "git-helper"}); J("/api/plugins/install", {"bundled": "code-review"})
cmds = J("/api/commands"); ok("commands", any(x["name"] == "review" for x in cmds) and any(x["name"] == "commit-message" for x in cmds))
J("/api/plugins/toggle", {"name": "code-review", "enabled": False}); ok("toggle off", not any(x["name"] == "review" for x in J("/api/commands")))
J("/api/mcp/save", {"servers": [{"name": "fake", "command": sys.executable + " " + os.path.abspath("fake_mcp.py"), "enabled": True}]})
t = J("/api/mcp/test", {"name": "fake"}); ok("mcp test", t["tools"][0]["name"] == "echo")
cfgp = sys.argv[1] + "/claude_desktop_config.json"
json.dump({"mcpServers": {"files": {"command": "npx", "args": ["-y", "srv", "C:\\a b"], "env": {"K": "v"}}}}, open(cfgp, "w"))
st = J("/api/claude-desktop?path=" + cfgp); ok("claude desktop read", st["servers"][0]["name"] == "files")
J("/api/claude-desktop/import", {"path": cfgp}); ok("import", any(x["name"] == "files" for x in J("/api/plugins")["mcp"]))
J("/api/claude-desktop/connect", {"path": cfgp}); cfg = json.load(open(cfgp)); ok("connect writes entry", "marchand" in cfg["mcpServers"] and "files" in cfg["mcpServers"])
ok("backup made", any("marchand-backup" in f for f in os.listdir(sys.argv[1])))
J("/api/claude-desktop/disconnect", {"path": cfgp}); ok("disconnect", "marchand" not in json.load(open(cfgp))["mcpServers"])
# python tool plugin + mcp tool inside agent run is covered by UI test; check marchand_mcp server speaks MCP
sys.path.insert(0, "..")
import plugins
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11555"
c = plugins.McpClient({"command": sys.executable + " " + os.path.abspath("../marchand_mcp.py"), "env": {"OLLAMA_HOST": "http://127.0.0.1:11555"}})
c.start(); ok("marchand mcp tools", [t["name"] for t in c.tools] == ["list_local_models", "ask_local_model", "run_local_coding_agent"])
ok("marchand mcp list models", "qwen2.5-coder:14b" in c.call("list_local_models", {}))
ok("marchand mcp ask", "LGTM" in c.call("ask_local_model", {"prompt": "hi"}))
c.stop()
print("ALL OK")
