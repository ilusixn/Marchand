import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import engine
import providers

DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
LESSONS = DATA / "lessons.json"
EXAMPLES = DATA / "examples.jsonl"

TEACHER_CONTEXT = """You are acting as a TEACHER inside Marchand, a desktop app that trains a smaller AI model (the STUDENT) that runs locally on the
user's computer through Ollama. The student is a much smaller open model (typically 3 to 32 billion parameters). It cannot see this
conversation. It learns only from (1) short rules you write, which are added to its instructions for every future task, and (2) worked
examples of tasks solved correctly, which may later be used to fine-tune it.

How to teach well:
- Judge the student's work by what really happened (test results, tool output), not by what it claimed.
- Name the single most important mistake first; small models improve fastest with one clear fix at a time.
- Write rules as short, general, imperative habits ("Run the failing test before editing") that apply to many future tasks.
  Never write rules about one specific file, variable or project; the student will meet different code next time.
- Prefer concrete procedures over vague advice ("re-read the file and copy the exact lines" beats "be careful").
- The student uses these tools: list_files, read_file, search, edit_file (exact text replacement), write_file, run_command, plan,
  ask_user, finish. Phrase advice in terms of those tools.
- Be honest and specific. Do not praise. Do not lecture."""

TEACHER_DEMO = """You are demonstrating how to solve this task for a smaller AI model that will learn by copying your transcript.
Work in small, clear, verifiable steps a small model can imitate: run the failing test first, read the relevant file, make the
smallest edit, run the tests again, and finish with a one-paragraph summary of what you changed and how you verified it.
Avoid clever shortcuts, avoid unnecessary tools, and do not change the test files."""

TRAIN_SCRIPT = '''# Template: LoRA fine-tune with Unsloth. Needs an NVIDIA GPU (8 GB+ VRAM for a 7B model), Python 3.10+.
# pip install unsloth trl datasets
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

BASE = "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit"
model, tok = FastLanguageModel.from_pretrained(BASE, max_seq_length=8192, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
ds = load_dataset("json", data_files="marchand_dataset.jsonl", split="train")
ds = ds.map(lambda ex: {"text": tok.apply_chat_template(ex["messages"], tokenize=False)})
SFTTrainer(model=model, tokenizer=tok, train_dataset=ds, args=SFTConfig(
    dataset_text_field="text", per_device_train_batch_size=1, gradient_accumulation_steps=8,
    num_train_epochs=2, learning_rate=2e-4, logging_steps=5, output_dir="outputs")).train()
model.save_pretrained_gguf("marchand-gguf", tok, quantization_method="q4_k_m")
# Then: write a Modelfile containing  FROM ./marchand-gguf/<file>.gguf  and run  ollama create marchand-tuned -f Modelfile
'''


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def lessons():
    return read_json(LESSONS, [])


def save_lessons(items):
    DATA.mkdir(parents=True, exist_ok=True)
    LESSONS.write_text(json.dumps(items, indent=1), encoding="utf-8")


def add_lessons(texts, source, tags=None):
    items = lessons()
    have = {l["text"].lower() for l in items}
    n = 0
    for t in texts:
        text = (t.get("text") if isinstance(t, dict) else str(t)).strip()
        if not text or text.lower() in have:
            continue
        tg = (t.get("tags") if isinstance(t, dict) else None) or tags or ["general"]
        items.append({"id": uuid.uuid4().hex[:8], "text": text[:300], "tags": tg, "source": source, "time": int(time.time()), "enabled": True})
        have.add(text.lower())
        n += 1
    save_lessons(items)
    return n


def update_lesson(lid, enabled=None, delete=False, text=None):
    items = lessons()
    out = []
    for l in items:
        if l["id"] == lid:
            if delete:
                continue
            if enabled is not None:
                l["enabled"] = bool(enabled)
            if text is not None:
                l["text"] = text[:300]
        out.append(l)
    save_lessons(out)


