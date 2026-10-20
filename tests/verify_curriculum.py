import os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import curriculum, trainer

def run(task, solution):
    d = tempfile.mkdtemp()
    for n, c in {**task["files"], **task["tests"]}.items():
        os.makedirs(os.path.dirname(os.path.join(d, n)) or d, exist_ok=True)
        open(os.path.join(d, n), "w").write(trainer.render(c))
    if solution:
        for n, c in task["solution"].items():
            open(os.path.join(d, n), "w").write(trainer.render(c))
    t0 = time.time()
    r = subprocess.run(trainer.run_cmd(dict(task, builtin=True)), shell=True, cwd=d, capture_output=True, text=True, timeout=300)
    shutil.rmtree(d, ignore_errors=True)
    return r.returncode, (r.stdout + r.stderr), time.time() - t0

only = sys.argv[1:]
bad, skipped, done = [], [], 0
by_lang = {}
for t in curriculum.TASKS:
    if only and t["id"] not in only and t["lang"] not in only: continue
    ok, why = trainer.availability(t)
    if not ok:
        skipped.append((t["id"], why)); continue
    rc0, out0, s0 = run(t, False); rc1, out1, s1 = run(t, True)
    good = rc0 != 0 and rc1 == 0
    by_lang.setdefault(t["lang"], []).append(good)
    print("%-3s %-10s %-22s starter rc=%-3s solution rc=%-3s %.1fs/%.1fs" % ("OK" if good else "BAD", t["lang"], t["id"], rc0, rc1, s0, s1))
    if not good:
        bad.append(t["id"])
        if rc0 == 0: print("    starter unexpectedly PASSES")
        if rc1 != 0: print("    solution output:", out1[-500:].replace("\n", "\n      "))
    done += 1
print("\n%d tasks verified, %d bad, %d skipped %s" % (done, len(bad), len(skipped), skipped))
print("languages:", {k: "%d/%d" % (sum(v), len(v)) for k, v in by_lang.items()})
sys.exit(1 if bad else 0)
