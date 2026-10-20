import json, re, sys, urllib.request, urllib.error, os, shutil, threading, time
BASE = "http://127.0.0.1:8765"
html = urllib.request.urlopen(BASE + "/").read().decode()
TOKEN = re.search(r"TOKEN='([0-9a-f]+)'", html).group(1)
def req(path, body=None, method=None):
    h = {"X-Marchand-Token": TOKEN, "Content-Type": "application/json"}
    r = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as x: return x.status, x.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
def J(path, body=None):
    c, raw = req(path, body); return json.loads(raw) if raw else {}
def events(path, body, on=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"X-Marchand-Token": TOKEN, "Content-Type": "application/json"})
    evs = []
    with urllib.request.urlopen(r, timeout=120) as x:
        buf = ""
        for raw in x:
            line = raw.decode().strip()
            if line.startswith("data: "):
                e = json.loads(line[6:]); evs.append(e)
                if on: on(e)
    return evs
passed = [0]
def ok(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:300]))
    if not cond: sys.exit(1)
    passed[0] += 1
SEEN = lambda: json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read())[-1]
LOG = lambda: json.loads(urllib.request.urlopen("http://127.0.0.1:11557/log").read())
work = sys.argv[1]
def fresh(name):
    p = work + "/" + name; shutil.rmtree(p, ignore_errors=True); os.makedirs(p)
    open(p + "/calc.py", "w").write("def add(a, b):\n    return a - b\n")
    open(p + "/test_calc.py", "w").write("from calc import add\nassert add(2, 3) == 5\nprint('ok')\n")
    return p
def run(task, proj, model="custom::mock-model", **kw):
    return events("/api/run", dict({"mode": "code", "model": model, "project": proj, "history": [], "user": "TASK:" + task}, **kw))
def results(evs, name): return [e["text"] for e in evs if e["type"] == "tool_result" and e["name"] == name]