def consolidate(settings, model):
    items = lessons()
    mine = [l for l in items if l.get("source") == "you"]
    others = [l for l in items if l.get("source") != "you" and l.get("enabled", True)]
    if len(others) < 8:
        return len(items)
    system = (TEACHER_CONTEXT + "\n\nTask now: merge the student's current rules into at most 25 short, general, non-overlapping rules (max 25 words each). Keep the most "
              "useful ones, drop duplicates and project-specific trivia. Reply with ONLY a JSON array of strings.")
    res = providers.chat_once(settings, model, [{"role": "system", "content": system},
                                                {"role": "user", "content": "\n".join("- " + l["text"] for l in others)}], {"temperature": 0.1})
    m = re.search(r"\[.*\]", res, re.S)
    rules = [str(r).strip() for r in json.loads(m.group(0)) if str(r).strip()] if m else []
    if not rules:
        raise ValueError("the teacher did not return a list of rules")
    new = mine + [{"id": uuid.uuid4().hex[:8], "text": r[:300], "tags": ["general"], "source": "condensed", "time": int(time.time()), "enabled": True}
                  for r in rules[:25]]
    save_lessons(new)
    return len(new)


def lessons_prompt(langs, limit=1800):
    pri = [l for l in lessons() if l.get("enabled", True)]
    if "*" in langs:
        groups = {}
        for l in sorted(pri, key=lambda l: -l.get("time", 0)):
            groups.setdefault((l.get("tags") or ["general"])[0], []).append(l)
        order = ["general"] + sorted(k for k in groups if k != "general")
        pri = []
        depth = 0
        while any(depth < len(groups.get(k, [])) for k in order):
            for k in order:
                if depth < len(groups.get(k, [])):
                    pri.append(groups[k][depth])
            depth += 1
    else:
        pri.sort(key=lambda l: (0 if set(l.get("tags", [])) & set(langs) else 1 if "general" in l.get("tags", []) else 2, -l.get("time", 0)))
    lines, used = [], 0
    for l in pri:
        if used + len(l["text"]) > limit:
            break
        lines.append("- " + l["text"])
        used += len(l["text"]) + 2
    return "# Lessons learned from your teacher (follow them)\n" + "\n".join(lines) if lines else ""


def transcript(history, max_chars=14000):
    out = []
    for m in history:
        r = m.get("role")
        if r == "user":
            out.append("USER: " + (m.get("content") or ""))
        elif r == "assistant":
            if m.get("content"):
                out.append("ASSISTANT: " + m["content"])
            for c in m.get("tool_calls") or []:
                fn = c.get("function", {})
                a = json.dumps(fn.get("arguments", {}))
                out.append("TOOL CALL %s %s" % (fn.get("name"), a[:500]))
        elif r == "tool":
            out.append("TOOL RESULT: " + (m.get("content") or "")[:700])
    text = "\n".join(out)
    return text if len(text) <= max_chars else text[:max_chars // 2] + "\n...\n" + text[-max_chars // 2:]


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("teacher did not return JSON")
    return json.loads(m.group(0))


def evaluate(settings, teacher_model, history, project_langs):
    system = (TEACHER_CONTEXT + "\n\nTask now: read the transcript of the student's work and judge "
              "it honestly. Reply with ONLY a JSON object: {\"score\": 1-10, \"verdict\": \"one sentence\", \"mistakes\": [\"...\"], "
              "\"lessons\": [{\"text\": \"a general, reusable rule (max 25 words) that would have avoided the mistakes\", "
              "\"tags\": [\"general\" or a language like python/js/cpp]}], \"better_approach\": \"how you would have solved it\"}. "
              "Lessons must be generic habits, not facts about this one project. Give at most 5 lessons.")
    res = providers.chat_once(settings, teacher_model, [{"role": "system", "content": system},
                                                        {"role": "user", "content": "Transcript:\n" + transcript(history)}], {"temperature": 0.2})
    data = extract_json(res)
    data["added"] = add_lessons(data.get("lessons", []), "teacher:" + teacher_model, project_langs or None)
    return data


def ask_teacher(settings, teacher_model, question, context):
    system = (TEACHER_CONTEXT + "\n\nTask now: the student is stuck and asks you a question during a task. Give a short, concrete answer: "
              "the likely cause, the exact next step, and a code snippet if useful. Max 200 words.")
    return providers.chat_once(settings, teacher_model, [{"role": "system", "content": system},
                                                         {"role": "user", "content": "Situation:\n%s\n\nQuestion: %s" % (context[-6000:], question)}],
                               {"temperature": 0.2})


def save_example(convo, rating, system_prompt=""):
    DATA.mkdir(parents=True, exist_ok=True)
    prov, model = providers.split_model(convo.get("model", ""))
    rec = {"id": uuid.uuid4().hex[:8], "title": convo.get("title", ""), "model": convo.get("model", ""), "provider": prov,
           "mode": convo.get("mode", "code"), "rating": int(rating), "time": int(time.time()), "messages": convo.get("history", [])}
    with EXAMPLES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec["id"]


def examples():
    out = []
    if EXAMPLES.is_file():
        for line in EXAMPLES.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def delete_example(eid):
    keep = [e for e in examples() if e["id"] != eid]
    EXAMPLES.write_text("".join(json.dumps(e) + "\n" for e in keep), encoding="utf-8")


def hf_messages(history, system):
    out = [{"role": "system", "content": system}]
    for m in history:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": [
                {"type": "function", "function": {"name": c["function"]["name"], "arguments": providers.parse_args(c["function"].get("arguments"))}}
                for c in m["tool_calls"]]})
        elif m["role"] == "tool":
            out.append({"role": "tool", "name": m.get("tool_name", ""), "content": m.get("content", "")})
        elif m["role"] in ("user", "assistant"):
            out.append({"role": m["role"], "content": m.get("content", "")})
    return out


