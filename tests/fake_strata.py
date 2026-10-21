#!/usr/bin/env python3
import sys
KNOWN = {"q2_0", "iq2_xs", "iq3_xxs", "iq3_s", "gyro-s", "gyro-m", "coder", "swift", "qwen36"}
a = sys.argv[1:]
if a[:1] == ["--version"]:
    print("strata 0.1.46"); sys.exit(0)
if a[:1] == ["launch"]:
    model = a[a.index("--model") + 1] if "--model" in a else ""
    if model not in KNOWN:
        sys.stderr.write("Unknown model '%s'. Closest: q2_0\n" % model); sys.exit(2)
    if "--plan" in a:
        print("Plan: %s, nothing changes" % model); sys.exit(0)
    for line in ("Downloading shard 1 of 2: 40%", "Downloading shard 1 of 2: 100%", "\x1b[32mEngine started\x1b[0m", "Serving at http://127.0.0.1:8080"):
        print(line, flush=True)
    sys.exit(0)
sys.exit(1)
