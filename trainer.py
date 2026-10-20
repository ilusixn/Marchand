import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import curriculum
import engine
import ollama_mgr
import pack
import providers
import teacher

DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
TRAIN = DATA / "training"
SESSIONS = TRAIN / "sessions"
WS = TRAIN / "workspaces"
CUSTOM = TRAIN / "custom_tasks.json"
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", "target", ".next"}
LIVE = {}


def python_cmd():
    return '"%s"' % sys.executable if " " in sys.executable else sys.executable


_TFM = {}
_PROBES = {}


def dotnet_tfm():
    if "v" not in _TFM:
        try:
            out = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
            _TFM["v"] = "net%s.0" % out.split(".")[0] if out else "net8.0"
        except (OSError, subprocess.TimeoutExpired):
            _TFM["v"] = "net8.0"
    return _TFM["v"]


def render(text):
    return text.replace("{{TFM}}", dotnet_tfm()) if "{{TFM}}" in text else text


def exe_name(name):
    return name + ".exe" if os.name == "nt" else "./" + name


def run_cmd(task):
    cmd = task["test_cmd"]
    if task.get("builtin", True) and cmd.startswith("python "):
        cmd = python_cmd() + cmd[len("python"):]
    return re.sub(r"\{exe:(\w+)\}", lambda m: exe_name(m.group(1)), cmd)


def availability(task):
    missing = [r for r in task.get("requires") or [] if not shutil.which(r)]
    if missing:
        return False, "needs " + ", ".join(missing)
    probe = task.get("probe")
    if probe:
        if probe not in _PROBES:
            try:
                _PROBES[probe] = subprocess.run(probe, shell=True, capture_output=True, timeout=60).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                _PROBES[probe] = False
        if not _PROBES[probe]:
            return False, "toolchain not ready (%s)" % task["requires"][0] if task.get("requires") else "toolchain not ready"
    return True, ""


def custom_tasks():
    try:
        return json.loads(CUSTOM.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_custom(items):
    TRAIN.mkdir(parents=True, exist_ok=True)
    CUSTOM.write_text(json.dumps(items, indent=1), encoding="utf-8")


def add_custom(data):
    folder = Path(data.get("folder", "")).expanduser()
    if not folder.is_dir():
        raise ValueError("Folder not found: %s" % folder)
    if not data.get("prompt", "").strip() or not data.get("test_cmd", "").strip():
        raise ValueError("A task needs a description and a test command.")
    size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not (set(f.relative_to(folder).parts) & SKIP))
    if size > 50 * 2 ** 20:
        raise ValueError("That folder is larger than 50 MB (without .git/node_modules). Pick a smaller project.")
    t = {"id": "custom_" + uuid.uuid4().hex[:6], "title": data.get("title") or data["prompt"][:50], "topic": "your project", "level": 3,
         "prompt": data["prompt"].strip(), "folder": str(folder.resolve()), "test_cmd": data["test_cmd"].strip(), "builtin": False}
    items = custom_tasks()
    items.append(t)
    save_custom(items)
    return t


def all_tasks():
    out = []
    for t in curriculum.TASKS:
        ok, why = availability(t)
        out.append(dict(t, builtin=True, available=ok, why=why))
    for t in custom_tasks():
        out.append(dict(t, lang="custom", available=True, why=""))
    return out


def find_task(tid):
    return next((t for t in all_tasks() if t["id"] == tid), None)


def make_workspace(task, tag):
    ws = WS / tag / task["id"]
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    if task.get("builtin", True):
        for name, content in {**task["files"], **task["tests"]}.items():
            (ws / name).write_text(render(content), encoding="utf-8")
    else:
        src = Path(task["folder"])
        for f in src.rglob("*"):
            rel = f.relative_to(src)
            if set(rel.parts) & SKIP or not f.is_file():
                continue
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, ws / rel)
    return ws


