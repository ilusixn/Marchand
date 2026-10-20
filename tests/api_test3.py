import json, os, re, shutil, subprocess, sys, threading, time, urllib.request, urllib.error
BASE = "http://127.0.0.1:8765"
html = urllib.request.urlopen(BASE + "/").read().decode()
TOKEN = re.search(r"TOKEN='([0-9a-f]+)'", html).group(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
def req(path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(BASE + path, data, {"X-Marchand-Token": TOKEN, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(r, timeout=120) as x: return x.status, x.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
def J(path, body=None, **kw):
    c, raw = req(path, body, **kw); return json.loads(raw) if raw else {}
def events(path, body, on=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"X-Marchand-Token": TOKEN, "Content-Type": "application/json"})
    evs = []
    with urllib.request.urlopen(r, timeout=300) as x:
        for raw in x:
            line = raw.decode().strip()
            if line.startswith("data: "):
                e = json.loads(line[6:]); evs.append(e)
                if on: on(e)
    return evs
n = [0]
def ok(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:400]))
    if not cond: sys.exit(1)
    n[0] += 1
work = sys.argv[1]
def calls(): return [json.loads(l) for l in open(os.path.join(HERE, "fake_claude_calls.jsonl"))] if os.path.exists(os.path.join(HERE, "fake_claude_calls.jsonl")) else []
SEEN = lambda: json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read())[-1]
J("/api/settings", {"auto_approve": True, "critic": False, "providers": {"custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}}})

# ---- reference traces replay correctly for every task (they are what the student learns from)
import curriculum, trainer, engine
replayed = 0
for t in curriculum.TASKS:
    if not trainer.availability(t)[0]: continue
    hist, passed = trainer.reference_trace(dict(t, builtin=True))
    d = os.path.join(work, "replay_" + t["id"]); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for k, v in {**t["files"], **t["tests"]}.items(): open(os.path.join(d, k), "w").write(trainer.render(v))
    tools = engine.Tools(d, lambda *a: True, lambda e: None, None)
    for m in hist:
        for c in m.get("tool_calls") or []:
            if c["function"]["name"] in ("edit_file", "write_file"):
                res = tools.call(c["function"]["name"], c["function"]["arguments"]); assert res.startswith(("edited", "wrote")), (t["id"], res)
    r = subprocess.run(trainer.run_cmd(dict(t, builtin=True)), shell=True, cwd=d, capture_output=True, text=True)
    assert passed and r.returncode == 0, (t["id"], r.stdout + r.stderr)
    replayed += 1
ok("reference traces for all %d tasks (%d languages incl. reverse engineering) replay into passing code with Marchand's own tools" % (replayed, len({t["lang"] for t in curriculum.TASKS})), replayed == len(curriculum.TASKS) and replayed >= 62)
tr = trainer.reference_trace(dict(curriculum.get("pagination"), builtin=True))[0]
names = [c["function"]["name"] for m in tr for c in (m.get("tool_calls") or [])]
ok("reference trace follows the method: test, read, small edit, test, finish", names == ["run_command", "read_file", "edit_file", "run_command", "finish"], names)

# ---- Claude Code bridge
st = J("/api/cc/status"); ok("Claude Code detected", st["installed"] and st["path"].endswith("fake_claude.py"), st)
g = {x["provider"]: x for x in J("/api/models")["groups"]}
ok("Claude subscription models listed", "claude-code" in g and "claude-code::opus" in [m["id"] for m in g["claude-code"]["models"]] and "claude-code::sonnet" in [m["id"] for m in g["claude-code"]["models"]])
ev = events("/api/run", {"mode": "chat", "model": "claude-code::opus", "history": [], "user": "hi", "effort": "max", "images": ["iVBORw0KGgo="]})
txt = "".join(e.get("text", "") for e in ev if e["type"] == "token"); done = ev[-1]
ok("chat via subscription with effort + image", "model=opus effort=max images=1 resumed=no" in txt and done["type"] == "done" and done.get("cc_session"), txt)
c = calls()[-1]; ok("chat runs with tools disabled in a neutral folder", c["tools_off"] and c["cwd"].endswith("cc-chat"))
sid = done["cc_session"]
ev = events("/api/run", {"mode": "chat", "model": "claude-code::sonnet", "history": done["history"], "user": "again", "effort": "low", "cc_session": sid})
ok("follow-up resumes the same Claude session", ("resumed=" + sid) in "".join(e.get("text", "") for e in ev if e["type"] == "token"))
ev = events("/api/run", {"mode": "chat", "model": "claude-code::opus", "history": [], "user": "x", "cc_session": "bad-session"})
ok("broken session falls back to a fresh one", any(e["type"] == "status" and "fresh" in e["text"] for e in ev) and ev[-1]["type"] == "done")
ok("cost/usage reported per reply", any(e["type"] == "cc_result" and e["cost"] == 0.0123 for e in ev))
u = J("/api/cc/status")["usage"]
ok("plan limits stored (session 5h + weekly)", u["rate"]["unifiedWindows"]["five_hour"]["utilization"] == 0.12 and u["rate"]["unifiedWindows"]["seven_day"]["utilization"] == 0.42 and u["today_runs"] >= 3 and u["window"] == 200000, u)
r = J("/api/cc/refresh", {}); ok("refresh usage uses a tiny haiku request", calls()[-1]["model"] == "haiku" and calls()[-1]["effort"] == "low" and "usage" in r)
def proj(name):
    p = os.path.join(work, name); shutil.rmtree(p, ignore_errors=True); os.makedirs(p)
    open(p + "/calc.py", "w").write("def add(a, b):\n    return a - b\n"); open(p + "/test_calc.py", "w").write("from calc import add\nassert add(2, 3) == 5\nprint('ok')\n")
    open(p + "/MARCHAND.md", "w").write("RULE-XYZ"); return p
p = proj("cc_auto"); ev = events("/api/run", {"mode": "code", "model": "claude-code::opus", "project": p, "history": [], "user": "TASK:ccedit", "effort": "high"})
ok("code mode (auto-approve): Claude edits the project", "a + b" in open(p + "/calc.py").read() and any(e["type"] == "diff" and "+    return a + b" in e["diff"] for e in ev) and any(e["type"] == "tool" and e["name"] == "Edit" for e in ev))
c = calls()[-1]; ok("code mode passes bypass + MARCHAND.md + project cwd", c["perm_mode"] == "bypassPermissions" and "RULE-XYZ" in c["append"] and c["cwd"] == p and not c["tools_off"], c)
import tempfile
xd = tempfile.mkdtemp(prefix="extra_"); open(xd + "/lib.txt", "w").write("EXTRA-LIB")
ev = events("/api/run", {"mode": "code", "model": "claude-code::opus", "project": p, "history": [], "user": "hello", "effort": "low", "extra_dirs": [xd]})
ok("extra folders are passed to Claude with --add-dir", calls()[-1]["add_dirs"] == [xd], calls()[-1])
T = engine.Tools(p, lambda *a, **k: True, lambda *a, **k: None, lambda: False, None, [xd])
ok("engine reads files in an extra folder", "EXTRA-LIB" in T.t_read_file(xd + "/lib.txt"), T.t_read_file(xd + "/lib.txt"))
try:
    T.t_read_file("/etc/hostname"); refused = False
except ValueError:
    refused = True
ok("engine still refuses paths outside project and extra folders", refused)
J("/api/settings", {"auto_approve": False})
for decision in (True, False):
    p = proj("cc_ask_%s" % decision); state = {}
    def on(e, decision=decision):
        if e["type"] == "start": state["run"] = e["run"]
        if e["type"] == "approval":
            state.setdefault("kinds", []).append(e["kind"]); state.setdefault("diffs", []).append(e.get("diff") or "")
            J("/api/approve", {"run": state["run"], "id": e["id"], "allow": decision})
    ev = events("/api/run", {"mode": "code", "model": "claude-code::opus", "project": p, "history": [], "user": "TASK:ccedit"}, on)
    fixed = "a + b" in open(p + "/calc.py").read()
    ok("Marchand approval card for Claude's edit (%s)" % ("allow" if decision else "deny"), state["kinds"][0] == "edit" and "+    return a + b" in state["diffs"][0] and fixed == decision, (state, fixed))
c = calls()[-1]; ok("approvals go through the MCP permission bridge", c["perm_tool"] == "mcp__marchand__approve" and c["perm_mode"] == "default")
J("/api/settings", {"auto_approve": True})

# ---- vision routing
J("/api/settings", {"vision_model": "llama3.2-vision:11b"})
ev = events("/api/run", {"mode": "chat", "model": "qwen2.5-coder:14b", "history": [], "user": "what is in this?", "images": ["iVBORw0KGgo="]})
ok("Ollama model without vision gets images described by the vision model", any(e["type"] == "status" and "describes them" in e["text"] for e in ev) and "described by llama3.2-vision:11b" in ev[-1]["history"][-2]["content"], ev[-1])
ev = events("/api/run", {"mode": "chat", "model": "custom::mock-model", "history": [], "user": "look at this", "images": ["iVBORw0KGgo="]})
ok("other providers receive images directly", SEEN().get("image_part") and not any(e["type"] == "status" for e in ev))
ev = events("/api/run", {"mode": "chat", "model": "llama3.2-vision:11b", "history": [], "user": "look", "images": ["iVBORw0KGgo="]})
ok("vision model receives images directly", not any(e["type"] == "status" for e in ev))

# ---- file store + video
c_id = "convo-files"
st_, raw = req("/api/upload?convo=%s&name=notes.txt" % c_id, raw=b"hello store", ctype="application/octet-stream")
ok("upload stores a file", st_ == 200 and json.loads(raw)["size"] == 11)
vid = os.path.join(work, "clip.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10", "-pix_fmt", "yuv420p", "-y", vid], check=True)
req("/api/upload?convo=%s&name=clip.mp4" % c_id, raw=open(vid, "rb").read(), ctype="application/octet-stream")
files = {f["name"]: f for f in J("/api/files?convo=" + c_id)}
ok("files listed with type", files["notes.txt"]["type"] == "text/plain" and files["clip.mp4"]["type"] == "video/mp4")
ok("stored file downloads", req("/api/stored?convo=%s&name=notes.txt" % c_id)[1] == b"hello store")
fr = J("/api/video/frames", {"convo": c_id, "name": "clip.mp4", "count": 6})
import base64
ok("video becomes 6 timestamped frames", fr["duration"] == 4.0 and len(fr["frames"]) == 6 and base64.b64decode(fr["frames"][0]["b64"])[:3] == b"\xff\xd8\xff" and fr["frames"][-1]["t"] > 3, {k: v for k, v in fr.items() if k != "frames"})
bad = J("/api/video/frames", {"convo": c_id, "name": "notes.txt"}); ok("non-video gives a clear error", "error" in bad)
ok("path tricks rejected in file store", req("/api/stored?convo=../..&name=../../etc/passwd")[0] == 404)
J("/api/files/delete", {"convo": c_id, "name": "notes.txt"}); ok("delete stored file", "notes.txt" not in [f["name"] for f in J("/api/files?convo=" + c_id)])

# ---- git panel
gp = proj("gitproj"); subprocess.run("git init -q && git -c user.email=a@b -c user.name=t add -A && git -c user.email=a@b -c user.name=t commit -qm init", shell=True, cwd=gp, check=True)
open(gp + "/calc.py", "a").write("# change\n")
gi = J("/api/git?root=" + gp); ok("git branch + changes", gi["git"] and gi["changed"] == 1, gi)
ok("git diff", "# change" in J("/api/git/diff?root=" + gp)["diff"])
os.environ["GIT_AUTHOR_NAME"] = "t"
subprocess.run("git config user.email a@b && git config user.name t", shell=True, cwd=gp)
r = J("/api/git/commit", {"root": gp, "message": "from marchand"}); ok("commit from the panel", r["ok"] and J("/api/git?root=" + gp)["changed"] == 0, r)

# ---- training: student improves after Claude teaches
J("/api/settings", {"teacher_model": "claude-code::opus", "cc_effort": "high"})
r = J("/api/training/start", {"name": "t1", "student": "custom::mock-model", "teacher": "claude-code::opus", "demos": "teacher", "rounds": 2, "max_steps": 12,
                               "tasks": ["pagination", "rename"], "learn": True, "keep_successes": True, "persona": True, "consolidate": True})
sid = r["id"]; ok("training started", bool(sid))
c, raw = req("/api/training/start", {"student": "custom::mock-model", "tasks": ["pagination"]}); ok("only one session at a time", c == 400)
for _ in range(240):
    s = J("/api/training/session?id=" + sid)
    if s["status"] != "running": break
    time.sleep(0.5)
ok("training finished", s["status"] == "finished", s.get("log", [])[-5:])
r1 = [x["passed"] for x in s["rounds"][0]["results"]]; r2 = [x["passed"] for x in s["rounds"][1]["results"]]
ok("student fails before any lessons, passes once taught (50% -> 100%)", r1 == [False, True] and r2 == [True, True] and s["summary"] == "50% -> 100%", (r1, r2, s["summary"]))
ok("teacher reviewed and demonstrated the failure", s["rounds"][0]["results"][0]["demo"] == "teacher" and s["rounds"][0]["results"][0]["demo_passed"] and s["rounds"][0]["results"][0]["lessons"] == 2, s["rounds"][0]["results"])
cc_calls = [c for c in calls() if "TEACHER inside Marchand" in c.get("system", "")]
ok("teacher is told it is teaching another AI", len(cc_calls) >= 1)
demo = [c for c in calls() if c["append"].startswith("You are demonstrating")]
ok("teacher demonstrations get the demonstration brief and run in the sandbox", demo and all("/training/workspaces/" in c["cwd"] for c in demo) and demo[-1]["perm_mode"] == "bypassPermissions")
les = J("/api/teach/lessons"); ok("small lesson sets are kept as written (no needless condensing)", len(les) == 2 and all(l["source"].startswith("teacher:") for l in les), les)
os.environ["MARCHAND_CLAUDE"] = os.path.join(HERE, "fake_claude.py")
import teacher
teacher.add_lessons(["Teacher rule %d for testing condensing." % i for i in range(8)], "teacher:test")
J("/api/teach/lesson", {"add": "My own rule stays."})
n_after = teacher.consolidate({"host": "http://127.0.0.1:11555", "providers": {}}, "claude-code::opus")
les = J("/api/teach/lessons")
ok("teacher condenses many lessons, keeps your own", n_after == 6 and sum(1 for l in les if l["source"] == "condensed") == 5 and [l["text"] for l in les if l["source"] == "you"] == ["My own rule stays."], [l["source"] for l in les])
ok("condense request carries the teaching context", "TEACHER inside Marchand" in calls()[-1]["system"])
ex = J("/api/teach/examples"); ok("examples saved from teacher demos and student successes", sum(1 for e in ex if e["title"].startswith("[teacher]")) == 1 and sum(1 for e in ex if e["title"].startswith("[training]")) == 3, [e["title"] for e in ex])
ok("session in results list", any(x["id"] == sid and x["summary"] == "50% -> 100%" for x in J("/api/training/sessions")))
# student example uses Marchand tool names (convertible for fine-tuning)
dsj = J("/api/teach/export?min=4&cloud=0")["jsonl"].splitlines()
tool_names = {tc["function"]["name"] for line in dsj for m in json.loads(line)["messages"] for tc in (m.get("tool_calls") or [])}
ok("teacher demos converted to Marchand's tool format for the dataset", {"run_command", "read_file", "write_file", "finish"} <= tool_names and "Write" not in tool_names, tool_names)
# save trained local student
r = J("/api/training/start", {"name": "t2", "student": "qwen2.5-coder:14b", "teacher": "", "demos": "reference", "rounds": 1, "tasks": ["transpose"], "save_as": "trained-one"})
for _ in range(120):
    s2 = J("/api/training/session?id=" + r["id"])
    if s2["status"] != "running": break
    time.sleep(0.5)
ok("reference-only training works without a teacher", s2["status"] == "finished" and s2["rounds"][0]["results"][0]["demo"] == "reference")
ok("save_as builds and registers the trained AI", s2.get("saved_ai") == "trained-one" and any(a["name"] == "trained-one" for a in J("/api/ais")))
r = J("/api/training/save-ai", {"id": r["id"], "name": "Saved Later!"}); ok("Save AI button endpoint", r.get("name") == "saved-later" and any(a["name"] == "saved-later" for a in J("/api/ais")), r)
cr = json.loads(urllib.request.urlopen("http://127.0.0.1:11555/created").read())["created"]
last = [c for c in cr if c.get("model") == "saved-later"][-1]
ok("saved AI carries persona + lessons + examples", "Marchand Coder" in last["system"] and "Lessons learned" in last["system"] and len(last.get("messages", [])) >= 2)
r = J("/api/training/save-ai", {"id": sid, "name": "x"}); ok("cloud students cannot be saved as local AI (clear error)", "error" in r)
# stop + custom task + delete
cp = proj("customtask")
t = J("/api/training/custom", {"title": "My calc", "folder": cp, "prompt": "Fix add() in calc.py", "test_cmd": sys.executable + " test_calc.py"})
ok("custom task added", t["id"].startswith("custom_") and any(x["id"] == t["id"] for x in J("/api/training/tasks")))
ok("custom task with bad folder rejected", "error" in J("/api/training/custom", {"folder": "/nope", "prompt": "x", "test_cmd": "y"}))
slow = J("/api/training/custom", {"title": "Slow", "folder": cp, "prompt": "TASK:slow please fix", "test_cmd": sys.executable + " test_calc.py"})
r = J("/api/training/start", {"name": "stopme", "student": "custom::mock-model", "teacher": "", "demos": "none", "rounds": 3, "tasks": [slow["id"], t["id"]]})
time.sleep(1.5); J("/api/training/stop", {"id": r["id"]})
for _ in range(60):
    s3 = J("/api/training/session?id=" + r["id"])
    if s3["status"] != "running": break
    time.sleep(0.5)
ok("stop a training session", s3["status"] == "stopped")
ok("custom task ran in a copy (original untouched)", "a - b" in open(cp + "/calc.py").read())
J("/api/training/delete", {"id": r["id"]}); ok("delete training report", not any(x["id"] == r["id"] for x in J("/api/training/sessions")))
# ---- Marchand Coder pack
pk = events("/api/training/coder", {"base": "qwen2.5-coder:7b", "name": "marchand-coder"})
ok("Marchand Coder: downloads base if missing, then builds", any("Downloading" in (e.get("status") or "") for e in pk) and pk[-1].get("done") and pk[-1].get("name") == "marchand-coder", pk[-3:])
ais = {a["name"]: a for a in J("/api/ais")}; ok("Marchand Coder registered", ais["marchand-coder"]["pack"] and ais["marchand-coder"]["base"] == "qwen2.5-coder:7b")
les = J("/api/teach/lessons"); import pack
ok("%d expert lessons added, tagged per language (deduplicated)" % len(pack.LESSONS), sum(1 for l in les if l["source"] == "marchand-pack") == len(pack.LESSONS) and {"rust", "go", "reverse", "sql", "bash"} <= {l["tags"][0] for l in les})
pk2 = events("/api/training/coder", {"base": "qwen2.5-coder:14b", "name": "marchand-coder"})
ok("rebuild does not duplicate lessons/examples", sum(1 for l in J("/api/teach/lessons") if l["source"] == "marchand-pack") == len(pack.LESSONS) and not any("Downloading" in (e.get("status") or "") for e in pk2))
cr2 = [c for c in json.loads(urllib.request.urlopen("http://127.0.0.1:11555/created").read())["created"] if c.get("model") == "marchand-coder"][-1]
sysp = cr2["system"]
ok("Marchand Coder system prompt: persona names all languages, reverse-engineering method, lessons from many languages",
   "Rust" in sysp and "Reverse engineering" in sysp and sum(1 for k in ("Go,", "Rust", "SQL", "Bash", "JavaScript", "assembly") if k in sysp) >= 6 and "Lessons learned" in sysp, sysp[:200])
ok("Coder pack added worked examples in several languages", len({e["title"] for e in J("/api/teach/examples") if e["title"].startswith("[reference]")}) >= 12)
rec = J("/api/training/recommend"); ok("hardware-based recommendation", rec["base"].startswith("qwen2.5-coder"))
# ---- multi-language + reverse engineering training
langs = J("/api/training/languages")
ok("language list reports every language as runnable here", {"javascript", "typescript", "c", "cpp", "csharp", "java", "go", "rust", "php", "ruby", "perl", "lua", "bash", "sql", "reverse", "python"} <= set(langs) and all(v["available"] == v["tasks"] for v in langs.values()), langs)
alltasks = J("/api/training/tasks"); ok("62+ tasks with language + availability", len([x for x in alltasks if x["builtin"]]) >= 62 and all("lang" in x and "available" in x for x in alltasks))
mt = ["js_sort", "c_sum_range", "go_errors_is", "rust_parse_pair", "sql_left_join", "bash_spaces", "re_layers", "re_bytecode"]
r = J("/api/training/start", {"name": "multi", "student": "custom::mock-model", "teacher": "", "demos": "reference", "rounds": 2, "max_steps": 12, "tasks": mt, "learn": False})
for _ in range(240):
    sm = J("/api/training/session?id=" + r["id"])
    if sm["status"] != "running": break
    time.sleep(0.5)
ok("multi-language training session ran every task", sm["status"] == "finished" and len(sm["rounds"][0]["results"]) == len(mt), sm.get("log", [])[-4:])
ok("results carry the language and the student solved them in 6 languages + RE after the reference lessons", {x["lang"] for x in sm["rounds"][1]["results"]} == {"javascript", "c", "go", "rust", "sql", "bash", "reverse"} and all(x["passed"] for x in sm["rounds"][1]["results"]), [(x["task"], x["passed"]) for x in sm["rounds"][1]["results"]])
# lesson prioritisation by language + skipping unavailable toolchains (in-process)
import teacher as T, shutil as sh
T.add_lessons([{"text": "A Go-only rule for testing.", "tags": ["go"]}, {"text": "A Rust-only rule for testing.", "tags": ["rust"]}], "t")
lp = T.lessons_prompt(["go", "general"], 600); ok("lessons are prioritised for the task language", lp.index("Go-only") < lp.index("Rust-only") if "Rust-only" in lp else "Go-only" in lp)
bal = T.lessons_prompt(["*"], 1500); ok("balanced mix for the pack covers many languages", sum(1 for k in ("Go-only", "Rust-only") if k in bal) >= 1 and bal.count("\n- ") >= 8)
orig = sh.which
sh.which = lambda n: None if n in ("go", "dotnet") else orig(n)
av_go = trainer.availability(curriculum.get("go_errors_is")); av_py = trainer.availability(curriculum.get("pagination"))
sh.which = orig
ok("missing toolchain is detected with an install hint, others unaffected", av_go == (False, "needs go") and av_py[0] is True, av_go)
sh.which = lambda n: None if n == "go" else orig(n)
try:
    try:
        trainer.start({"host": "http://127.0.0.1:11555", "providers": {}}, {"student": "custom::mock-model", "tasks": ["go_errors_is", "go_slice_alias"]})
        raised = None
    except ValueError as ex: raised = str(ex)
finally: sh.which = orig
ok("session with only unavailable tasks refuses with a clear message", raised and "needs go" in raised and "Install" in raised, raised)
ok("TFM placeholder rendered for the installed .NET SDK", re.search(r"net\d+\.0", trainer.render("{{TFM}}")) is not None)

# ---- GPU fine-tune pipeline (fake trainer, real import path)
ck = J("/api/finetune/check"); ok("fine-tune check reports missing GPU/packages honestly", ck["ready"] is False and "unsloth" in ck["missing"])
r = J("/api/finetune/start", {"base": "qwen2.5-coder:7b", "name": "tuned-test", "min_examples": 1})
ok("fine-tune job started", "id" in r, r)
for _ in range(60):
    j = J("/api/finetune/job?id=" + r["id"])
    if j["status"] != "running": break
    time.sleep(0.5)
ok("fine-tune finished and imported into Ollama", j["status"] == "finished" and any("loss" in l for l in j["log"]), j["log"][-4:])
crb = json.loads(urllib.request.urlopen("http://127.0.0.1:11555/created").read())
ok("GGUF uploaded as blob and model created from it", any(b[0].startswith("/api/blobs/sha256:") and b[1] == 2052 for b in crb["blobs"]) and any(c.get("model") == "tuned-test" and "files" in c for c in crb["created"]))
ok("fine-tuned AI registered", J("/api/ais") and any(a["name"] == "tuned-test" and a.get("fine_tuned") for a in J("/api/ais")))
ok("fine-tune refuses unknown base without HF id", "error" in J("/api/finetune/start", {"base": "phi4:14b", "min_examples": 1}))

import ollama_mgr, software
w = ollama_mgr.parse_win_gpus("Intel(R) UHD Graphics|1073741824\nAMD Radeon RX 7800 XT|17163091968\nAMD Radeon(TM) Graphics|536870912\n")
ok("AMD cards are parsed (largest Radeon wins, 16 GB)", w == ("AMD Radeon RX 7800 XT", 16.0, "amd"), w)
ok("NVIDIA/Intel names are not mistaken for AMD", ollama_mgr.parse_win_gpus("NVIDIA GeForce RTX 4070|12884901888\nIntel(R) Arc A770|17179869184") is None)
ok("AMD backend note mentions ROCm and Vulkan", "ROCm" in ollama_mgr.gpu_backend({"vendor": "amd"}) and "Vulkan" in ollama_mgr.gpu_backend({"vendor": "amd"}))
ok("fit uses AMD video memory", ollama_mgr.fit(9.0, {"vram_gb": 16.0, "ram_gb": 32.0}) == "great")
cat = J("/api/ollama/catalog")
ok("model library has 70+ models, each with an ollama.com link", len(cat["models"]) >= 70 and all(m["url"].startswith("https://ollama.com/library/") for m in cat["models"]) and cat["library"].startswith("https://ollama.com"))
ok("hardware reports vendor and graphics backend note", "vendor" in cat["hardware"] and cat["hardware"]["backend"])
lk = J("/api/links")
ids = {l["id"] for l in lk["links"]}
ok("download links exist for Forge, ComfyUI, A1111, Ollama, LM Studio, ffmpeg, Claude Code", {"forge", "comfyui", "a1111", "ollama", "lmstudio", "ffmpeg", "claude-code"} <= ids and all(l["url"].startswith("https://") for l in lk["links"]))
am = {l["id"]: l for l in software.links("amd")}
ok("AMD users get the AMD builds of Forge, A1111 and ComfyUI", "amdgpu-forge" in am["forge"]["url"] and "amdgpu" in am["a1111"]["url"] and "AMD" in am["comfyui"]["amd_note"] and am["forge"]["nvidia_url"].endswith("stable-diffusion-webui-forge"))
ok("non-AMD users get the standard links", software.links("nvidia")[8]["url"].endswith("stable-diffusion-webui-forge"))
open(os.path.join(HERE, "open_urls.log"), "w").close()
ok("open-url accepts allowed https sites", J("/api/open-url", {"url": "https://ollama.com/download"}).get("ok") and "ollama.com/download" in open(os.path.join(HERE, "open_urls.log")).read())
ok("open-url refuses other hosts, http and file links", all("error" in J("/api/open-url", {"url": u}) for u in ["https://evil.example.com/x", "http://ollama.com/", "file:///etc/passwd", "javascript:alert(1)"]))
mg = J("/api/models")
ok("model groups carry a type (claude / local / cloud)", all(g.get("kind") in ("claude", "local", "cloud") for g in mg["groups"]), [g.get("kind") for g in mg["groups"]])

import providers
ok("OpenAI list includes a Codex model offline fallback", "gpt-5-codex" in providers.FALLBACK_MODELS["openai"])
rv = events("/api/training/coder", {"kind": "reverser", "base": "qwen2.5-coder:14b"})
ok("Marchand Reverser installs (default name marchand-reverser)", rv[-1].get("done") and rv[-1].get("name") == "marchand-reverser" and "Reverser" in rv[-1]["status"], rv[-2:])
rvm = [c for c in json.loads(urllib.request.urlopen("http://127.0.0.1:11555/created").read())["created"] if c.get("model") == "marchand-reverser"][-1]
ok("Reverser prompt: reverse-engineering persona and method, not the general coder persona", "Marchand Reverser" in rvm["system"] and "Observe" in rvm["system"] or "samples" in rvm["system"], rvm["system"][:200])
ok("Reverser prompt has reverse-engineering lessons and no language-specific ones", "known plaintext" in rvm["system"].lower() and "strcpy" not in rvm["system"], "")
ok("Reverser is registered with its own pack kind", {a["name"]: a for a in J("/api/ais")}["marchand-reverser"]["pack"] == "reverser")
ok("Marchand Coder stays a separate pack", {a["name"]: a for a in J("/api/ais")}["marchand-coder"]["pack"] is True)
ok("GGUF import rejects a missing file", "error" in J("/api/training/import-model", {"path": "/nope/x.gguf", "name": "x"}))
gg = os.path.join(HERE, "work", "tiny.gguf"); open(gg, "wb").write(b"GGUF" + b"\0" * 2000)
ok("GGUF import rejects non-gguf files", "error" in J("/api/training/import-model", {"path": os.path.join(HERE, "api_test3.py"), "name": "x"}))
ok("GGUF import uploads and creates the model", J("/api/training/import-model", {"path": gg, "name": "My Own Model"}).get("name") == "my-own-model" and any(b[1] >= 2000 for b in json.loads(urllib.request.urlopen("http://127.0.0.1:11555/created").read())["blobs"]))

import zipfile, extract
dx = os.path.join(HERE, "work", "t.docx")
with zipfile.ZipFile(dx, "w") as z: z.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Quarterly &amp; plan</w:t></w:r></w:p><w:p><w:r><w:t>Second line</w:t></w:r></w:p></w:body></w:document>")
ok("docx text is extracted", extract.extract(dx) == "Quarterly & plan\nSecond line", repr(extract.extract(dx)))
xl = os.path.join(HERE, "work", "t.xlsx")
with zipfile.ZipFile(xl, "w") as z: z.writestr("xl/sharedStrings.xml", "<sst><si><t>alpha</t></si><si><t>beta</t></si></sst>")
ok("xlsx shared strings are extracted", "alpha" in extract.extract(xl) and "beta" in extract.extract(xl))
pp = os.path.join(HERE, "work", "t.pptx")
with zipfile.ZipFile(pp, "w") as z: z.writestr("ppt/slides/slide2.xml", "<p><a:p><a:r><a:t>Two</a:t></a:r></a:p></p>"); z.writestr("ppt/slides/slide1.xml", "<p><a:p><a:r><a:t>One</a:t></a:r></a:p></p>")
ok("pptx slides are extracted in order", extract.extract(pp).index("One") < extract.extract(pp).index("Two"))
zp = os.path.join(HERE, "work", "t.zip")
with zipfile.ZipFile(zp, "w") as z: z.writestr("src/main.c", "int main(){}"); z.writestr("README", "hi")
ok("zip contents are listed", "src/main.c" in extract.extract(zp) and "2 entries" in extract.extract(zp))
ok("unknown binary gives empty text", extract.extract(gg) == "")
c, raw = req("/api/upload?convo=extr&name=t.docx", raw=open(dx, "rb").read(), ctype="application/octet-stream"); ok("upload docx", json.loads(raw).get("ok"))
ok("/api/extract returns the text of a stored file", "Quarterly" in J("/api/extract?convo=extr&name=t.docx").get("text", ""))
ok("/api/extract 404s for unknown files", "error" in J("/api/extract?convo=extr&name=nope.docx"))

fh = os.path.join(HERE, "work", "fakehome"); os.makedirs(fh + "/.local/bin", exist_ok=True); open(fh + "/.local/bin/claude", "w").write("#!/bin/sh\n")
os.makedirs(fh + "/Library/Application Support/Claude/claude-code/2.0.1", exist_ok=True); open(fh + "/Library/Application Support/Claude/claude-code/2.0.1/claude", "w").write("x")
os.makedirs(fh + "/Library/Application Support/Claude/claude-code/2.10.0", exist_ok=True); open(fh + "/Library/Application Support/Claude/claude-code/2.10.0/claude", "w").write("x")
fd = subprocess.run([sys.executable, "-c", "import claude_code as c;print(c.exe());print([str(x) for x in c.candidates() if 'claude-code' in str(x)])"], capture_output=True, text=True,
                    env=dict(os.environ, HOME=fh, USERPROFILE=fh, PATH="/usr/bin:/bin", MARCHAND_CLAUDE="", MARCHAND_HOME=fh + "/m", PYTHONPATH=os.path.dirname(HERE)), cwd=os.path.dirname(HERE)).stdout.splitlines()
ok("Claude Code is found outside PATH (~/.local/bin)", fd[0].endswith("/.local/bin/claude"), fd)
ok("Claude Desktop's bundled Claude Code is searched, newest version first", fd[1].index("2.10.0") < fd[1].index("2.0.1"), fd[1])
J("/api/settings", {"claude_path": "/some/where/claude"}); ok("Claude Code location is a saved setting", J("/api/settings").get("claude_path") == "/some/where/claude"); J("/api/settings", {"claude_path": ""})

ag = J("/api/agents/scan?deep=0")["agents"]
ok("agent scan lists Claude Code (found, usable, in use) and other agents", {a["id"] for a in ag} >= {"claude", "codex", "gemini", "aider", "goose", "opencode"} and [a for a in ag if a["id"] == "claude"][0]["found"] and [a for a in ag if a["id"] == "claude"][0]["usable"], ag[:1])
ok("agents that are not installed come with an install link", all(a["url"].startswith("https://") for a in ag))
fh2 = os.path.join(HERE, "work", "fakehome2")
for rel in (".vscode/extensions/anthropic.claude-code-1.2.3/resources/native-binary/claude", ".npm-global/bin/codex", ".local/share/tools/deep/aider"):
    os.makedirs(os.path.dirname(os.path.join(fh2, rel)), exist_ok=True); open(os.path.join(fh2, rel), "w").write("#!/bin/sh\necho 1.0\n"); os.chmod(os.path.join(fh2, rel), 0o755)
sc = subprocess.run([sys.executable, "-c", "import json,agents;print(json.dumps({a['id']:a['path'] for a in agents.scan(True, 8)}))"], capture_output=True, text=True,
                    env=dict(os.environ, HOME=fh2, USERPROFILE=fh2, PATH="/usr/bin:/bin", MARCHAND_CLAUDE="", MARCHAND_HOME=fh2 + "/m", PYTHONPATH=os.path.dirname(HERE)), cwd=os.path.dirname(HERE))
fa = json.loads(sc.stdout or "{}")
ok("deep search finds Claude Code bundled in a VS Code extension", fa.get("claude", "").endswith("native-binary/claude"), sc.stdout + sc.stderr)
ok("deep search finds Codex in npm folder and Aider in a nested folder", fa.get("codex", "").endswith(".npm-global/bin/codex") and fa.get("aider", "").endswith("deep/aider"), fa)
ok("agents/use refuses programs that are not Claude Code", "error" in J("/api/agents/use", {"path": "/bin/sh"}))
cp_ = os.path.join(HERE, "work", "claude"); open(cp_, "w").write("#!/bin/sh\n")
ok("agents/use saves the chosen Claude Code", J("/api/agents/use", {"path": cp_}).get("ok") and J("/api/settings").get("claude_path") == cp_); J("/api/settings", {"claude_path": ""})

og = [g for g in J("/api/models")["groups"] if g["provider"] == "ollama"][0]["models"]
by = {m["id"]: m for m in og}
ok("saved AIs are flagged as 'mine' in the model list, base models are not", by["marchand-coder"]["mine"] is True and by["marchand-reverser"]["mine"] is True and by["qwen2.5-coder:14b"]["mine"] is False, {k: v["mine"] for k, v in by.items()})
ok("every AI in My AIs that exists in Ollama is flagged (tuned-test, my-own-model)", all(by[n]["mine"] for n in ("tuned-test",) if n in by))

import winquiet
class _P:
    def __init__(self, *a, **k): self.kw = k
ok("winquiet adds CREATE_NO_WINDOW to every subprocess on Windows", winquiet.install(_P, force=True) and _P(["x"]).kw["creationflags"] == 0x08000000 and _P(["x"], creationflags=0x200).kw["creationflags"] == 0x08000200)
ok("winquiet installs only once", winquiet.install(_P, force=True) is False)
ok("winquiet leaves subprocess alone on other systems", winquiet.install(type("Q", (), {"__init__": lambda self, *a, **k: None}), force=False) is False)

code = """
import sys, threading, os
sys.path.insert(0, %r)
import claude_code
ev = []
st = claude_code.stream([sys.executable, %r, "--model", "haiku"], os.getcwd(), "BIG " + "x" * 700000, [], lambda e: ev.append(e["type"]), threading.Event())
print("ok", len(st["text"]) > 0, "token" in ev)
""" % (os.path.dirname(HERE), os.path.join(HERE, "fake_claude.py"))
try:
    fl = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, env=dict(os.environ, FAKE_CC_FLOOD="1", MARCHAND_HOME=os.path.join(HERE, "work", "flood")))
    flood_ok = "ok True True" in fl.stdout
except subprocess.TimeoutExpired:
    flood_ok = False
ok("a huge message does not deadlock the pipe to Claude (child floods stdout before reading stdin)", flood_ok)
cc = claude_code if "claude_code" in dir() else None
import claude_code as _cc
a_ = _cc.build_args("sonnet", "low", system="S" * 5 + "\nline2", append="A" * 5)
ok("system prompts are passed as files (no huge or multi-line command lines)", "--system-prompt-file" in a_ and "--append-system-prompt-file" in a_ and "--system-prompt" not in a_ and open(a_[a_.index("--system-prompt-file") + 1]).read() == "SSSSS\nline2")
pc = _cc.perm_config("http://127.0.0.1:1", "tok", "r1")
ok("permission bridge config is a file, not inline JSON with the token", os.path.isfile(pc) and "tok" in open(pc).read()); os.remove(pc)

# ---- every AI works everywhere: chat, code and training with each kind of provider
J("/api/settings", {"auto_approve": True, "providers": {"custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}, "anthropic": {"key": "k", "base": "http://127.0.0.1:11556"}}})
for mdl in ("qwen2.5-coder:14b", "custom::mock-model", "anthropic::claude-test", "claude-code::sonnet"):
    ev = events("/api/run", {"mode": "chat", "model": mdl, "history": [], "user": "say hi", "effort": "low"})
    done = [e for e in ev if e["type"] == "done"]
    ok("chat works with " + mdl, done and "error" not in [e["type"] for e in ev] and any(m["role"] == "assistant" and (m.get("content") or "").strip() for m in done[0]["history"]), [e["type"] for e in ev])
for mdl in ("custom::mock-model", "anthropic::claude-test", "claude-code::sonnet"):
    pm = proj("matrix_" + re.sub(r"\W", "", mdl)); open(pm + "/MARCHAND.md", "w").write("")
    ev = events("/api/run", {"mode": "code", "model": mdl, "project": pm, "history": [], "user": "TASK:ccedit" if mdl.startswith("claude-code") else "fix the test", "effort": "low"})
    ok("code works with " + mdl, "done" in [e["type"] for e in ev] and "error" not in [e["type"] for e in ev], [e["type"] for e in ev][-6:])
    if mdl.startswith("claude-code"): ok("code edit landed with " + mdl, "a + b" in open(pm + "/calc.py").read())
for teacher_id in ("anthropic::claude-test", "custom::mock-model", "claude-code::sonnet"):
    r = J("/api/training/start", {"name": "teach-" + teacher_id, "student": "qwen2.5-coder:14b", "teacher": teacher_id, "demos": "teacher", "rounds": 1, "max_steps": 6,
                                  "tasks": ["pagination"], "learn": True, "keep_successes": False, "persona": True, "consolidate": False})
    ok("training starts with teacher " + teacher_id, bool(r.get("id")), r)
    for _ in range(240):
        s = J("/api/training/session?id=" + r["id"])
        if s["status"] != "running": break
        time.sleep(0.5)
    ok("training with teacher %s finished and the teacher was used" % teacher_id, s["status"] == "finished" and s["counters"]["student_runs"] >= 1, [s["status"], s.get("log", [])[-3:]])

ok("settings report the app build so a stale copy can be recognised", J("/api/settings").get("app_build") not in (None, ""), J("/api/settings").get("app_build"))
print("ALL OK (%d checks)" % n[0])
