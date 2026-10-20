from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.goto("http://127.0.0.1:8765"); pg.wait_for_timeout(1200)
    for tab in ("Chat", "Code", "Images", "Training", "Plugins", "Models", "Help"):
        pg.click("#t" + tab if tab != "Plugins" else "#tPlug"); pg.wait_for_timeout(300)
        vis = pg.is_visible("#bmc"); href = pg.get_attribute("#bmc", "href")
        print(tab, "visible:", vis, href)
    print("title:", pg.title(), "| brand:", pg.inner_text(".brand"))
    pg.screenshot(path="bmc.png", clip={"x": 0, "y": 0, "width": 700, "height": 200}); b.close()