def verify(ws, task):
    if task.get("builtin", True):
        for name, content in task["tests"].items():
            (ws / name).write_text(render(content), encoding="utf-8")
    try:
        r = subprocess.run(run_cmd(task), shell=True, cwd=ws, capture_output=True, text=True, errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        return False, "tests timed out after 180 seconds"
    return r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def task_prompt(task):
    return "%s\n\nRun the tests with: %s" % (task["prompt"], run_cmd(task))


def lessons_text(langs):
    return teacher.lessons_prompt(langs or ["general"], 2400)


def run_agent(settings, model, ws, task, emit, cancel, max_steps, use_lessons=True, persona=""):
    if providers.split_model(model)[0] == "claude-code":
        import claude_code
        try:
            hist = claude_code.run_agent_capture(providers.split_model(model)[1], settings.get("cc_effort") or "medium", ws, task_prompt(task), cancel,
                                                 emit, max_turns=max_steps, append=persona or None)
        except claude_code.Cancelled:
            raise engine.Cancelled()
        except Exception as ex:
            emit("  error: %s" % ex)
            return [{"role": "user", "content": task_prompt(task)}, {"role": "assistant", "content": "(run failed: %s)" % ex}], 0
        return hist, sum(1 for m in hist if m.get("tool_calls"))
    cfg = {"settings": settings, "host": settings["host"], "model": model, "num_ctx": int(settings.get("num_ctx", 16384)),
           "temperature": 0.2, "max_steps": max_steps, "critic": False, "task": task["prompt"]}
    lang = task.get("lang") or "python"
    extra = persona + ("\n\n" + lessons_text([lang, "general"]) if use_lessons else "")
    system = engine.build_system(ws, "code", cfg["num_ctx"], extra)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task_prompt(task)}]
    stats = {"tools": 0}

    def on(ev):
        if ev["type"] == "tool":
            stats["tools"] += 1
            a = ev.get("args") or {}
            detail = a.get("path") or a.get("command") or a.get("pattern") or "" if isinstance(a, dict) else ""
            emit("  %s %s" % (ev["name"], str(detail)[:80]))
    try:
        engine.run_code(cfg, messages, ws, on, cancel, lambda *x: True)
    except engine.Cancelled:
        raise
    except Exception as ex:
        emit("  error: %s" % providers.err_text(ex))
        messages.append({"role": "assistant", "content": "(run failed: %s)" % ex})
    return messages[1:], stats["tools"]


def numbered(text):
    return "\n".join("%d\t%s" % (i + 1, l) for i, l in enumerate(text.splitlines()))


def minimal_edit(old, new):
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(a=a, b=b)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    if not ops:
        return None
    i1, i2, j1, j2 = ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]
    while True:
        old_txt = "".join(a[i1:i2])
        if old_txt and old.count(old_txt) == 1:
            return old_txt, "".join(b[j1:j2])
        if i1 == 0 and i2 == len(a):
            return None
        i1, j1 = max(0, i1 - 1), max(0, j1 - 1)
        if i2 < len(a):
            i2, j2 = i2 + 1, j2 + 1


def reference_trace(task):
    ws = make_workspace(task, "reference")
    cmd = run_cmd(task)
    msgs = [{"role": "user", "content": task_prompt(task)}]

    def call(name, args, result, text=""):
        msgs.append({"role": "assistant", "content": text, "tool_calls": [{"function": {"name": name, "arguments": args}}]})
        msgs.append({"role": "tool", "tool_name": name, "content": result})
    r = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, errors="replace", timeout=180)
    call("run_command", {"command": cmd}, "exit code %d\n%s" % (r.returncode, (r.stdout + r.stderr)[-1200:]), "First I reproduce the failure.")
    for name in task["solution"]:
        cur = (ws / name).read_text(encoding="utf-8")
        call("read_file", {"path": name}, numbered(cur))
    for name, new in task["solution"].items():
        cur = (ws / name).read_text(encoding="utf-8")
        edit = minimal_edit(cur, new)
        if edit:
            call("edit_file", {"path": name, "old": edit[0], "new": edit[1]}, "edited %s" % name, "")
        else:
            call("write_file", {"path": name, "content": new}, "wrote %s (%d lines)" % (name, new.count("\n") + 1))
        (ws / name).write_text(render(new), encoding="utf-8")
    r = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, errors="replace", timeout=180)
    call("run_command", {"command": cmd}, "exit code %d\n%s" % (r.returncode, (r.stdout + r.stderr)[-600:]))
    files = ", ".join(task["solution"])
    call("finish", {"summary": "Fixed %s in %s. Verified with `%s`: all checks pass." % (task["title"].lower(), files, cmd)},
         "Fixed %s in %s. Verified with `%s`: all checks pass." % (task["title"].lower(), files, cmd))
    shutil.rmtree(ws, ignore_errors=True)
    return msgs, r.returncode == 0


