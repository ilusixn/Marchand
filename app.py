#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
ICON = HERE / "assets" / "icon.ico"
DATA.mkdir(parents=True, exist_ok=True)
if sys.stdout is None or sys.stderr is None:
    log = open(DATA / "app.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log
sys.path.insert(0, str(HERE))


def report_failure(text):
    try:
        with open(DATA / "app.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Marchand could not start.\n\n%s\n\nDetails: %s" % (text[-600:], DATA / "app.log"), "Marchand Studio", 0x10)
        except Exception:
            pass
    else:
        print(text, file=sys.stderr)


try:
    import server
except Exception:
    import traceback
    report_failure("Loading the program failed:\n" + traceback.format_exc())
    raise SystemExit(1)

TITLE = "Marchand Studio"
SIZE = (1360, 880)
BG = "#1b1d22"


def state():
    try:
        return json.loads((DATA / "app.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(s):
    (DATA / "app.json").write_text(json.dumps(s))


def report_log(text):
    print(text, flush=True)
    try:
        with open(DATA / "app.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def ensure_pywebview():
    try:
        import webview
        return webview
    except ImportError:
        return None


class Api:
    window = None

    def open_url(self, url):
        if url.startswith("https://buymeacoffee.com/"):
            webbrowser.open(url)

    def pick_folder(self, start=""):
        import webview
        res = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=start or "")
        return res[0] if res else ""


def run_webview(webview, url, srv):
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Marchand.Desktop")
        except Exception:
            pass
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass
    api = Api()
    started = time.time()
    win = webview.create_window(TITLE, url, js_api=api, width=SIZE[0], height=SIZE[1], min_size=(900, 600), background_color=BG)
    api.window = win

    def after():
        try:
            import clr
            clr.AddReference("System.Drawing")
            from System.Drawing import Icon
            win.native.Icon = Icon(str(ICON))
        except Exception:
            pass
    webview.start(after, icon=str(HERE / "assets" / "icon.png"))
    if time.time() - started < 4:
        raise RuntimeError("the window closed immediately")


def find_chromium():
    env = os.environ.get("MARCHAND_BROWSER")
    if env and Path(env).exists():
        return env
    cands = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe",
                          Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe"]
    elif sys.platform == "darwin":
        cands += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                  Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
    else:
        for n in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser", "brave-browser"):
            p = shutil.which(n)
            if p:
                cands.append(Path(p))
    for c in cands:
        if Path(c).exists():
            return str(c)
    return None


def app_window_args(exe, url):
    profile = DATA / "app-profile"
    args = [exe, "--app=" + url, "--user-data-dir=" + str(profile), "--window-size=%d,%d" % SIZE, "--no-first-run",
            "--no-default-browser-check", "--disable-features=Translate"]
    return args + os.environ.get("MARCHAND_BROWSER_ARGS", "").split()


def open_app_window(url):
    exe = find_chromium()
    if exe:
        return subprocess.Popen(app_window_args(exe, url))
    webbrowser.open(url)
    return None


IS_WIN = sys.platform.startswith("win")
KEEP = []


def single_instance():
    if not IS_WIN:
        return True
    import ctypes
    KEEP.append(ctypes.windll.kernel32.CreateMutexW(None, False, "Marchand.Studio.Single"))
    return ctypes.windll.kernel32.GetLastError() != 183


def tray_window():
    import ctypes
    return ctypes.windll.user32.FindWindowW("MarchandStudioTray", None)


def replace_old_instance():
    import ctypes
    h = tray_window()
    if h:
        ctypes.windll.user32.PostMessageW(h, 0x0111, 1003, 0)
    deadline = time.time() + 12
    while tray_window() and time.time() < deadline:
        time.sleep(0.3)
    time.sleep(1.0)
    while KEEP:
        ctypes.windll.kernel32.CloseHandle(KEEP.pop())
    return single_instance()


def running_info():
    try:
        return json.loads((DATA / "running.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    tray_on = IS_WIN and not os.environ.get("MARCHAND_NO_TRAY")
    if tray_on and not single_instance():
        info = running_info()
        if info.get("build") == server.BUILD and info.get("url"):
            open_app_window(info["url"])
            return
        report_log("An older Marchand (build %s) is still running; replacing it with build %s." % (info.get("build") or "unknown", server.BUILD))
        if not replace_old_instance():
            try:
                open_app_window((DATA / "url.txt").read_text().strip())
            except OSError:
                pass
            return
    srv = server.make_server(8765)
    url = "http://127.0.0.1:%d" % server.PORT["n"]
    (DATA / "url.txt").write_text(url)
    (DATA / "running.json").write_text(json.dumps({"url": url, "build": server.BUILD}), encoding="utf-8")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("Marchand server on " + url, flush=True)
    quit_ev = threading.Event()
    win = [None]
    tray = None
    if tray_on:
        from tray import Tray

        def open_again():
            p = win[0]
            if p is None or p.poll() is not None:
                win[0] = open_app_window(url)

        tray = Tray(str(ICON), "Marchand Studio", open_again, lambda: webbrowser.open("https://buymeacoffee.com/ilusixne"), quit_ev.set)
        if not tray.start():
            report_log("The tray icon could not be created; closing the window will close Marchand.")
            tray = None
    shown = False
    if not os.environ.get("MARCHAND_BROWSER"):
        webview = ensure_pywebview()
        if webview:
            try:
                run_webview(webview, url, srv)
                shown = True
            except Exception as ex:
                report_log("Native window failed, using the browser instead: %s" % ex)
    if not shown:
        t0 = time.time()
        p = open_app_window(url)
        win[0] = p
        if p is not None and tray is None:
            p.wait()
            if time.time() - t0 < 5:
                report_log("The browser handed the window to another process; Marchand stays running.")
                threading.Event().wait()
        elif p is None and tray is None:
            report_log("No app window available; opening your browser. Marchand keeps running in the background until you close it from Task Manager.")
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    if tray is not None:
        quit_ev.wait()
        if win[0] is not None and win[0].poll() is None:
            win[0].terminate()
        tray.stop()
    srv.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        report_failure("Marchand crashed:\n" + traceback.format_exc())
        raise SystemExit(1)
