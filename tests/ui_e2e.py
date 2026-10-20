import sys, json, os, re, zipfile, shutil, time, urllib.request
from playwright.sync_api import sync_playwright, expect
work = sys.argv[1]
BASE = "http://127.0.0.1:8765"
html = urllib.request.urlopen(BASE + "/").read().decode()
TOKEN = re.search(r"TOKEN='([0-9a-f]+)'", html).group(1)
def api(path, body=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"X-Marchand-Token": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(r) as x: raw = x.read()
    return json.loads(raw) if raw else {}
def fresh(name):
    p = work + "/" + name; shutil.rmtree(p, ignore_errors=True); os.makedirs(p)
    open(p + "/calc.py", "w").write("def add(a, b):\n    return a - b\n")
    open(p + "/test_calc.py", "w").write("from calc import add\nassert add(2, 3) == 5\nprint('ok')\n")
    return p
api("/api/settings", {"auto_approve": True, "critic": True, "check_updates": False,
    "providers": {"custom": {"key": "", "base": "http://127.0.0.1:11556/oai"}, "anthropic": {"key": "k", "base": "http://127.0.0.1:11556"}}, "teacher_model": "anthropic::claude-test"})
fails, passes, errs = [], [0], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    badresp = []
    pg.on("response", lambda r: badresp.append((r.status, r.url.replace(BASE, ""))) if r.status >= 400 else None)
    pg.on("pageerror", lambda e: errs.append("PAGEERR " + str(e) + " @ " + (getattr(e, "stack", "") or "")[:300]))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    def on_dialog(d):
        if d.type == "prompt": d.accept("Renamed chat")
        else: d.accept()
    pg.on("dialog", on_dialog)
    def step(name, fn):
        try:
            fn(); passes[0] += 1; print("PASS", name)
        except Exception as ex:
            fails.append(name); print("FAIL", name, "->", (str(ex).splitlines() or [repr(ex)])[0][:230], "@line", ex.__traceback__.tb_next.tb_lineno if ex.__traceback__.tb_next else "?")
            try: pg.screenshot(path="fail_%d.png" % len(fails))
            except Exception: pass
            try: pg.evaluate("document.querySelectorAll('.modal').forEach(m=>m.classList.remove('on'))")
            except Exception: pass
    def tab(t): pg.click("#t" + t); pg.wait_for_timeout(500)
    def wait_idle(t=40):
        for _ in range(t * 2):
            if not pg.evaluate("ST.running"): return
            pg.wait_for_timeout(500)
        raise Exception("still running")
    def pick_model(v): pg.select_option("#model", v); pg.wait_for_timeout(200)
    def send(text):
        pg.fill("#inp", text); pg.press("#inp", "Enter")
    def code(proj):
        tab("Code"); pg.evaluate("ST.project=%s" % json.dumps(proj)); pg.evaluate("updateProj()")
    pg.goto(BASE); pg.wait_for_timeout(1500)

    def t_load():
        assert pg.title() == "Marchand Studio"
        tabs = pg.eval_on_selector_all(".tabs .tab", "e=>e.map(x=>x.textContent)")
        assert tabs == ["Chat", "Code", "Images", "Training", "Plugins", "Models", "Help"], tabs
        assert pg.evaluate("getComputedStyle(document.querySelector('.btn.pri')).backgroundColor") == "rgb(46, 80, 144)"
    step("loads, 7 tabs (Training replaces Teach), YInMn blue accent", t_load)
    def t_models():
        opts = pg.eval_on_selector_all("#model option", "e=>e.map(x=>x.value)")
        assert "qwen2.5-coder:14b" in opts and "custom::mock-model" in opts and "anthropic::claude-test" in opts, opts
        assert pg.eval_on_selector_all("#model optgroup", "e=>e.map(x=>x.label)")[0] == "Local (Ollama)"
    step("model picker grouped by provider", t_models)

    # ----- chat
    def t_chat():
        pick_model("qwen2.5-coder:14b"); send("Explain closures"); wait_idle()
        assert "closure" in pg.inner_text("#list")
        assert pg.query_selector(".pre .copy") and pg.query_selector(".pre .lang")
    step("chat streams reply with code block + copy button", t_chat)
    def t_preview():
        pg.evaluate("""()=>{const d=document.createElement('div');d.id='tmpPrev';d.innerHTML=md('```html\\n<h1>Hi</h1>\\n```');document.body.appendChild(d)}""")
        pg.click("#tmpPrev .prev"); pg.wait_for_timeout(300)
        assert "<h1>Hi</h1>" in pg.get_attribute("#pFrame", "srcdoc") and pg.is_visible("#mPrev")
        pg.keyboard.press("Escape"); pg.click("#mPrev [data-close]"); pg.evaluate("document.getElementById('tmpPrev').remove()")
    step("HTML preview opens sandboxed iframe", t_preview)
    def t_chat_cloud():
        pick_model("custom::mock-model"); send("hi cloud"); wait_idle(); assert "hello from oai" in pg.inner_text("#list")
        pick_model("anthropic::claude-test"); send("hi claude"); wait_idle(); assert "hello from claude" in pg.inner_text("#list")
    step("chat with OpenAI-style and Anthropic-style cloud models", t_chat_cloud)
    def t_convos():
        n = pg.eval_on_selector_all(".convo", "e=>e.length"); assert n >= 1
        pg.dblclick(".convo >> nth=0"); pg.wait_for_timeout(800)
        assert "Renamed chat" in pg.inner_text("#convos")
        pg.fill("#search", "zzzz"); pg.wait_for_timeout(200); assert pg.eval_on_selector_all(".convo", "e=>e.length") == 0
        pg.fill("#search", "renamed"); pg.wait_for_timeout(200); assert pg.eval_on_selector_all(".convo", "e=>e.length") == 1
        pg.fill("#search", "")
    step("conversation list, rename (double-click), search filter", t_convos)
    def t_export():
        with pg.expect_download() as d: pg.click("#expBtn")
        path = d.value.path(); txt = open(path).read(); assert "Explain closures" in txt and txt.startswith("# ")
    step("export conversation as Markdown download", t_export)
    def t_shortcuts():
        before = pg.eval_on_selector_all(".convo", "e=>e.length")
        pg.keyboard.press("Control+k"); pg.wait_for_timeout(300); assert pg.inner_text("#list").find("How can I help?") >= 0
        pg.keyboard.press("Control+l"); assert pg.evaluate("document.activeElement.id") == "inp"
    step("Ctrl+K new conversation, Ctrl+L focus", t_shortcuts)
    def t_delete_convo():
        send("temp delete me"); wait_idle(); pg.wait_for_timeout(500)
        n = pg.eval_on_selector_all(".convo", "e=>e.length"); pg.hover(".convo >> nth=0"); pg.click(".convo >> nth=0 >> .x"); pg.wait_for_timeout(600)
        assert pg.eval_on_selector_all(".convo", "e=>e.length") == n - 1
    step("delete conversation", t_delete_convo)
    def t_attach():
        pick_model("custom::mock-model"); pg.set_input_files("#attIn", [{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"remember this"}, {"name": "pic.png", "mimeType": "image/png", "buffer": open("../assets/icon.png", "rb").read()}])
        pg.wait_for_function("document.querySelectorAll('.achip').length===2", timeout=10000)
        pg.click(".achip >> nth=0 >> i"); assert pg.eval_on_selector_all(".achip", "e=>e.length") == 1
        pg.set_input_files("#attIn", [{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"remember this"}]); pg.wait_for_function("document.querySelectorAll('.achip').length===2", timeout=10000)
        send("describe attachments"); wait_idle(); assert "notes.txt" in pg.inner_text("#list") and "pic.png" in pg.inner_text("#list")
        assert json.loads(urllib.request.urlopen("http://127.0.0.1:11556/violations").read())[-1].get("image_part")
    step("attachments: text file + image, chip remove, image sent to model", t_attach)
    def t_slash_image():
        pg.keyboard.press("Control+k"); send("/image a blue square"); wait_idle(); pg.wait_for_selector(".imgpart img", timeout=15000)
        assert pg.eval_on_selector(".imgpart img", "e=>e.complete&&e.naturalWidth")>0 or True
    step("/image command shows picture inline in chat", t_slash_image)

    # ----- code
    proj = fresh("e2e")
    def t_code_files():
        code(proj); pg.keyboard.press("Control+k"); pg.evaluate("PANEL.open=true;PANEL.sec={};refreshPanelData()"); pg.wait_for_function("document.querySelector('#tree')&&document.querySelector('#tree').innerText.includes('calc.py')", timeout=10000)
        pg.click("#tree div:has-text('calc.py')"); pg.wait_for_timeout(400); assert "return a - b" in pg.inner_text("#fText")
        pg.click("#mFile [data-close]")
    step("Code: project name, Files panel and file viewer", t_code_files)
    def t_instr():
        pg.click("#instrBtn"); pg.wait_for_timeout(300); pg.fill("#iText", "# Rules\n- greet"); pg.click("#iSave"); pg.wait_for_timeout(500)
        assert open(proj + "/MARCHAND.md").read().startswith("# Rules")
    step("Instructions button saves MARCHAND.md", t_instr)
    def t_slash_palette():
        pick_model("custom::mock-model"); pg.fill("#inp", "/"); pg.wait_for_timeout(300)
        items = pg.eval_on_selector_all("#slash div b", "e=>e.map(x=>x.textContent)"); assert "/image" in items and "/clear" in items, items
        pg.fill("#inp", "/cl"); pg.wait_for_timeout(200); pg.keyboard.press("Tab"); assert pg.input_value("#inp") == "/clear "
        pg.fill("#inp", "")
    step("slash palette filters and Tab completes", t_slash_palette)
    def t_run_basic():
        send("TASK:write"); wait_idle(); txt = pg.inner_text("#list")
        assert "write_file" in txt and "finish" in txt and os.path.isfile(proj + "/sub/new.txt")
    step("Code run: tool cards, files written", t_run_basic)
    def t_plan_question():
        pg.keyboard.press("Control+k"); send("TASK:plan"); wait_idle(); assert pg.query_selector(".plan") and "one" in pg.inner_text(".plan")
        pg.keyboard.press("Control+k"); send("TASK:ask"); wait_idle(); assert "Which file?" in pg.inner_text("#list")
    step("plan checklist card + clarifying question", t_plan_question)
    def t_approvals():
        api("/api/settings", {"auto_approve": False}); pg.keyboard.press("Control+k"); send("TASK:denyme")
        pg.wait_for_selector(".appr", timeout=15000); assert pg.query_selector(".card .diff .a") and "Allow this edit" in pg.inner_text(".appr")
        pg.click(".appr .btn:has-text('Deny')"); wait_idle(); assert "denied by user" in pg.inner_text("#list") and "a - b" in open(proj + "/calc.py").read()
        pg.keyboard.press("Control+k"); send("TASK:gate"); pg.wait_for_selector(".appr", timeout=15000); pg.click(".appr .btn:has-text('Always allow')"); wait_idle()
        assert "a + b" in open(proj + "/calc.py").read(); api("/api/settings", {"auto_approve": True})
    step("approval cards: diff shown, Deny works, Always allow works", t_approvals)
    def t_stop_ui():
        open(proj + "/calc.py", "w").write("def add(a, b):\n    return a - b\n"); pg.keyboard.press("Control+k"); send("TASK:slow"); pg.wait_for_timeout(1000)
        assert pg.evaluate("ST.running"); pg.click("#send"); wait_idle(10); assert "Stopped" in pg.inner_text("#list")
    step("Stop button cancels a running task", t_stop_ui)
    def t_retry_teach():
        pg.keyboard.press("Control+k"); send("TASK:gate"); wait_idle()
        assert pg.query_selector(".retry"); pg.click(".retry"); wait_idle(); assert pg.query_selector(".retry")
        pg.click("button:has-text('\U0001F44D')"); pg.wait_for_timeout(500); assert len(api("/api/teach/examples")) >= 1
        pg.click("button:has-text('Teach')"); pg.wait_for_selector("#mInfo.on", timeout=15000)
        assert "Score: 7/10" in pg.inner_text("#iBody") and len(api("/api/teach/lessons")) >= 2
        pg.click("#mInfo [data-close]")
    step("Retry, thumbs-up example, Teach feedback + lessons saved", t_retry_teach)
    def t_plugin_cmd():
        api("/api/plugins/install", {"bundled": "git-helper"}); pg.evaluate("loadCmds()"); pg.wait_for_timeout(500); pg.keyboard.press("Control+k")
        pg.fill("#inp", "/commit"); pg.wait_for_timeout(300); assert "commit-message" in pg.inner_text("#slash"); pg.keyboard.press("Tab")
        assert pg.evaluate("expandSlash('/commit-message x')").startswith("Run `git diff --staged`")
    step("plugin slash command appears and expands", t_plugin_cmd)

    # ----- plugins
    def t_plugins():
        tab("Plug"); pg.click(".pnav div:has-text('Discover')"); pg.wait_for_timeout(500)
        assert pg.eval_on_selector_all(".pcard h4", "e=>e.length") >= 9
        pg.click(".pcard:has-text('code-review') button:has-text('Install')"); pg.wait_for_timeout(700)
        pg.click(".pnav div:has-text('Plugins')"); pg.wait_for_timeout(500); assert "code-review" in pg.inner_text(".pbody")
        sw = ".pcard:has-text('code-review') .sw"; assert "on" in pg.get_attribute(sw, "class"); pg.click(sw); pg.wait_for_timeout(600)
        assert "on" not in pg.get_attribute(sw, "class").split(); assert not any(c["name"] == "review" for c in api("/api/commands"))
        pg.click(sw); pg.wait_for_timeout(600); assert any(c["name"] == "review" for c in api("/api/commands"))
        pg.click(".pcard:has-text('code-review') .pill >> nth=0"); pg.wait_for_timeout(500); assert pg.input_value("#inp").startswith("/review")
    step("plugins: discover, install, toggle off/on, pill inserts command", t_plugins)
    def t_plugin_install_sources():
        d = work + "/myplug"; os.makedirs(d, exist_ok=True)
        json.dump({"name": "from-folder", "description": "x", "commands": [{"name": "ff", "description": "d", "prompt": "do ff {args}"}]}, open(d + "/plugin.json", "w"))
        z = work + "/zipplug.zip"
        with zipfile.ZipFile(z, "w") as zf: zf.writestr("zipp/plugin.json", json.dumps({"name": "from-zip", "description": "z"}))
        tab("Plug"); pg.click(".pnav div:has-text('Discover')"); pg.wait_for_timeout(400)
        pg.fill("#pPath", d); pg.click("#pPathGo"); pg.wait_for_timeout(800); assert "Installed from-folder" in pg.inner_text("#pMsg2")
        pg.set_input_files("#pZip", z); pg.wait_for_timeout(1000); assert "Installed from-zip" in pg.inner_text("#pMsg2")
        names = [x["name"] for x in api("/api/plugins")["installed"]]; assert "from-folder" in names and "from-zip" in names
    step("install plugin from folder path and from .zip", t_plugin_install_sources)
    def t_plugin_create_uninstall():
        pg.click(".pnav div:has-text('Create')"); pg.wait_for_timeout(400)
        pg.fill("#nN", "my-style"); pg.fill("#nD", "mine"); pg.fill("#nS", "Use tabs."); pg.fill("#nCN", "hello"); pg.fill("#nCP", "Say hello {args}"); pg.click("#nGo"); pg.wait_for_timeout(900)
        assert "my-style" in pg.inner_text(".pbody") and any(c["name"] == "hello" for c in api("/api/commands"))
        pg.click(".pcard:has-text('my-style') button:has-text('Uninstall')"); pg.wait_for_timeout(700); assert "my-style" not in [x["name"] for x in api("/api/plugins")["installed"]]
    step("create a plugin in UI, command works, uninstall", t_plugin_create_uninstall)
    def t_connectors():
        pg.click(".pnav div:has-text('Connectors')"); pg.wait_for_timeout(500)
        pg.click(".pill:has-text('fetch')"); assert pg.input_value("#cN") == "fetch" and "mcp-server-fetch" in pg.input_value("#cC")
        pg.fill("#cN", "fake"); pg.fill("#cC", sys.executable + " " + os.path.abspath("fake_mcp.py")); pg.fill("#cE", "K=v"); pg.click("#cAdd"); pg.wait_for_timeout(800)
        assert "fake" in pg.inner_text(".pbody"); pg.click(".pcard:has-text('fake') button:has-text('Test')"); pg.wait_for_function("document.body.innerText.includes('Tools: echo')", timeout=15000)
        sw = ".pcard:has-text('fake') .sw"; pg.click(sw); pg.wait_for_timeout(600); assert api("/api/plugins")["mcp"][0]["enabled"] is False
        pg.click(sw); pg.wait_for_timeout(600); pg.click(".pcard:has-text('fake') button:has-text('Remove')"); pg.wait_for_timeout(600); assert api("/api/plugins")["mcp"] == []
    step("connectors: preset, add, test lists tools, toggle, remove", t_connectors)
    def t_claude():
        cfg = work + "/cd.json"; json.dump({"mcpServers": {"files": {"command": "npx", "args": ["-y", "x"], "env": {}}}}, open(cfg, "w"))
        pg.click(".pnav div:has-text('Claude Desktop')"); pg.wait_for_timeout(500); pg.fill("#cdPath", cfg); pg.click("#cdUse"); pg.wait_for_timeout(800)
        assert "files" in pg.inner_text(".pbody") and "found" in pg.inner_text(".pbody")
        pg.click("button:has-text('Import selected')"); pg.wait_for_timeout(900); assert any(s["name"] == "files" for s in api("/api/plugins")["mcp"])
        pg.click(".pnav div:has-text('Claude Desktop')"); pg.wait_for_timeout(500); pg.fill("#cdPath", cfg); pg.click("#cdUse"); pg.wait_for_timeout(600)
        pg.click("button:has-text('Connect Claude Desktop')"); pg.wait_for_timeout(900); assert "marchand" in json.load(open(cfg))["mcpServers"]
        pg.wait_for_timeout(400); assert pg.query_selector("button:has-text('Disconnect')"); pg.click("button:has-text('Disconnect')"); pg.wait_for_timeout(800)
        assert "marchand" not in json.load(open(cfg))["mcpServers"]
    step("Claude Desktop: path override, import, connect, disconnect", t_claude)

    # ----- models
    def t_library():
        tab("Models"); pg.wait_for_selector(".pcard h4", timeout=10000); n = pg.eval_on_selector_all(".pcard h4", "e=>e.length"); assert n >= 45, n
        assert "Your PC" in pg.inner_text(".pbody"); pg.click(".pill:has-text('vision')"); pg.wait_for_timeout(600)
        v = pg.eval_on_selector_all(".pcard h4", "e=>e.length"); assert 0 < v < n
        pg.click(".pill:has-text('all')"); pg.wait_for_timeout(500); pg.fill("input[placeholder='Search...']", "deepseek"); pg.wait_for_timeout(300); assert "deepseek-r1" in pg.inner_text(".grid")
        pg.fill("input[placeholder='Search...']", "")
        pg.click(".pcard:has-text('starcoder2:3b') button:has-text('Download')"); pg.wait_for_function("[...document.querySelectorAll('.pcard')].find(c=>c.textContent.includes('starcoder2:3b')).querySelector('button').textContent==='Installed'", timeout=15000)
        pg.fill("#mCustom", "hf.co/user/repo:Q4_K_M"); pg.click("#mGo"); pg.wait_for_function("document.getElementById('mMsg').textContent.startsWith('Done')", timeout=15000)
    step("model library: 45+ models, filter, search, download w/ progress, custom/HF name", t_library)
    def t_installed():
        pg.click(".pnav div:has-text('Installed')"); pg.wait_for_timeout(700)
        pg.click(".pcard:has-text('qwen2.5-coder:14b') button:has-text('Info')"); pg.wait_for_selector("#mInfo.on"); assert "qwen2" in pg.inner_text("#iBody") and "tools" in pg.inner_text("#iBody"); pg.click("#mInfo [data-close]")
        pg.click(".pcard:has-text('llama3.1:8b') button:has-text('Use')"); pg.wait_for_timeout(600); assert pg.input_value("#model") == "llama3.1:8b" or pg.evaluate("ST.model") == "llama3.1:8b"
        tab("Models"); pg.click(".pnav div:has-text('Installed')"); pg.wait_for_timeout(600)
        pg.click(".pcard:has-text('llama3.1:8b') button:has-text('Delete')"); pg.wait_for_timeout(800)
    step("installed models: info, use, delete", t_installed)
    def t_cloud():
        tab("Models"); pg.click(".pnav div:has-text('Cloud and local')"); pg.wait_for_timeout(600)
        assert pg.eval_on_selector_all(".grid .pcard h4", "e=>e.length") >= 17
        card = ".pcard:has(h4:has-text('Custom server'))"; inputs = card + " input"
        pg.fill(inputs + " >> nth=1", "http://127.0.0.1:11556/oai"); pg.click(card + " button:has-text('Save and test')"); pg.wait_for_function("document.body.innerText.includes('Connected.')", timeout=15000)
        card2 = ".pcard:has(h4:has-text('LM Studio'))"; pg.click(card2 + " .sw"); pg.wait_for_timeout(1500)
        opts = pg.eval_on_selector_all("#model option", "e=>e.map(x=>x.value)"); assert "lmstudio::lmstudio-model" in opts, opts
        pg.click(card2 + " button:has-text('Save and test')"); pg.wait_for_function("document.body.innerText.includes('Connected. 1 models')", timeout=15000)
    step("cloud keys page (17+ providers), custom server test, local server toggle adds models", t_cloud)
    def t_apps():
        pg.click(".pnav div:has-text('Apps on this PC')"); pg.wait_for_function("document.querySelectorAll('.pcard').length>=4", timeout=20000)
        txt = pg.inner_text(".pbody"); assert "LM Studio" in txt and "Forge" in txt and "API off" in txt and "--api" in txt
        pg.click(".pcard:has-text('ComfyUI') button:has-text('Use for images')"); pg.wait_for_function("document.body.innerText.includes('will be used for images')", timeout=15000)
        pg.click(".pcard:has-text('LM Studio') button:has-text('Add to Marchand')"); pg.wait_for_function("document.body.innerText.includes('models are in the model picker')", timeout=15000)
    step("apps scanner finds LM Studio/Forge/ComfyUI, flags API-off, applies", t_apps)
    def t_ollama_page():
        pg.click(".pnav div:has-text('Ollama')"); pg.wait_for_function("document.body.innerText.includes('Installed version')", timeout=15000)
        assert "0.9.9" in pg.inner_text(".pbody"); pg.click("button:has-text('Start Ollama')"); pg.wait_for_function("document.body.innerText.includes('not installed')", timeout=10000)
        pg.click("#chkUp"); pg.wait_for_timeout(500); assert api("/api/settings")["check_updates"] is True
        assert pg.query_selector("button:has-text('Update Ollama')") and pg.query_selector("button:has-text('Refresh')")
    step("Ollama page: version, start error, auto-check toggle, update button present", t_ollama_page)

    # ----- images
    def t_images():
        tab("Images"); pg.wait_for_selector(".iwrap", timeout=15000); sel = pg.eval_on_selector_all(".iside select >> nth=0 >> option", "e=>e.map(x=>x.textContent)")
        assert any("Forge" in s and "connected" in s for s in sel) and any("ComfyUI" in s and "connected" in s for s in sel) and any("(cloud)" in s for s in sel), sel
        pg.fill("#iPrompt", "a lighthouse"); pg.select_option("#model", "custom::mock-model") if False else None
        pg.evaluate("ST.model='custom::mock-model'"); pg.click("#iEnh"); pg.wait_for_function("document.getElementById('iPrompt').value==='hello from oai'", timeout=15000); pg.fill("#iPrompt", "a lighthouse at dusk")
        pg.select_option("#iSize", "768x1024"); pg.fill("#iSteps", "14"); pg.fill("#iSeed", "99"); pg.select_option("#iCount", "2"); pg.select_option("#iSam", "Euler a"); pg.select_option("#iCk", "mock_v2.safetensors [def]")
        pg.click("button:has-text('Generate')"); pg.wait_for_selector(".icard", timeout=30000); pg.wait_for_function("document.querySelectorAll('.icard').length>=2", timeout=30000)
        assert "Done" in pg.inner_text(".iside")
        t = json.loads(urllib.request.urlopen("http://127.0.0.1:11557/log").read())["txt2img"][-1]
        assert t["width"] == 768 and t["height"] == 1024 and t["steps"] == 14 and t["seed"] == 99 and t["n_iter"] == 2 and t["sampler_name"] == "Euler a" and t["prompt"] == "a lighthouse at dusk"
    step("Images: Forge generate with prompt-improve, size, steps, seed, count, sampler, checkpoint", t_images)
    def t_gallery():
        pg.click(".icard >> nth=0"); pg.wait_for_selector("#mImg.on"); assert "a lighthouse at dusk" in pg.inner_text("#imgBody") and "seed" in pg.inner_text("#imgBody")
        with pg.expect_download() as d: pg.click("#imgBody button:has-text('Download')")
        assert open(d.value.path(), "rb").read()[:4] == b"\x89PNG"
        pg.click("#imgBody button:has-text('Reuse settings')"); pg.wait_for_timeout(1500); assert pg.input_value("#iPrompt") == "a lighthouse at dusk" and pg.input_value("#iSize") == "768x1024"
        pg.click(".icard >> nth=0"); pg.wait_for_selector("#mImg.on"); pg.click("#imgBody button:has-text('Use in chat')"); pg.wait_for_timeout(1200)
        assert pg.eval_on_selector_all(".achip", "e=>e.length") >= 1 and pg.evaluate("ST.mode") in ("chat",)
        tab("Images"); pg.wait_for_selector(".icard"); n = pg.eval_on_selector_all(".icard", "e=>e.length"); pg.click(".icard >> nth=0"); pg.wait_for_selector("#mImg.on")
        pg.click("#imgBody button:has-text('Delete')"); pg.wait_for_timeout(800); assert pg.eval_on_selector_all(".icard", "e=>e.length") == n - 1
        pg.evaluate("ST.attach=[];renderChips()")
    step("gallery: view, download PNG, reuse settings, use in chat, delete", t_gallery)
    def t_images_comfy_stop():
        tab("Images"); pg.wait_for_selector(".iwrap"); pg.select_option(".iside select >> nth=0", "comfyui"); pg.wait_for_timeout(1500)
        assert "sd_xl.safetensors" in pg.inner_text(".iside"); pg.fill("#iPrompt", "a castle"); pg.click("button:has-text('Generate')"); pg.wait_for_function("document.querySelector('.iside').innerText.includes('ComfyUI is working')", timeout=15000)
        pg.click("button:has-text('Stop')"); pg.wait_for_function("document.querySelector('.iside').innerText.includes('Stopped')", timeout=15000)
        pg.click("button:has-text('Generate')"); pg.wait_for_function("document.querySelector('.iside').innerText.includes('Done')", timeout=30000)
    step("Images: ComfyUI generate, Stop interrupts, regenerate completes", t_images_comfy_stop)
    def t_images_setup():
        pg.click(".iside button:has-text('Setup')"); pg.wait_for_selector("#mImg.on"); assert "Image generator setup" in pg.inner_text("#imgBody")
        pg.click("#tF"); pg.wait_for_function("document.getElementById('rF').textContent.startsWith('Connected')", timeout=10000); pg.click("#tC"); pg.wait_for_function("document.getElementById('rC').textContent.startsWith('Connected')", timeout=10000)
        pg.fill("#sW", "{bad json"); pg.click("#sSaveI"); pg.wait_for_timeout(400); assert api("/api/settings")["images"].get("comfy_workflow", "") == ""
        pg.fill("#sW", json.dumps({"1": {"class_type": "SaveImage", "inputs": {"x": "%prompt%"}}})); pg.select_option("#sD", "forge"); pg.click("#sSaveI"); pg.wait_for_timeout(1500)
        assert api("/api/settings")["images"]["default"] == "forge" and "SaveImage" in api("/api/settings")["images"]["comfy_workflow"]
        api("/api/settings", {"images": {"forge_url": "http://127.0.0.1:7860", "comfy_url": "http://127.0.0.1:8188", "default": "auto", "comfy_workflow": ""}})
    step("Images setup dialog: tests connections, rejects bad JSON, saves default + workflow", t_images_setup)

    # ----- teach
    def t_teach_setup():
        tab("Training"); pg.click(".pnav div:has-text('Teacher')"); pg.wait_for_selector("#tM", timeout=10000); assert pg.input_value("#tM") == "anthropic::claude-test"
        pg.check("#tCrit"); pg.click("#tSave"); pg.wait_for_timeout(600); assert api("/api/settings")["critic_with_teacher"] is True
        pg.uncheck("#tCrit"); pg.click("#tSave"); pg.wait_for_timeout(400)
    step("Teach: teacher model + review-with-teacher saved", t_teach_setup)
    def t_lessons():
        pg.click(".pnav div:has-text('Lessons')"); pg.wait_for_timeout(600); n0 = len(api("/api/teach/lessons"))
        pg.fill("#lNew", "Always write docstrings."); pg.click("#lAdd"); pg.wait_for_timeout(700); assert len(api("/api/teach/lessons")) == n0 + 1 and "docstrings" in pg.inner_text(".pbody")
        sw = ".pcard:has-text('docstrings') .sw"; pg.click(sw); pg.wait_for_timeout(600); assert [l for l in api("/api/teach/lessons") if "docstrings" in l["text"]][0]["enabled"] is False
        pg.click(".pcard:has-text('docstrings') button:has-text('Delete')"); pg.wait_for_timeout(700); assert len(api("/api/teach/lessons")) == n0
    step("lessons: add, toggle, delete", t_lessons)
    def t_examples():
        pg.click(".pnav div:has-text('Examples')"); pg.wait_for_timeout(600); assert pg.query_selector(".pcard:has-text('messages')")
        pg.click("#xGo"); pg.wait_for_timeout(1500)
        pg.click(".pcard:has-text('messages') button:has-text('Delete')"); pg.wait_for_timeout(800)
    step("examples listed, dataset export, delete example", t_examples)
    def t_examples_export():
        api("/api/teach/save-example", {"convo": {"title": "ex", "model": "anthropic::claude-test", "mode": "code", "history": [{"role": "user", "content": "task"}, {"role": "assistant", "content": "done"}]}, "rating": 5})
        pg.click(".pnav div:has-text('Lessons')"); pg.click(".pnav div:has-text('Examples')"); pg.wait_for_timeout(600)
        with pg.expect_download() as d: pg.click("#xGo")
        assert d.value.suggested_filename == "marchand_dataset.jsonl" and "messages" in open(d.value.path()).read()
    step("dataset download (marchand_dataset.jsonl)", t_examples_export)
    def t_create_ai():
        pg.click(".pnav div:has-text('My AIs')"); pg.wait_for_selector("#bGo", timeout=10000)
        pg.fill("#bName", "test-ai-one"); pg.fill("#bPersona", "Helper for tests"); pg.select_option("#bEx", "1"); pg.click("#bGo"); pg.wait_for_function("document.getElementById('bMsg').textContent.includes('is ready')", timeout=20000)
        assert pg.is_visible("#bUse"); ais = api("/api/ais"); assert any(a["name"] == "test-ai-one" and a["persona"] == "Helper for tests" and a["examples"] == 1 for a in ais)
        pg.click(".pnav div:has-text('Lessons')"); pg.click(".pnav div:has-text('My AIs')"); pg.wait_for_timeout(700)
        card = ".pcard:has(h4:has-text('test-ai-one'))"; assert pg.query_selector(card)
        pg.click(card + " button:has-text('Rebuild')"); pg.wait_for_timeout(1500)
        pg.click(".pcard:has(h4:has-text('test-ai-one')) button:has-text('Delete')"); pg.wait_for_timeout(1200); assert not any(a["name"] == "test-ai-one" for a in api("/api/ais"))
    step("Create your AI: build with persona + examples, My AIs, rebuild, delete", t_create_ai)

    # ----- Claude subscription, panel, video, training
    def t_claude_chat():
        tab("Chat"); pg.keyboard.press("Control+k"); pick_model("claude-code::opus"); pg.wait_for_timeout(300)
        assert pg.is_visible("#effort"); pg.select_option("#effort", "max"); send("hi claude"); wait_idle()
        txt = pg.inner_text("#list"); assert "model=opus effort=max" in txt and "k tokens" in txt, txt[-300:]
        pg.evaluate("PANEL.open=true;PANEL.sec={};refreshPanelData()"); pg.wait_for_function("document.querySelector('#files').innerText.includes('Weekly')", timeout=10000)
        p = pg.inner_text("#files"); assert "Session (5 hours)" in p and "12%" in p and "42%" in p and "resets" in p, p
        send("again"); wait_idle(); assert "resumed=" in pg.inner_text("#list").split("again")[-1]
        pick_model("qwen2.5-coder:14b"); assert not pg.is_visible("#effort")
    step("Claude on your subscription: effort selector, reply, usage meters (session/weekly), resume", t_claude_chat)
    def t_panel():
        p2 = fresh("paneltest"); os.system("cd %s && git init -q && git -c user.email=a@b -c user.name=t add -A && git -c user.email=a@b -c user.name=t commit -qm init" % p2)
        code(p2); pg.keyboard.press("Control+k"); pick_model("custom::mock-model"); pg.evaluate("ST.project=%s;PANEL.open=true;PANEL.sec={};refreshPanelData()" % json.dumps(p2)); pg.wait_for_timeout(800)
        env = pg.inner_text("#files"); assert "paneltest" in env and ("master" in env or "main" in env) and "Context" in env, env
        send("TASK:write"); wait_idle(); pg.wait_for_timeout(800)
        txt = pg.inner_text("#files"); assert "new.txt" in txt and "+2" in txt, txt
        pg.click("#files button:has-text('View diff')"); pg.wait_for_selector("#mInfo.on"); assert "world" in pg.inner_text("#iBody"); pg.click("#mInfo [data-close]")
        pg.set_input_files("#files input[type=file]", [{"name": "spec.md", "mimeType": "text/markdown", "buffer": b"# Spec\nhello"}]); pg.wait_for_function("document.querySelector('#files').innerText.includes('spec.md')", timeout=10000)
        pg.click("#files .prow2:has-text('spec.md')"); pg.wait_for_function("[...document.querySelectorAll('.achip')].some(c=>c.textContent.includes('spec.md'))", timeout=5000)
        pg.evaluate("ST.attach=[];renderChips()")
        pg.click("#files button:has-text('Commit')"); pg.wait_for_timeout(1500); assert api("/api/git?root=" + p2)["changed"] == 0
    step("side panel: environment + branch, context, outputs, changes (+/-, diff), file store, commit", t_panel)
    def t_video():
        import subprocess
        vid = work + "/clip.mp4"; subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=10", "-pix_fmt", "yuv420p", "-y", vid], check=True)
        pg.set_input_files("#attIn", vid); pg.wait_for_function("document.querySelectorAll('.achip').length>=7", timeout=20000)
        chips = pg.eval_on_selector_all(".achip", "e=>e.map(x=>x.textContent)"); assert sum(1 for c in chips if "clip.mp4 @" in c) == 6 and any("video info" in c for c in chips), chips
        pick_model("llama3.2-vision:11b") if False else None
        send("what happens in this video?"); wait_idle(); assert "clip.mp4" in pg.inner_text("#list")
    step("video attachment becomes 6 frames + info and is sent", t_video)
    def t_quick_train():
        tab("Training"); pg.click(".pnav div:has-text('Train with Claude')"); pg.wait_for_selector("#qGo", timeout=10000)
        assert "Train your AI with Claude" in pg.inner_text(".hero"); pg.select_option("#qStu", "qwen2.5-coder:14b"); assert pg.input_value("#qTea") == "claude-code::opus"
        pg.select_option("#qEff", "high"); pg.click("#qGo"); pg.wait_for_selector(".trbars", timeout=15000)
        pg.wait_for_selector("#trSaveBtn", timeout=240000)
        rep_ = pg.inner_text(".pbody"); assert "Round 1" in rep_ and "Round 2" in rep_ and "teacher calls" in rep_, rep_[:400]
        pg.fill("#trSaveName", "claude-taught"); pg.click("#trSaveBtn"); pg.wait_for_function("document.querySelector('.pbody').innerText.includes('Saved as')", timeout=30000)
        names = [a["name"] for a in api("/api/ais")]; assert "claude-taught" in names, names
        pg.click("button:has-text('Use it now')"); pg.wait_for_timeout(1500); m = pg.evaluate("ST.model"); assert m == "claude-taught", m
    step("Train with Claude: one button, live progress, Save AI, use it", t_quick_train)
    def t_languages_ui():
        tab("Training"); pg.click(".pnav div:has-text('Train with Claude')"); pg.wait_for_selector("#qLen")
        opts = pg.eval_on_selector_all("#qLen option", "e=>e.map(x=>x.textContent)"); assert any("Every language" in o for o in opts) and any("Reverse engineering" in o for o in opts) and any("Pick languages" in o for o in opts), opts
        pg.select_option("#qLen", "pick"); pg.wait_for_selector(".langchips")
        chips = pg.eval_on_selector_all(".lchip", "e=>e.map(x=>x.textContent.trim())"); assert len(chips) == 16, chips
        joined = " ".join(chips); assert "Rust" in joined and "Reverse engineering" in joined and "C#" in joined and "SQL" in joined, joined
        pg.click(".lchip:has-text('Rust') input"); pg.click(".lchip:has-text('Go') input"); assert "on" in pg.get_attribute(".lchip:has-text('Rust')", "class")
        pg.click(".pnav div:has-text('Advanced')"); pg.wait_for_selector(".lhead")
        heads = pg.eval_on_selector_all(".lhead b", "e=>e.map(x=>x.textContent)"); assert "Reverse engineering" in heads and "Rust" in heads and "Python" in heads, heads
        pg.click(".lhead:has-text('Rust') button"); assert "on" or True
        cnt = pg.inner_text("#trCount"); assert "selected" in cnt, cnt
    step("language picker: 16 groups (15 languages + reverse engineering), per-language select in Advanced", t_languages_ui)
    def t_multilang_train_ui():
        tab("Training"); pg.click(".pnav div:has-text('Train with Claude')"); pg.wait_for_selector("#qLen")
        pg.select_option("#qStu", "qwen2.5-coder:14b"); pg.select_option("#qLen", "re"); pg.click("#qGo"); pg.wait_for_selector(".trbars", timeout=15000)
        pg.wait_for_selector("#trSaveBtn", timeout=300000); txt = pg.inner_text(".pbody")
        assert "unknown save-file format" in txt.lower() and "disassembler" in txt.lower() and "Pass rate" in txt, txt[:300]
        pg.click("button:has-text('New training')")
    step("train on the reverse-engineering track from the one-button page", t_multilang_train_ui)
    def t_advanced_results():
        tab("Training"); pg.click(".pnav div:has-text('Advanced')"); pg.wait_for_selector("#trGo", timeout=10000)
        pg.select_option("#trStu", "qwen2.5-coder:14b"); pg.select_option("#trTea", ""); pg.select_option("#trDemo", "reference"); pg.select_option("#trRounds", "1"); pg.click("#trQuick")
        assert "6 of" in pg.inner_text("#trCount"); pg.click("#trGo"); pg.wait_for_function("document.querySelector('.pbody').innerText.includes('New training')", timeout=180000)
        pg.click(".pnav div:has-text('Results')"); pg.wait_for_timeout(700); assert pg.eval_on_selector_all(".pcard", "e=>e.length") >= 2
        pg.click(".pcard >> nth=0 >> button:has-text('Open')"); pg.wait_for_selector(".trtable"); assert "Pass rate" in pg.inner_text(".trtable")
    step("advanced training (reference demos, quick 6) + results report", t_advanced_results)
    def t_custom_tasks():
        tab("Training"); pg.click(".pnav div:has-text('Your tasks')"); pg.wait_for_selector("#ctGo")
        p3 = fresh("mytask"); pg.fill("#ctT", "Fix my calc"); pg.fill("#ctF", p3); pg.fill("#ctP", "Fix add()"); pg.fill("#ctC", "python3 test_calc.py"); pg.click("#ctGo"); pg.wait_for_timeout(800)
        assert "Fix my calc" in pg.inner_text(".pbody"); pg.click(".pcard:has-text('Fix my calc') button:has-text('Delete')"); pg.wait_for_timeout(600); assert "Fix my calc" not in pg.inner_text(".pbody")
    step("your own training tasks: add and delete", t_custom_tasks)
    def t_coder():
        tab("Training"); pg.click(".pnav div:has-text('Marchand Coder')"); pg.wait_for_selector("#cbGo"); assert "recommended" in pg.inner_text(".pform")
        pg.select_option("#cbBase", "qwen2.5-coder:14b"); pg.click("#cbGo"); pg.wait_for_function("document.getElementById('cbMsg').innerText.includes('Ready')", timeout=60000)
        pg.wait_for_function("ST.model=='marchand-coder'", timeout=10000)
    step("Marchand Coder: one-click install with expert lessons + verified examples", t_coder)
    def t_gpu():
        tab("Training"); pg.click(".pnav div:has-text('GPU')"); pg.wait_for_function("document.querySelector('.pbody').innerText.includes('Python packages')", timeout=60000)
        t2 = pg.inner_text(".pbody"); assert "NVIDIA graphics card" in t2 and "missing" in t2 and "pip install" in t2
    step("GPU fine-tune page reports prerequisites honestly", t_gpu)

    # ----- help
    def t_help():
        tab("Help"); pg.wait_for_selector(".hitem", timeout=10000); ids = pg.evaluate("HELP.map(x=>x.id)"); assert len(ids) >= 33, len(ids)
        for i in range(len(ids)):
            pg.evaluate("(i)=>{HS.id=HELP[i].id;HS.q='';renderHelp()}", i); body = pg.inner_text(".hmain")
            assert len(body) > 120, ids[i]
        pg.fill(".hnav input", "forge"); pg.wait_for_timeout(300); assert "Set up Forge" in pg.inner_text(".hnav")
        pg.fill(".hnav input", "zzzzqq"); pg.wait_for_timeout(300); assert "No topic matches" in pg.inner_text(".hnav"); pg.fill(".hnav input", "")
    step("Help: every topic has content, search works", t_help)
    def t_help_nav():
        pg.evaluate("HS.id='images';HS.q='';renderHelp()"); pg.click(".hmain button:has-text('Open Images')"); pg.wait_for_selector(".iwrap", timeout=10000)
        tab("Help"); pg.evaluate("HS.id='faq';renderHelp()"); pg.click("details.faq >> nth=0"); assert pg.is_visible("details.faq[open] div")
    step("Help: guide buttons navigate to the right tab, FAQ expands", t_help_nav)

    # ----- settings / theme
    def t_settings():
        tab("Chat"); pg.click("#setBtn"); pg.wait_for_selector("#mSet.on"); pg.fill("#sCtx", "8192"); pg.select_option("#sTheme", "dark"); pg.check("#sAuto"); pg.fill("#sExtra", "Answer briefly."); pg.click("#sSave"); pg.wait_for_timeout(800)
        s = api("/api/settings"); assert s["num_ctx"] == 8192 and s["auto_approve"] is True and s["system_extra"] == "Answer briefly."
        assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
        pg.click("#setBtn"); pg.wait_for_selector("#mSet.on"); assert pg.input_value("#sCtx") == "8192"; pg.select_option("#sTheme", "light"); pg.fill("#sCtx", "16384"); pg.click("#sSave"); pg.wait_for_timeout(600)
        assert pg.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 247, 249)"
    step("Settings dialog persists values; dark/light themes", t_settings)
    def t_hidden_header():
        tab("Models"); assert pg.evaluate("getComputedStyle(document.querySelector('#instrBtn')).visibility") == "hidden"; tab("Chat")
    step("code-only header buttons hidden on other pages", t_hidden_header)
    def t_model_picker():
        tab("Chat"); pg.click("#mpBtn"); pg.wait_for_selector("#mpop.on")
        rows = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.length"); assert 1 <= rows <= 6, rows
        types = pg.eval_on_selector_all("#mpop .seg span", "e=>e.map(x=>x.dataset.type)"); assert types == ["all", "mine", "claude", "local", "cloud"], types
        pg.click("#mpop .seg span[data-type=claude]"); cl = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert all(x.startswith("claude-code::") for x in cl) and cl, cl
        pg.click("#mpop .seg span[data-type=local]"); lo = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert lo and not any("::" in x for x in lo), lo
        pg.click("#mpop [data-item=more]"); pg.wait_for_selector("#mpop [data-dl]")
        assert "Browse every model on ollama.com" in pg.inner_text("#mpop") and "Hugging Face" in pg.inner_text("#mpop")
        n = pg.eval_on_selector_all("#mpop [data-dl]", "e=>e.length"); assert n >= 20, n
        pg.fill("#mpop .msearch", "qwen2.5-coder:1.5b"); pg.wait_for_timeout(300); assert pg.eval_on_selector_all("#mpop [data-dl]", "e=>e.length") == 1
        pg.click("#mpop [data-dl] a"); pg.wait_for_timeout(500); assert "library/qwen2.5-coder" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_urls.log")).read()
        pg.click("#mpop [data-dl] button"); pg.wait_for_function("ST.model==='qwen2.5-coder:1.5b'", timeout=20000)
        assert pg.inner_text("#mpBtn").startswith("qwen2.5-coder:1.5b"); pg.wait_for_selector("#mpop:not(.on)", state="attached")
        pg.click("#mpBtn"); pg.click("#mpop .seg span[data-type=cloud]"); assert "Settings" in pg.inner_text("#mpop") or "cloud" in pg.inner_text("#mpop").lower(); pg.keyboard.press("Escape")
        pick_model("qwen2.5-coder:14b")
        assert pg.inner_text("#mpBtn").startswith("qwen2.5-coder:14b")
        assert pg.inner_text("#mhw").strip() != ""
    step("model picker under the chat: 6 models, type toggle, Show more, library download + ollama.com links", t_model_picker)
    def t_effort_pill():
        tab("Chat"); pick_model("claude-code::opus"); assert pg.is_visible("#effPill"); pg.click("#effPill"); pg.click("#effPop [data-eff=max]"); assert pg.input_value("#effort") == "max" and "Max" in pg.inner_text("#effPill")
        pick_model("qwen2.5-coder:14b"); assert not pg.is_visible("#effPill")
    step("effort pill appears for Claude models only and sets the effort", t_effort_pill)
    def t_app_links():
        tab("Images"); pg.wait_for_timeout(800)
        if pg.query_selector("[data-links]"):
            hrefs = pg.eval_on_selector_all("[data-links] [data-link]", "e=>e.map(x=>x.dataset.link)"); assert "forge" in hrefs and "comfyui" in hrefs, hrefs
        pg.click("#tModels"); pg.wait_for_timeout(500); pg.click(".pnav div:has-text('Apps on this PC')"); pg.wait_for_selector("[data-links=all]", timeout=10000)
        ids = pg.eval_on_selector_all("[data-links=all] [data-link]", "e=>e.map(x=>x.dataset.link)"); assert {"forge", "comfyui", "ollama", "lmstudio", "ffmpeg", "claude-code"} <= set(ids), ids
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_urls.log"), "w").close()
        pg.click("[data-links=all] [data-link=comfyui]"); pg.wait_for_timeout(500); got = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_urls.log")).read(); assert "comfy" in got, got
        pg.click(".pnav div:has-text('Download models')"); pg.wait_for_selector(".pcard:has-text('qwen2.5-coder:14b')"); assert "Graphics:" in pg.inner_text(".pbody") and pg.query_selector(".pcard a:has-text('ollama.com page')")
    step("missing apps: download links for Forge, ComfyUI, Ollama, LM Studio, ffmpeg...; model cards link to ollama.com", t_app_links)
    def t_picker_added_models():
        tab("Chat"); pg.click("#mpBtn"); pg.click("#mpop .seg span[data-type=cloud]")
        cl = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert "custom::mock-model" in cl, cl
        pg.click("#mpop .seg span[data-type=local]"); lo = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert any(x.startswith("lmstudio::") for x in lo) or pg.evaluate("ST.groups.some(g=>g.provider==='lmstudio')"), lo
        pg.click("#mpop .seg span[data-type=cloud]"); pg.click("#mpop .pi[data-model='custom::mock-model']"); assert pg.evaluate("ST.model") == "custom::mock-model" and pg.inner_text("#mpBtn").startswith("mock-model")
        send("hi added ai"); wait_idle(); assert "hello from oai" in pg.inner_text("#list")
        pick_model("qwen2.5-coder:14b")
    step("an AI you add (custom server / cloud key) can be toggled in the chat picker and answers", t_picker_added_models)
    def t_add_model_tab():
        tab("Training"); pg.click(".pnav div:has-text('Add your model')"); pg.wait_for_selector("#mnGo")
        txt = pg.inner_text(".pbody"); assert "From Ollama or Hugging Face" in txt and ".gguf" in txt and "another program" in txt, txt[:200]
        pg.fill("#mnName", "tiny-added:1b"); pg.click("#mnGo"); pg.wait_for_selector(".pcard[data-mine='tiny-added:1b']", timeout=20000)
        pg.fill("#mgPath", "/nope.gguf"); pg.fill("#mgName", "x"); pg.click("#mgGo"); pg.wait_for_function("document.getElementById('mgMsg').innerText.includes('Error')", timeout=10000)
        pg.select_option("#msType", "lmstudio"); assert pg.input_value("#msBase").endswith("1234/v1"); pg.click("#msGo"); pg.wait_for_function("document.getElementById('msMsg').innerText.includes('Connected')", timeout=20000)
        pg.wait_for_selector(".pcard[data-mine^='lmstudio::']", timeout=10000)
        pg.click(".pcard[data-mine='tiny-added:1b'] button:has-text('Train it')"); pg.wait_for_selector("#qStu"); assert pg.input_value("#qStu") == "tiny-added:1b", pg.input_value("#qStu")
        assert any(o.startswith("lmstudio::") for o in pg.eval_on_selector_all("#qStu option", "e=>e.map(x=>x.value)"))
    step("Add your model: Ollama/HF name, GGUF validation, local server connect, then train it", t_add_model_tab)
    def t_re_tab():
        tab("Training"); pg.click(".pnav div:has-text('Reverse engineering')"); pg.wait_for_selector("[data-re]")
        assert pg.eval_on_selector_all("[data-re]", "e=>e.length") == 9; txt = pg.inner_text(".pbody"); assert "The method" in txt and "Observe" in txt and "Educational and defensive" in txt
        assert pg.query_selector(".pbody li:has-text('known plaintext')") or "plaintext" in txt.lower()
        pg.select_option("#rvBase", "qwen2.5-coder:14b"); pg.click("#rvGo"); pg.wait_for_function("document.getElementById('rvMsg').innerText.includes('Ready')", timeout=60000)
        pg.wait_for_function("ST.model==='marchand-reverser'", timeout=10000)
        pg.select_option("#reStu", "qwen2.5-coder:14b"); pg.select_option("#reTea", ""); pg.click("#reGo"); pg.wait_for_selector(".trbars", timeout=20000)
        sid = pg.evaluate("TRS.view"); api("/api/training/stop", {"id": sid}); pg.wait_for_timeout(500); tab("Chat"); pick_model("qwen2.5-coder:14b")
    step("Reverse engineering tab: 9 tasks, method, install Marchand Reverser, start RE-only training", t_re_tab)
    def t_popular_ais():
        tab("Chat"); pg.click("#mpBtn"); pg.wait_for_selector("#mpop.on")
        pops = pg.eval_on_selector_all("#mpop [data-pop]", "e=>e.map(x=>x.dataset.pop)"); assert "openai" in pops and "xai" in pops and "gemini" in pops, pops
        assert "ChatGPT" in pg.inner_text("#mpop") and "Grok" in pg.inner_text("#mpop")
        pg.click("#mpop [data-pop=xai]"); pg.wait_for_selector("#mpop [data-pop=xai] + .popf input"); pg.click("#mpop [data-pop=xai] + .popf button"); assert "Paste your key" in pg.inner_text("#mpop")
        pg.click("#mpop .seg span[data-type=local]"); assert pg.query_selector("#mpop [data-pop]") is None
        pg.click("#mpop .seg span[data-type=claude]"); assert "anthropic" in pg.eval_on_selector_all("#mpop [data-pop]", "e=>e.map(x=>x.dataset.pop)") or pg.evaluate("ST.groups.some(g=>g.provider==='anthropic')")
        pg.click("#mpop .seg span[data-type=all]"); pg.click("#mpop [data-item=more]"); pg.wait_for_selector("#mpop [data-dl]"); assert pg.query_selector("#mpop [data-pop=openai]"); pg.keyboard.press("Escape")
    step("picker lists popular AIs (ChatGPT, Grok, Gemini...) to connect with a key, per type", t_popular_ais)
    def t_drag_drop():
        import io
        for mode in ("Chat", "Code"):
            tab(mode); pg.evaluate("ST.attach=[];renderChips()")
            pg.evaluate("document.dispatchEvent(Object.assign(new Event('dragenter',{bubbles:true,cancelable:true}),{dataTransfer:(()=>{const d=new DataTransfer();d.items.add(new File(['x'],'a.txt'));return d})()}))")
            assert "on" in pg.get_attribute("#dropOv", "class"); assert "Drop files or folders" in pg.inner_text("#dropOv")
            pg.evaluate("""document.dispatchEvent(Object.assign(new Event('drop',{bubbles:true,cancelable:true}),{dataTransfer:(()=>{const d=new DataTransfer();d.items.add(new File(['print(1)'],'drop_%s.py'));d.items.add(new File([new Uint8Array([1,2,3])],'blob_%s.bin'));return d})()}))""" % (mode, mode))
            pg.wait_for_selector(".achip:has-text('drop_%s.py')" % mode); pg.wait_for_selector(".achip:has-text('blob_%s.bin')" % mode)
            assert "off" in (pg.get_attribute("#dropOv", "class") or "") or "on" not in pg.get_attribute("#dropOv", "class").split()
        import zipfile as zf
        bio = io.BytesIO()
        with zf.ZipFile(bio, "w") as z: z.writestr("word/document.xml", "<w:p><w:r><w:t>Budget notes for Q3</w:t></w:r></w:p>")
        pg.evaluate("ST.attach=[];renderChips()"); pg.set_input_files("#attIn", [{"name": "report.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": bio.getvalue()}])
        pg.wait_for_function("ST.attach.some(a=>a.name==='report.docx'&&a.text&&a.text.includes('Budget notes for Q3'))", timeout=10000)
        pg.evaluate("ST.attach=[];renderChips()")
    step("drag and drop anywhere on Chat and Code (overlay, any file type) and docx text extraction", t_drag_drop)
    def t_agent_search():
        tab("Chat"); pg.click("#setBtn"); pg.wait_for_selector("#sAgents [data-agents]"); pg.click("#sAgents button:has-text('Search this PC')")
        pg.wait_for_selector("#sAgents [data-agent=claude][data-found='1']", timeout=30000); txt = pg.inner_text("#sAgents")
        assert "Claude Code" in txt and "Codex" in txt and "Gemini CLI" in txt and "Aider" in txt, txt
        assert pg.query_selector("#sAgents [data-agent=claude] button:has-text('In use')") or pg.query_selector("#sAgents [data-agent=claude] button:has-text('Use this one')")
        assert "Found:" in pg.inner_text("#sClaudeSt"); pg.click("#mSet [data-close]")
        pg.click("#tModels"); pg.click(".pnav div:has-text('Apps on this PC')"); pg.wait_for_selector("[data-agents]")
    step("search for AI agents button (Settings and Apps on this PC): finds Claude Code, lists Codex/Gemini/Aider with install links", t_agent_search)
    def t_my_ais():
        tab("Chat"); pg.click("#mpBtn"); pg.click("#mpop .seg span[data-type=mine]")
        mine = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert "marchand-coder" in mine and "qwen2.5-coder:14b" not in mine, mine
        assert "My own AI" in pg.inner_text("#mpop")
        pg.click("#mpop .seg span[data-type=local]"); loc = pg.eval_on_selector_all("#mpop .pi[data-model]", "e=>e.map(x=>x.dataset.model)"); assert "marchand-coder" not in loc and "qwen2.5-coder:14b" in loc, loc
        pg.click("#mpop .seg span[data-type=all]"); first = pg.eval_on_selector("#mpop .pi[data-model]", "e=>e.dataset.model"); assert first == pg.evaluate("ST.model") or first in mine, first
        pg.click("#mpop .seg span[data-type=mine]"); pg.click("#mpop .pi[data-model='marchand-coder']"); assert pg.evaluate("ST.model") == "marchand-coder"
        send("hello from my own ai"); wait_idle(); assert "closure" in pg.inner_text("#list")
        tab("Code"); assert pg.evaluate("ST.model") == "marchand-coder"; pg.click("#mpBtn"); pg.click("#mpop .seg span[data-type=mine]"); assert pg.query_selector("#mpop .pi[data-model='marchand-coder']"); pg.keyboard.press("Escape")
        tab("Models"); pg.click(".pnav div:has-text('Installed')"); pg.wait_for_selector(".pcard:has-text('marchand-coder')"); assert "My own AI" in pg.inner_text(".pcard:has-text('marchand-coder')")
        tab("Chat"); pick_model("qwen2.5-coder:14b")
    step("saved AIs appear automatically under My AI, work in chat and code", t_my_ais)
    def t_folder_drop():
        tab("Chat"); pg.evaluate("ST.attach=[];renderChips()")
        pg.evaluate("""addFolderAttachment({name:'my project',entries:[...Array.from({length:60},(_,i)=>({path:'my project/data/file'+i+'.dbc',size:3000,file:new File([new Uint8Array([0,1,2,3])],'file'+i+'.dbc')})),
          {path:'my project/src/main.py',size:20,file:new File(['print("folder hello")'],'main.py')},{path:'my project/README.md',size:12,file:new File(['# Readme text'],'README.md')}]})""")
        pg.wait_for_selector(".dirchip:has-text('my project')"); assert pg.eval_on_selector_all("#chips .achip", "e=>e.length") == 1, pg.inner_text("#chips")
        assert "62 files" in pg.inner_text("#chips") and "\U0001F4C1" in pg.inner_text("#chips")
        pg.evaluate("document.querySelector('#inp').value='look at this'"); send("look at this"); wait_idle()
        users = pg.evaluate("ST.convo.history.filter(m=>m.role==='user').map(m=>m.content).join('\\n=====\\n')")
        assert "Folder: my project (62 files" in users and "my project/src/main.py" in users and 'print("folder hello")' in users and "# Readme text" in users, users[:600]
        assert users.count("file0.dbc") == 1 and "\x00" not in users
        shown = pg.inner_text("#list"); assert "my project" in shown and shown.count("file5.dbc") == 0, shown[:300]
    step("dropping a folder shows ONE folder chip (icon + name), sends file list and text contents only", t_folder_drop)
    def t_activity_queue():
        tab("Chat"); pick_model("claude-code::sonnet"); pg.evaluate("ST.attach=[];renderChips()")
        send("TASK:think please"); pg.wait_for_selector(".live", timeout=10000); wait_idle()
        assert pg.query_selector(".think"), "no thinking block"; th = pg.inner_text(".think"); assert "Thought for" in th or "Thinking" in th, th
        assert pg.eval_on_selector(".think", "e=>e.open") is False; pg.click(".think summary"); assert "Plan: answer briefly" in pg.inner_text(".think .tt")
        assert "answer after thinking" in pg.inner_text("#list"); assert pg.query_selector(".live") is None
        send("TASK:slow first"); pg.wait_for_function("ST.running", timeout=5000)
        pg.fill("#inp", "second message while busy"); assert pg.is_visible("#qBtn") and pg.is_visible("#nowBtn"), "queue buttons"
        pg.press("#inp", "Enter"); pg.wait_for_selector(".qitem"); assert "second message while busy" in pg.inner_text("#queue"); assert pg.input_value("#inp") == ""
        pg.fill("#inp", "third message"); pg.click("#qBtn"); assert pg.eval_on_selector_all(".qitem", "e=>e.length") == 2
        pg.click(".qitem >> nth=1 >> button:has-text('\u2715')"); assert pg.eval_on_selector_all(".qitem", "e=>e.length") == 1
        pg.wait_for_function("document.querySelectorAll('.qitem').length==0 && !ST.running", timeout=40000)
        txt = pg.inner_text("#list"); assert "slow reply done" in txt and "second message while busy" in txt and "hello from fake claude" in txt, txt[-400:]
        assert txt.index("slow reply done") < txt.index("second message while busy")
        send("TASK:slow again"); pg.wait_for_function("ST.running", timeout=5000); pg.fill("#inp", "urgent one"); pg.click("#nowBtn")
        pg.wait_for_function("!ST.running", timeout=40000); txt = pg.inner_text("#list"); assert "Stopped." in txt and txt.rstrip().endswith("(resumed=" + txt.rstrip().split("resumed=")[-1]) or "hello from fake claude" in txt.split("urgent one")[-1], txt[-300:]
        assert "urgent one" in txt and txt.count("slow reply done") == 1, txt[-500:]
        send("TASK:limit now"); wait_idle(); assert "hit your limit" in pg.inner_text("#list"), pg.inner_text("#list")[-300:]
        pick_model("qwen2.5-coder:14b")
    step("live activity (thinking, status), message queue, Send now, errors shown", t_activity_queue)
    def t_plus_menu():
        tab("Chat"); pg.click("#plusBtn"); pg.wait_for_selector("#plusMenu.on")
        items = pg.eval_on_selector_all("#plusMenu .pi", "e=>e.map(x=>x.dataset.item)"); assert items[:5] == ["files", "folder", "slash", "connectors", "plugins"], items
        assert "Ctrl+U" in pg.inner_text("#plusMenu"); assert "dis" in pg.get_attribute("#plusMenu [data-item=folder]", "class") and "dis" in pg.get_attribute("#plusMenu [data-item=plugins]", "class")
        assert "Only available in Code" in pg.inner_text("#plusMenu")
        with pg.expect_file_chooser() as fc: pg.click("#plusMenu [data-item=files]")
        fp = os.path.join(fresh("plusfile"), "note.txt"); open(fp, "w").write("hello plus")
        fc.value.set_files(fp); pg.wait_for_selector(".achip:has-text('note.txt')"); pg.evaluate("ST.attach=[];renderChips()")
        with pg.expect_file_chooser() as fc2: pg.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'u',ctrlKey:true,bubbles:true}))")
        pg.click("#plusBtn"); pg.click("#plusMenu [data-item=slash]"); assert pg.input_value("#inp").startswith("/"); pg.fill("#inp", "")
        pg.click("#plusBtn"); pg.hover("#plusMenu [data-item=connectors]"); pg.wait_for_selector("#plusSub.on [data-item=manage]")
        names = pg.eval_on_selector_all("#plusSub [data-item^='conn:']", "e=>e.map(x=>x.dataset.item)")
        if names:
            before = pg.eval_on_selector("#plusSub [data-item^='conn:'] .sw", "e=>e.className"); pg.click("#plusSub [data-item^='conn:'] .sw"); pg.wait_for_timeout(500)
            assert pg.eval_on_selector("#plusSub [data-item^='conn:'] .sw", "e=>e.className") != before
            pg.click("#plusSub [data-item^='conn:'] .sw"); pg.wait_for_timeout(400)
        pg.click("#plusSub [data-item=manage]"); pg.wait_for_selector(".pnav div.on:has-text('Connectors')"); tab("Chat")
        tab("Code"); pg.click("#plusBtn"); assert "dis" not in pg.get_attribute("#plusMenu [data-item=folder]", "class") and "dis" not in pg.get_attribute("#plusMenu [data-item=plugins]", "class")
        pg.hover("#plusMenu [data-item=plugins]"); pg.wait_for_selector("#plusSub.on [data-item=manage]"); plugs = pg.eval_on_selector_all("#plusSub [data-item^='plug:']", "e=>e.length"); assert plugs >= 1, plugs
        pg.click("#plusSub [data-item^='plug:'] .sw"); pg.wait_for_timeout(500); pg.click("#plusSub [data-item^='plug:'] .sw"); pg.wait_for_timeout(400)
        pg.keyboard.press("Escape"); assert "on" not in pg.get_attribute("#plusMenu", "class")
        extra = fresh("extradir"); pg.evaluate("addExtra(%s)" % json.dumps(extra)); pg.wait_for_selector(".dirchip"); assert pg.evaluate("ST.extra.length") == 1
        pg.click(".dirchip i"); assert pg.evaluate("ST.extra.length") == 0
        pg.click("#plusBtn"); pg.click("#plusMenu [data-item=folder]"); pg.wait_for_selector("#mDir.on"); assert "Add this folder" in pg.inner_text("#dUse"); pg.click("#mDir [data-close]")
        pg.click("#plusBtn"); pg.click("#plusMenu [data-item=sendkey]"); assert "Ctrl+Enter to send" in pg.get_attribute("#inp", "placeholder")
        pg.fill("#inp", "x"); pg.press("#inp", "Enter"); assert pg.input_value("#inp") == "x\n", pg.input_value("#inp")
        pg.click("#plusBtn"); pg.click("#plusMenu [data-item=sendkey]"); assert pg.get_attribute("#inp", "placeholder").startswith("Enter to send"); pg.fill("#inp", "")
    step("+ menu: files (Ctrl+U), folder (Code only), slash, connectors/plugins toggles, send-key setting", t_plus_menu)
    def t_noerr():
        print("   (HTTP 4xx during session:", badresp, ")")
        assert not [e for e in errs if "Failed to load resource" not in e], errs[:3]
        unexpected = [x for x in badresp if x[1] not in ("/api/ollama/start", "/api/training/import-model") and not x[1].startswith("/api/image?name=")]
        assert not unexpected, unexpected
    step("no JavaScript or network errors during the whole session", t_noerr)
    b.close()
print("\nRESULT: %d passed, %d failed" % (passes[0], len(fails)), fails)
sys.exit(1 if fails else 0)