def save_session(s):
    SESSIONS.mkdir(parents=True, exist_ok=True)
    (SESSIONS / (s["id"] + ".json")).write_text(json.dumps({k: v for k, v in s.items() if k != "_cancel"}, indent=1), encoding="utf-8")


def sessions():
    out = []
    if SESSIONS.is_dir():
        for f in SESSIONS.glob("*.json"):
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append({k: s.get(k) for k in ("id", "name", "status", "started", "finished", "config", "summary")})
    return sorted(out, key=lambda s: -(s.get("started") or 0))


def get_session(sid):
    if sid in LIVE:
        return {k: v for k, v in LIVE[sid].items() if k != "_cancel"}
    f = SESSIONS / (os.path.basename(sid) + ".json")
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def delete_session(sid):
    f = SESSIONS / (os.path.basename(sid) + ".json")
    if f.is_file():
        f.unlink()
    shutil.rmtree(WS / os.path.basename(sid), ignore_errors=True)


def running():
    return next((s for s in LIVE.values() if s["status"] == "running"), None)


def start(settings, cfg):
    if running():
        raise RuntimeError("A training session is already running. Stop it first.")
    if not cfg.get("student"):
        raise ValueError("Choose the student model (the one you want to train).")
    ids = cfg.get("tasks")
    pool = {t["id"]: t for t in all_tasks()}
    if not ids:
        ids = [i for i, t in pool.items() if t.get("available") and t.get("builtin")]
    tasks = [pool[i] for i in ids if i in pool]
    skipped = [t for t in tasks if not t.get("available", True)]
    tasks = [t for t in tasks if t.get("available", True)]
    if not tasks:
        need = sorted({t["why"] for t in skipped})
        raise ValueError("Choose at least one task." if not skipped else "None of the chosen tasks can run on this PC: %s. Install the missing tools or choose other languages." % "; ".join(need))
    demos = cfg.get("demos", "teacher" if cfg.get("teacher") else "reference")
    if demos == "teacher" and not cfg.get("teacher"):
        raise ValueError("Choose a teacher model, or use the built-in reference solutions.")
    sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    s = {"id": sid, "name": cfg.get("name") or "Training %s" % time.strftime("%d %b %H:%M"), "status": "running", "started": int(time.time()),
         "finished": None, "config": dict(cfg, tasks=[t["id"] for t in tasks], demos=demos), "rounds": [], "log": [], "current": {},
         "counters": {"student_runs": 0, "teacher_calls": 0, "examples": 0, "lessons": 0, "tokens_est": 0}, "summary": "", "_cancel": threading.Event()}
    for t in skipped:
        _log(s, "Skipped %s (%s): %s" % (t["title"], curriculum.LANG_NAMES.get(t.get("lang"), t.get("lang")), t["why"]))
    s["skipped"] = [{"task": t["id"], "title": t["title"], "why": t["why"]} for t in skipped]
    LIVE[sid] = s
    threading.Thread(target=_run, args=(settings, s, tasks), daemon=True).start()
    return sid


def stop(sid):
    s = LIVE.get(sid)
    if s:
        s["_cancel"].set()


def _log(s, text):
    s["log"].append(time.strftime("%H:%M:%S ") + text)
    s["log"] = s["log"][-400:]


def _est(history):
    return sum(len(m.get("content") or "") + len(json.dumps(m.get("tool_calls") or "")) for m in history) // 4