def export_dataset(min_rating=4, cloud_only=False):
    system = engine.read_know("core") + "\n\n" + engine.read_know("tools")
    lines = []
    for e in examples():
        if e["rating"] < min_rating or (cloud_only and e["provider"] == "ollama"):
            continue
        lines.append(json.dumps({"messages": hf_messages(e["messages"], system)}))
    return "\n".join(lines) + ("\n" if lines else ""), len(lines)


AIS = DATA / "ais.json"


def ais():
    return read_json(AIS, [])


def save_ai(profile):
    items = [p for p in ais() if p["name"] != profile["name"]]
    items.append(profile)
    DATA.mkdir(parents=True, exist_ok=True)
    AIS.write_text(json.dumps(items, indent=1), encoding="utf-8")


def delete_ai(name):
    AIS.write_text(json.dumps([p for p in ais() if p["name"] != name], indent=1), encoding="utf-8")


def final_text(history):
    for m in reversed(history):
        if m.get("role") == "tool" and m.get("tool_name") == "finish":
            return m.get("content", "")
        if m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
            return m["content"]
    return ""


def few_shot(count):
    out = []
    good = [e for e in examples() if e["rating"] >= 4]
    good.sort(key=lambda e: (e["provider"] == "ollama", -e["time"]))
    for e in good[:count]:
        task = next((m["content"] for m in e["messages"] if m.get("role") == "user"), "")
        answer = final_text(e["messages"])
        if task and answer:
            out.append({"role": "user", "content": task[:600]})
            out.append({"role": "assistant", "content": answer[:600]})
    return out


def system_for(profile, langs):
    parts = [engine.read_know("core"), engine.read_know("tools"), engine.read_know("debugging")]
    if profile.get("persona", "").strip():
        parts.append("# Your role\n" + profile["persona"].strip())
    if profile.get("reverse"):
        parts.append(engine.read_know("reverse"))
    if profile.get("include_lessons", True):
        lp = lessons_prompt(langs or ["general"], int(profile.get("lesson_chars", 3000)))
        if lp:
            parts.append(lp)
    return "\n\n".join(parts)


def build_model(settings, base, name, langs, profile=None):
    profile = dict(profile or {})
    system = system_for(profile, langs)
    shots = few_shot(int(profile.get("examples", 0)))
    params = {"temperature": float(profile.get("temperature", 0.2)), "num_ctx": int(profile.get("num_ctx", 16384))}
    host = settings["host"].rstrip("/")

    def post(body):
        req = urllib.request.Request(host + "/api/create", json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                if raw.strip():
                    ev = json.loads(raw)
                    if ev.get("error"):
                        raise RuntimeError(ev["error"])
                    yield ev
    try:
        body = {"model": name, "name": name, "from": base, "system": system, "stream": True, "parameters": params}
        if shots:
            body["messages"] = shots
        yield from post(body)
    except (RuntimeError, urllib.error.HTTPError):
        mf = 'FROM %s\nPARAMETER temperature %s\nPARAMETER num_ctx %s\nSYSTEM """%s"""\n' % (
            base, params["temperature"], params["num_ctx"], system.replace('"""', "'''"))
        for m in shots:
            mf += 'MESSAGE %s """%s"""\n' % (m["role"], m["content"].replace('"""', "'''"))
        yield from post({"name": name, "modelfile": mf, "stream": True})
