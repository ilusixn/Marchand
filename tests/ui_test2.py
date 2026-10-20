import sys, json, os
from playwright.sync_api import sync_playwright
proj = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1360, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append("PAGEERR " + str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765"); pg.wait_for_timeout(1200)
    pg.screenshot(path="u1_home.png")
    # slash palette
    pg.click("#tCode"); pg.evaluate("ST.project=%s" % json.dumps(proj)); pg.fill("#inp", "/"); pg.wait_for_timeout(300)
    pg.screenshot(path="u2_slash.png")
    print("slash items:", pg.eval_on_selector_all("#slash div b", "e=>e.map(x=>x.textContent)"))
    pg.fill("#inp", "/commit-message"); pg.wait_for_timeout(200)
    print("expand:", pg.evaluate("expandSlash('/review src')")[:60])
    pg.fill("#inp", "")
    for tab, sec in (("#tPlug", None), ("#tModels", None), ("#tTeach", None), ("#tHelp", None)):
        pg.click(tab); pg.wait_for_timeout(900); pg.screenshot(path="u_%s.png" % tab[2:])
    # models subsections
    pg.click("#tModels")
    for name in ("Installed", "Cloud providers", "Ollama"):
        pg.click(".pnav div:has-text('%s')" % name); pg.wait_for_timeout(900); pg.screenshot(path="um_%s.png" % name.split()[0])
    # plugins subsections
    pg.click("#tPlug")
    for name in ("Discover", "Connectors (MCP)", "Claude Desktop", "Create"):
        pg.click(".pnav div:has-text('%s')" % name); pg.wait_for_timeout(900); pg.screenshot(path="up_%s.png" % name.split()[0])
    # teach subsections
    pg.click("#tTeach")
    for name in ("Lessons", "Examples and dataset", "Create your AI"):
        pg.click(".pnav div:has-text('%s')" % name); pg.wait_for_timeout(900); pg.screenshot(path="ut_%s.png" % name.split()[0])
    pg.click("#tHelp"); pg.wait_for_timeout(600)
    pg.fill(".hnav input", "teach"); pg.wait_for_timeout(300); pg.screenshot(path="uh_search.png")
    pg.fill(".hnav input", ""); pg.click(".hitem:has-text('Guide: teach your AI')"); pg.wait_for_timeout(300); pg.screenshot(path="uh_guide.png")
    pg.click(".hitem:has-text('Frequently asked')"); pg.wait_for_timeout(300); pg.click("details.faq >> nth=0"); pg.screenshot(path="uh_faq.png")
    pg.click(".hitem:has-text('Error messages')"); pg.wait_for_timeout(300); pg.screenshot(path="uh_err.png")
    pg.click("#tTeach"); pg.click(".pnav div:has-text('Create your AI')"); pg.wait_for_timeout(800); pg.screenshot(path="uh_create.png")
    # attach + agent run via mock ollama, then teach buttons
    pg.click("#tCode"); pg.wait_for_timeout(300)
    pg.set_input_files("#attIn", {"name": "notes.txt", "mimeType": "text/plain", "buffer": b"remember: be careful"})
    pg.wait_for_timeout(300)
    pg.fill("#inp", "fix the failing test"); pg.press("#inp", "Enter")
    for _ in range(30):
        pg.wait_for_timeout(600)
        if not pg.evaluate("ST.running"): break
    pg.wait_for_timeout(500)
    print("buttons:", pg.eval_on_selector_all(".retry, .msg button", "e=>e.map(x=>x.textContent.trim()).filter(x=>x)"))
    pg.screenshot(path="u9_code.png")
    pg.click("button:has-text('Retry')") if False else None
    print("ERRORS:", errs)
    b.close()
