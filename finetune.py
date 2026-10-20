import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import ollama_mgr
import pack
import teacher

DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
FT = DATA / "finetune"
HF_BASES = {
    "qwen2.5-coder:1.5b": ("unsloth/Qwen2.5-Coder-1.5B-Instruct-bnb-4bit", 4),
    "qwen2.5-coder:3b": ("unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit", 6),
    "qwen2.5-coder:7b": ("unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit", 8),
    "qwen2.5-coder:14b": ("unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit", 16),
    "qwen2.5-coder:32b": ("unsloth/Qwen2.5-Coder-32B-Instruct-bnb-4bit", 24),
    "qwen2.5:7b": ("unsloth/Qwen2.5-7B-Instruct-bnb-4bit", 8),
    "llama3.1:8b": ("unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit", 8),
    "llama3.2:3b": ("unsloth/Llama-3.2-3B-Instruct-bnb-4bit", 6),
    "mistral:7b": ("unsloth/mistral-7b-instruct-v0.3-bnb-4bit", 8),
}
SCRIPT = '''import glob, json, sys
cfg = json.load(open(sys.argv[1]))
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset
print("Loading", cfg["hf_base"], flush=True)
model, tok = FastLanguageModel.from_pretrained(cfg["hf_base"], max_seq_length=cfg["max_seq"], load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=cfg["lora_r"], lora_alpha=cfg["lora_r"], lora_dropout=0, bias="none",
    use_gradient_checkpointing="unsloth", target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
ds = load_dataset("json", data_files=cfg["dataset"], split="train")
ds = ds.map(lambda ex: {"text": tok.apply_chat_template(ex["messages"], tokenize=False)})
print("Training on", len(ds), "examples", flush=True)
SFTTrainer(model=model, tokenizer=tok, train_dataset=ds, args=SFTConfig(dataset_text_field="text", per_device_train_batch_size=1,
    gradient_accumulation_steps=8, num_train_epochs=cfg["epochs"], learning_rate=cfg["lr"], logging_steps=1, output_dir=cfg["out"] + "/ckpt",
    max_seq_length=cfg["max_seq"], report_to=[])).train()
print("Exporting GGUF", flush=True)
model.save_pretrained_gguf(cfg["out"] + "/gguf", tok, quantization_method="q4_k_m")
print("GGUF:", glob.glob(cfg["out"] + "/gguf/*.gguf"), flush=True)
'''
JOBS = {}


def check():
    hw = ollama_mgr.hardware()
    out = {"vendor": hw.get("vendor", ""), "gpu": hw.get("gpu", ""), "vram_gb": hw.get("vram_gb", 0), "nvidia": bool(shutil.which("nvidia-smi")) and hw.get("vram_gb", 0) > 0,
           "python": sys.executable, "missing": [], "bases": [{"name": k, "hf": v[0], "vram": v[1]} for k, v in HF_BASES.items()]}
    for mod in ("torch", "unsloth", "trl", "datasets"):
        r = subprocess.run([sys.executable, "-c", "import " + mod], capture_output=True, timeout=120)
        if r.returncode:
            out["missing"].append(mod)
    out["pip"] = "%s -m pip install unsloth trl datasets" % sys.executable
    out["examples"] = len([e for e in teacher.examples() if e["rating"] >= 4])
    out["ready"] = out["nvidia"] and not out["missing"] and out["examples"] >= 10
    return out