def _run(settings, s, tasks):
    cfg, cancel = s["config"], s["_cancel"]
    student, teach = cfg["student"], cfg.get("teacher") or ""
    rounds = max(1, min(5, int(cfg.get("rounds", 2))))
    max_steps = int(cfg.get("max_steps", 25))
    use_lessons = cfg.get("use_lessons", True)
    learn = cfg.get("learn", True)
    keep_good = cfg.get("keep_successes", True)
    persona = pack.PERSONA if cfg.get("persona", True) else ""
    try:
        for rnd in range(1, rounds + 1):
            results = []
            s["rounds"].append({"round": rnd, "results": results})
            _log(s, "Round %d of %d: %d tasks" % (rnd, rounds, len(tasks)))
            for t in tasks:
                if cancel.is_set():
                    raise engine.Cancelled()
                s["current"] = {"round": rnd, "task": t["id"], "title": t["title"], "phase": "student"}
                _log(s, "Student %s tries: %s" % (student, t["title"]))
                ws = make_workspace(t, "%s/r%d" % (s["id"], rnd))
                t0 = time.time()
                hist, ntools = run_agent(settings, student, ws, t, lambda m: _log(s, m), cancel, max_steps, use_lessons, persona)
                passed, out = verify(ws, t)
                s["counters"]["student_runs"] += 1
                r = {"task": t["id"], "title": t["title"], "lang": t.get("lang", "python"), "passed": passed, "tools": ntools, "seconds": round(time.time() - t0, 1),
                     "lessons": 0, "demo": None, "demo_passed": None}
                results.append(r)
                _log(s, "  -> %s" % ("PASSED" if passed else "FAILED: " + out.strip().splitlines()[-1][:160] if out.strip() else "FAILED"))
                if passed and keep_good:
                    teacher.save_example({"title": "[training] " + t["title"], "model": student, "mode": "code", "history": hist}, 4)
                    s["counters"]["examples"] += 1
                if not learn or rnd == rounds and cfg.get("final_round_is_test", True) and rounds > 1:
                    continue
                if not passed and teach:
                    s["current"]["phase"] = "teacher review"
                    review = hist + [{"role": "user", "content": "TEST RESULT: FAILED\n" + out[-800:]}]
                    try:
                        ev = teacher.evaluate(settings, teach, review, [t.get("lang") or "python", "general"])
                        r["lessons"] = ev.get("added", 0)
                        s["counters"]["lessons"] += r["lessons"]
                        s["counters"]["teacher_calls"] += 1
                        s["counters"]["tokens_est"] += _est(review) + 600
                        _log(s, "  teacher: %s/10 - %s (%d new lessons)" % (ev.get("score"), str(ev.get("verdict", ""))[:120], r["lessons"]))
                    except Exception as ex:
                        _log(s, "  teacher review failed: %s" % providers.err_text(ex))
                if passed:
                    continue
                mode = cfg["demos"]
                if mode in ("teacher", "both") and teach:
                    s["current"]["phase"] = "teacher demonstrates"
                    _log(s, "  teacher %s shows how" % teach)
                    ws2 = make_workspace(t, "%s/r%d-teacher" % (s["id"], rnd))
                    th, _ = run_agent(settings, teach, ws2, t, lambda m: _log(s, "  " + m), cancel, max_steps, False, teacher.TEACHER_DEMO)
                    s["counters"]["teacher_calls"] += 1
                    s["counters"]["tokens_est"] += _est(th)
                    ok2, _ = verify(ws2, t)
                    r["demo"], r["demo_passed"] = "teacher", ok2
                    if ok2:
                        teacher.save_example({"title": "[teacher] " + t["title"], "model": teach, "mode": "code", "history": th}, 5)
                        s["counters"]["examples"] += 1
                        _log(s, "  teacher solved it; saved as an example")
                    else:
                        _log(s, "  teacher did not solve it either")
                if (mode in ("reference", "both") or (mode == "teacher" and r["demo_passed"] is False)) and t.get("builtin", True):
                    th, ok3 = reference_trace(t)
                    if ok3:
                        teacher.save_example({"title": "[reference] " + t["title"], "model": "reference", "mode": "code", "history": th}, 5)
                        s["counters"]["examples"] += 1
                        r["demo"] = r["demo"] or "reference"
                        r["demo_passed"] = True
                        _log(s, "  saved the reference solution as an example")
            passed_n = sum(1 for r in results if r["passed"])
            _log(s, "Round %d: %d/%d passed" % (rnd, passed_n, len(results)))
        if teach and cfg.get("consolidate") and s["counters"]["lessons"]:
            s["current"] = {"phase": "teacher condenses lessons"}
            try:
                n = teacher.consolidate(settings, teach)
                s["counters"]["teacher_calls"] += 1
                _log(s, "Teacher condensed the lessons to %d rules" % n)
            except Exception as ex:
                _log(s, "Condensing lessons failed: %s" % providers.err_text(ex))
        save = cfg.get("save_as")
        if save and providers.split_model(student)[0] == "ollama":
            s["current"] = {"phase": "saving your AI"}
            _log(s, "Saving the trained AI as %s" % save)
            for _ in teacher.build_model(settings, providers.split_model(student)[1], save, ["general"] + sorted({t.get("lang", "python") for t in tasks}),
                                         {"persona": pack.PERSONA if cfg.get("persona", True) else "", "include_lessons": True, "examples": 3, "temperature": 0.2,
                                          "num_ctx": int(settings.get("num_ctx", 16384))}):
                pass
            teacher.save_ai({"name": save, "base": providers.split_model(student)[1], "persona": pack.PERSONA if cfg.get("persona", True) else "",
                             "include_lessons": True, "examples": 3, "temperature": 0.2, "num_ctx": int(settings.get("num_ctx", 16384)),
                             "created": int(time.time()), "lessons": len([l for l in teacher.lessons() if l.get("enabled", True)]),
                             "training": s["id"]})
            s["saved_ai"] = save
        s["status"] = "finished"
    except engine.Cancelled:
        s["status"] = "stopped"
        _log(s, "Stopped by you.")
    except Exception as ex:
        s["status"] = "error"
        _log(s, "Error: %s" % providers.err_text(ex))
    finally:
        rates = []
        for rd in s["rounds"]:
            if rd["results"]:
                rates.append("%d%%" % round(100 * sum(1 for r in rd["results"] if r["passed"]) / len(rd["results"])))
        s["summary"] = " -> ".join(rates)
        s["finished"] = int(time.time())
        s["current"] = {}
        save_session(s)
        LIVE.pop(s["id"], None)