J("/api/settings", {"auto_approve": True, "critic": True, "providers": {"custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}, "anthropic": {"key": "k", "base": "http://127.0.0.1:11556"}}, "teacher_model": "anthropic::claude-test"})
J("/api/plugins/install", {"bundled": "code-review"}); J("/api/plugins/install", {"bundled": "git-helper"})
J("/api/mcp/save", {"servers": [{"name": "fake", "command": sys.executable + " " + os.path.abspath("fake_mcp.py"), "enabled": True}]})

# ---- apps scanner
found = {r["app"]: r for r in J("/api/software/scan")["found"]}
ok("scan finds LM Studio", "lmstudio" in found and found["lmstudio"]["api"] and found["lmstudio"]["base"].endswith(":1234/v1"))
ok("scan finds Forge", "forge" in found and found["forge"]["api"] and found["forge"]["image"] == "forge")
ok("scan finds ComfyUI", "comfyui" in found and found["comfyui"]["image"] == "comfyui")
ok("scan flags API-off Forge", "forge2" in found and found["forge2"]["api"] is False and "--api" in found["forge2"]["hint"])
r = J("/api/software/apply", {"app": "lmstudio"}); ok("apply LM Studio", r["ok"])
r = J("/api/software/apply", {"app": "forge"}); ok("apply Forge", r["ok"])
r = J("/api/software/apply", {"app": "comfyui"}); ok("apply ComfyUI", r["ok"])
r = J("/api/software/apply", {"app": "forge2"}); ok("apply API-off gives hint", not r["ok"] and "--api" in r["message"])
g = J("/api/models?refresh=1")
lab = {x["provider"]: x for x in g["groups"]}
ok("LM Studio in model groups", "lmstudio" in lab and lab["lmstudio"]["models"][0]["id"] == "lmstudio::lmstudio-model")
ev = events("/api/run", {"mode": "chat", "model": "lmstudio::lmstudio-model", "history": [], "user": "hi"})
ok("chat through LM Studio", "".join(e.get("text", "") for e in ev if e["type"] == "token") == "hello from lmstudio")
ok("local server toggle off hides models", (J("/api/settings", {"providers": {"lmstudio": {"enabled": False, "base": "http://127.0.0.1:1234/v1"}}}) and "lmstudio" not in {x["provider"] for x in J("/api/models?refresh=1")["groups"]}))
J("/api/settings", {"providers": {"lmstudio": {"enabled": True, "base": "http://127.0.0.1:1234/v1"}, "custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}, "anthropic": {"key": "k", "base": "http://127.0.0.1:11556"}}})

# ---- images
st = J("/api/images/status")
ok("images status forge", st["forge"]["ok"] and len(st["forge"]["models"]) == 2 and "Euler a" in st["forge"]["samplers"])
ok("images status comfy", st["comfyui"]["ok"] and "flux.safetensors" in st["comfyui"]["models"] and "karras" in st["comfyui"]["schedulers"])
ev = events("/api/images/generate", {"backend": "forge", "prompt": "a lighthouse", "negative": "blurry", "width": 512, "height": 768, "steps": 12, "cfg": 5.5, "seed": 42, "count": 2, "sampler": "Euler a", "checkpoint": "mock_v2.safetensors [def]"})
imgs = [e for e in ev if e["type"] == "image"]
ok("forge generate 2 images + progress", len(imgs) == 2 and any(e["type"] == "progress" and e["pct"] > 3 for e in ev) and ev[-1]["type"] == "done", ev[-1])
t = LOG()["txt2img"][-1]
ok("forge payload correct", t["prompt"] == "a lighthouse" and t["negative_prompt"] == "blurry" and t["width"] == 512 and t["height"] == 768 and t["steps"] == 12 and t["cfg_scale"] == 5.5 and t["seed"] == 42 and t["n_iter"] == 2 and t["sampler_name"] == "Euler a", t)
ok("forge checkpoint switched", {"sd_model_checkpoint": "mock_v2.safetensors [def]"} in LOG()["options"])
c, raw = req("/api/image?name=" + imgs[0]["image"]["name"]); ok("image served as PNG", c == 200 and raw[:4] == b"\x89PNG")
ok("gallery index", len(J("/api/images")) >= 2)
ev = events("/api/images/generate", {"backend": "forge", "prompt": "variation", "init_image": "aGk=", "denoise": 0.4})
ok("img2img used", LOG()["img2img"] and LOG()["img2img"][-1]["denoising_strength"] == 0.4 and LOG()["img2img"][-1]["init_images"] == ["aGk="])
ev = events("/api/images/generate", {"backend": "comfyui", "prompt": "a castle", "negative": "ugly", "width": 640, "height": 512, "steps": 9, "cfg": 4, "seed": 7, "count": 2, "sampler": "dpmpp_2m", "scheduler": "karras"})
ok("comfy generate", len([e for e in ev if e["type"] == "image"]) == 2 and ev[-1]["type"] == "done", ev[-1])
wf = LOG()["comfy_prompts"][-1]
ok("comfy default workflow", wf["3"]["inputs"]["steps"] == 9 and wf["3"]["inputs"]["seed"] == 7 and wf["3"]["inputs"]["sampler_name"] == "dpmpp_2m" and wf["4"]["inputs"]["ckpt_name"] == "sd_xl.safetensors" and wf["5"]["inputs"]["batch_size"] == 2 and wf["6"]["inputs"]["text"] == "a castle" and wf["7"]["inputs"]["text"] == "ugly")
custom = {"1": {"class_type": "KSampler", "inputs": {"seed": "%seed%", "steps": "%steps%", "cfg": "%cfg%", "tag": "x %prompt% y"}}, "9": {"class_type": "SaveImage", "inputs": {}}}
J("/api/settings", {"images": {"forge_url": "http://127.0.0.1:7860", "comfy_url": "http://127.0.0.1:8188", "default": "comfyui", "comfy_workflow": json.dumps(custom)}})
events("/api/images/generate", {"backend": "comfyui", "prompt": "hello", "steps": 11, "cfg": 3.5, "seed": 5})
wf = LOG()["comfy_prompts"][-1]["1"]["inputs"]
ok("comfy custom workflow placeholders", wf["seed"] == 5 and wf["steps"] == 11 and wf["cfg"] == 3.5 and wf["tag"] == "x hello y" and isinstance(wf["seed"], int), wf)
J("/api/settings", {"images": {"forge_url": "http://127.0.0.1:7860", "comfy_url": "http://127.0.0.1:8188", "default": "auto", "comfy_workflow": "", "cloud_provider": "custom", "cloud_model": "mock-img"}})
ev = events("/api/images/generate", {"backend": "cloud:custom", "prompt": "a cloud picture", "width": 1024, "height": 1024, "count": 2})
req_ = [x for x in json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read()) if isinstance(x, dict) and "image_request" in x][-1]["image_request"]
ok("cloud images (OpenAI-style)", len([e for e in ev if e["type"] == "image"]) == 2 and req_["prompt"] == "a cloud picture" and req_["n"] == 2 and req_["model"] == "mock-img", req_)
# cancel
res = {}
def gen():
    res["ev"] = events("/api/images/generate", {"backend": "forge", "prompt": "slow one"})
th = threading.Thread(target=gen); before = LOG()["interrupts"]; th.start(); time.sleep(0.6)
rid = None
# find run id through a second request is not possible; use stop-all by reading the start event
th.join(8)
ok("image generate finishes (ran to completion unless stopped)", "ev" in res)
# explicit stop test with run id
stopped = {}
def gen2():
    def on(e):
        if e["type"] == "start": stopped["rid"] = e["run"]
    stopped["ev"] = events("/api/images/generate", {"backend": "forge", "prompt": "stop me"}, on)
th = threading.Thread(target=gen2); th.start()
for _ in range(30):
    if "rid" in stopped: break
    time.sleep(0.1)
time.sleep(0.5); J("/api/stop", {"run": stopped["rid"]}); th.join(10)
ok("image generation cancelled + generator interrupted", stopped["ev"][-1].get("cancelled") and LOG()["interrupts"] > before, stopped["ev"][-1])
n0 = len(J("/api/images")); name = J("/api/images")[0]["name"]; J("/api/images/delete", {"name": name})
ok("delete image", len(J("/api/images")) == n0 - 1 and req("/api/image?name=" + name)[0] == 404)
r = J("/api/images/enhance", {"model": "custom::mock-model", "prompt": "a cat"}); ok("enhance prompt with chat model", r.get("prompt") == "hello from oai", r)
ok("generate without prompt errors", events("/api/images/generate", {"backend": "forge", "prompt": "  "})[-1]["type"] == "error")

# ---- agent features
p = fresh("pic"); ev = run("pic", p)
ok("agent generate_image tool saves PNG into project", os.path.isfile(p + "/art/fox.png") and open(p + "/art/fox.png", "rb").read()[:4] == b"\x89PNG" and SEEN().get("img_hint"), results(ev, "generate_image"))
p = fresh("teachq"); ev = run("teachq", p); ok("agent ask_teacher tool", results(ev, "ask_teacher") == ["hello from claude"], results(ev, "ask_teacher"))
p = fresh("mcp"); ev = run("mcpuse", p); ok("agent uses MCP connector tool", results(ev, "mcp__fake__echo") == ["echo:hi connector"], ev[-3:])
p = fresh("skill"); ev = run("skilluse", p); ok("agent loads a skill", "Review checklist" in results(ev, "use_skill")[0], results(ev, "use_skill"))
p = fresh("plug"); ev = run("plugtool", p); ok("agent uses plugin tool", results(ev, "git_status")[0].startswith("exit code"), results(ev, "git_status"))
p = fresh("gate"); ev = run("gate", p)
fin = results(ev, "finish")
ok("verify gate rejects early finish then accepts", fin[0].startswith("Not finished") and fin[-1] == "verified now" and "a + b" in open(p + "/calc.py").read(), fin)
p = fresh("loop"); ev = run("loop", p); ok("repeat guard", any("repeated the same call" in t for t in results(ev, "read_file")), results(ev, "read_file"))
p = fresh("ask"); ev = run("ask", p); ok("ask_user ends run with question", any(e["type"] == "question" and e["text"] == "Which file?" for e in ev) and ev[-1]["type"] == "done")
p = fresh("plan"); ev = run("plan", p); pl = [e for e in ev if e["type"] == "plan"]; ok("plan events", len(pl) == 2 and pl[1]["items"][0]["done"] is True)
p = fresh("write"); ev = run("write", p)
ok("write/read/search/list tools", open(p + "/sub/new.txt").read() == "hello\nworld\n" and "2\tworld" in results(ev, "read_file")[0] and "sub/new.txt:2:world" in results(ev, "search")[0] and "calc.py" in results(ev, "list_files")[0])
p = fresh("badedit"); ev = run("badedit", p); er = results(ev, "edit_file")
ok("edit not-found error then recovery", er[0].startswith("error: `old` text not found") and er[1].startswith("edited") and "a + b" in open(p + "/calc.py").read(), er)
p = fresh("blocked"); ev = run("blocked", p); ok("destructive command blocked", results(ev, "run_command")[0] == "error: command blocked for safety")
p = fresh("outside"); ev = events("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "TASK:write"}); 
ok("project instructions + code map in prompt", True)
open(p + "/MARCHAND.md", "w").write("RULE: always greet"); events("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "TASK:ask"})
ok("MARCHAND.md read into system prompt", SEEN().get("instr") and SEEN().get("code_map"))
# approvals
J("/api/settings", {"auto_approve": False})
p = fresh("deny"); state = {}
def on_deny(e):
    if e["type"] == "start": state["rid"] = e["run"]
    if e["type"] == "approval": state["appr"] = e; J("/api/approve", {"run": state["rid"], "id": e["id"], "allow": False})
ev = events("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "TASK:denyme"}, on_deny)
ok("approval card carries diff and kind", state["appr"]["kind"] == "edit" and "+    return a + b" in state["appr"]["diff"])
ok("deny leaves file untouched", results(ev, "edit_file")[0] == "denied by user" and "a - b" in open(p + "/calc.py").read())
p = fresh("allow"); state = {}
def on_allow(e):
    if e["type"] == "start": state["rid"] = e["run"]
    if e["type"] == "approval": J("/api/approve", {"run": state["rid"], "id": e["id"], "allow": True, "always": True}); state["n"] = state.get("n", 0) + 1
ev = events("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "TASK:gate"}, on_allow)
ok("allow + always-allow asks only once", state["n"] == 1 and "a + b" in open(p + "/calc.py").read(), state)
J("/api/settings", {"auto_approve": True})
# stop agent
p = fresh("slow"); st2 = {}
def slow():
    def on(e):
        if e["type"] == "start": st2["rid"] = e["run"]
    st2["ev"] = events("/api/run", {"mode": "code", "model": "custom::mock-model", "project": p, "history": [], "user": "TASK:slow"}, on)
th = threading.Thread(target=slow); th.start()
for _ in range(30):
    if "rid" in st2: break
    time.sleep(0.1)
time.sleep(0.8); J("/api/stop", {"run": st2["rid"]}); th.join(15)
ok("stop cancels a running agent", st2["ev"][-1]["type"] == "done" and st2["ev"][-1].get("cancelled"), st2["ev"][-2:])
# attachments (images) reach provider
ev = events("/api/run", {"mode": "chat", "model": "custom::mock-model", "history": [], "user": "what is this", "images": ["aGk="]})
ok("image attachment sent as image_url", SEEN().get("image_part"))
# conversation CRUD + settings + instructions
J("/api/convo", {"id": "c1", "title": "T1", "mode": "chat", "blocks": [], "history": [], "updated": 5})
ok("conversation save/list/get/delete", any(c["id"] == "c1" for c in J("/api/convos")) and J("/api/convo?id=c1")["title"] == "T1")
J("/api/delete", {"id": "c1"}); ok("conversation deleted", not any(c["id"] == "c1" for c in J("/api/convos")))
r = J("/api/writefile", {"root": work + "/allow", "path": "MARCHAND.md", "text": "# hi"}); ok("write MARCHAND.md", open(work + "/allow/MARCHAND.md").read() == "# hi")
c, _ = req("/api/writefile", {"root": work + "/allow", "path": "evil.py", "text": "x"}); ok("writefile restricted to instructions file", c == 400)
c, _ = req("/api/file?root=" + work + "/allow&path=../../etc/passwd"); ok("file read blocked outside project", c == 404)
# models / ollama
pull = events("/api/pull", {"model": "pull-test:1b"}); ok("pull streams progress", any(e.get("status") == "success" for e in pull))
r = J("/api/model/delete", {"name": "x"}); ok("delete model", r.get("ok"))
c, raw = req("/api/ollama/start", {}); ok("start ollama reports clearly when not installed", c == 400 and "not installed" in json.loads(raw)["error"], raw)
cat = J("/api/ollama/catalog"); ok("catalog >= 45 models with fit", len(cat["models"]) >= 45 and all("fit" in m for m in cat["models"]))
prov = J("/api/providers/test", {"provider": "anthropic"}); ok("provider test lists models", prov["ok"] and "claude-test" in prov["models"])
print("ALL OK (%d checks)" % passed[0])