def upload_blob(host, path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = "sha256:" + h.hexdigest()
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        req = urllib.request.Request(host + "/api/blobs/" + digest, f, {"Content-Length": str(size), "Content-Type": "application/octet-stream"}, method="POST")
        urllib.request.urlopen(req, timeout=3600).read()
    return digest


def import_gguf(settings, gguf, name, system):
    host = settings["host"].rstrip("/")
    try:
        digest = upload_blob(host, gguf)
        body = {"model": name, "files": {os.path.basename(gguf): digest}, "system": system, "parameters": {"temperature": 0.2}, "stream": False}
        req = urllib.request.Request(host + "/api/create", json.dumps(body).encode(), {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3600).read()
    except Exception:
        mf = 'FROM %s\nPARAMETER temperature 0.2\nSYSTEM """%s"""\n' % (os.path.abspath(gguf), system.replace('"""', "'''"))
        req = urllib.request.Request(host + "/api/create", json.dumps({"name": name, "modelfile": mf, "stream": False}).encode(), {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3600).read()


def start(settings, cfg):
    if any(j["status"] == "running" for j in JOBS.values()):
        raise RuntimeError("A fine-tune is already running.")
    base = cfg.get("base", "")
    hf = cfg.get("hf_base") or HF_BASES.get(base, ("", 0))[0]
    if not hf:
        raise ValueError("No training weights known for %s. Paste a Hugging Face model id." % base)
    name = cfg.get("name") or "marchand-tuned"
    jid = time.strftime("%Y%m%d-%H%M%S")
    out = FT / jid
    out.mkdir(parents=True, exist_ok=True)
    data, n = teacher.export_dataset(int(cfg.get("min_rating", 4)), bool(cfg.get("cloud_only", False)))
    if n < int(cfg.get("min_examples", 10)):
        raise ValueError("Only %d good examples. Collect at least %d (Training tab) before fine-tuning." % (n, int(cfg.get("min_examples", 10))))
    (out / "dataset.jsonl").write_text(data, encoding="utf-8")
    (out / "train.py").write_text(SCRIPT, encoding="utf-8")
    conf = {"hf_base": hf, "dataset": str(out / "dataset.jsonl"), "out": str(out), "epochs": int(cfg.get("epochs", 2)),
            "lr": float(cfg.get("lr", 2e-4)), "lora_r": int(cfg.get("lora_r", 16)), "max_seq": int(cfg.get("max_seq", 4096))}
    (out / "config.json").write_text(json.dumps(conf, indent=1), encoding="utf-8")
    job = {"id": jid, "status": "running", "name": name, "base": base, "hf": hf, "examples": n, "log": [], "started": int(time.time())}
    JOBS[jid] = job
    threading.Thread(target=_run, args=(settings, job, out), daemon=True).start()
    return jid


def _run(settings, job, out):
    def log(t):
        job["log"].append(t.rstrip())
        job["log"] = job["log"][-500:]
    cmd = os.environ.get("MARCHAND_FT_CMD")
    args = cmd.split() + [str(out / "config.json")] if cmd else [sys.executable, str(out / "train.py"), str(out / "config.json")]
    try:
        log("Starting: " + " ".join(args))
        p = subprocess.Popen(args, cwd=str(out), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        job["pid"] = p.pid
        for line in p.stdout:
            log(line)
        p.wait()
        if job.get("stop"):
            job["status"] = "stopped"
            return
        if p.returncode:
            raise RuntimeError("training exited with code %d (see log)" % p.returncode)
        ggufs = sorted((out / "gguf").glob("*.gguf")) + sorted(out.glob("*.gguf"))
        if not ggufs:
            raise RuntimeError("training finished but no .gguf file was produced")
        log("Importing %s into Ollama as %s" % (ggufs[0].name, job["name"]))
        system = pack.PERSONA + "\n\n" + teacher.lessons_prompt(["python", "general"], 2000)
        import_gguf(settings, str(ggufs[0]), job["name"], system)
        teacher.save_ai({"name": job["name"], "base": job["base"] or job["hf"], "persona": pack.PERSONA, "include_lessons": True, "examples": 0,
                         "temperature": 0.2, "num_ctx": 8192, "created": int(time.time()), "lessons": len(teacher.lessons()), "fine_tuned": True})
        job["status"] = "finished"
        log("Done. Your fine-tuned model is %s." % job["name"])
    except Exception as ex:
        job["status"] = "error"
        log("Error: %s" % ex)


def stop(jid):
    job = JOBS.get(jid)
    if job and job.get("pid"):
        job["stop"] = True
        try:
            os.kill(job["pid"], 9)
        except OSError:
            pass