def install_coder_pack(settings, base, name, emit, kind="coder"):
    re_only = kind == "reverser"
    persona = pack.PERSONA_RE if re_only else pack.PERSONA
    lessons = [(x, g) for x, g in pack.LESSONS if g in ("reverse", "general")] if re_only else pack.LESSONS
    added = teacher.add_lessons([{"text": x, "tags": [g]} for x, g in lessons], "marchand-pack")
    emit({"status": "Added %d expert lessons" % added, "pct": 10})
    have = {e["title"] for e in teacher.examples()}
    n = 0
    for tid in (pack.DEMO_RE if re_only else pack.DEMO_TASKS):
        t = dict(curriculum.get(tid), builtin=True)
        title = "[reference] " + t["title"]
        if title in have or not availability(t)[0]:
            continue
        hist, ok = reference_trace(t)
        if ok:
            teacher.save_example({"title": title, "model": "reference", "mode": "code", "history": hist}, 5)
            n += 1
    emit({"status": "Added %d verified worked examples" % n, "pct": 20})
    langs = ["reverse", "general"] if re_only else ["*"]
    for ev in teacher.build_model(settings, base, name, langs,
                                  {"persona": persona, "include_lessons": True, "examples": 3, "temperature": 0.2, "reverse": True, "lesson_chars": 5500,
                                   "num_ctx": int(settings.get("num_ctx", 16384))}):
        emit(dict(ev, pct=60))
    teacher.save_ai({"name": name, "base": base, "persona": persona, "include_lessons": True, "examples": 3, "temperature": 0.2,
                     "num_ctx": int(settings.get("num_ctx", 16384)), "created": int(time.time()),
                     "lessons": len([l for l in teacher.lessons() if l.get("enabled", True)]), "pack": "reverser" if re_only else True})
    emit({"status": ("Marchand Reverser" if re_only else "Marchand Coder") + " is ready", "pct": 100, "done": True, "name": name})


def recommend_base():
    return pack.best_base(ollama_mgr.catalog())
