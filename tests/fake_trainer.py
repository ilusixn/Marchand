import json, os, sys, time
cfg = json.load(open(sys.argv[1]))
n = sum(1 for _ in open(cfg["dataset"]))
print("Loading", cfg["hf_base"], flush=True)
for step in range(3):
    print("{'loss': %.3f, 'epoch': %.2f}" % (1.5 - step * 0.4, (step + 1) / 3), flush=True); time.sleep(0.2)
os.makedirs(cfg["out"] + "/gguf", exist_ok=True)
open(cfg["out"] + "/gguf/unsloth.Q4_K_M.gguf", "wb").write(b"GGUF" + b"\0" * 2048)
print("trained on", n, "examples", flush=True)
