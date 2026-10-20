import base64
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import providers

DATA = Path(os.environ.get("MARCHAND_HOME", Path.home() / ".marchand"))
IMG_DIR = DATA / "images"
INDEX = DATA / "images.json"
IMAGE_PROVIDERS = {"openai": "gpt-image-1", "xai": "grok-2-image", "together": "black-forest-labs/FLUX.1-schnell",
                   "fireworks": "", "custom": "", "huggingface": ""}
DEFAULTS = {"forge_url": "http://127.0.0.1:7860", "comfy_url": "http://127.0.0.1:8188", "default": "auto",
            "cloud_provider": "openai", "cloud_model": "gpt-image-1", "comfy_workflow": ""}


class Cancelled(Exception):
    pass


def conf(settings):
    c = dict(DEFAULTS)
    c.update(settings.get("images") or {})
    return c


def http(url, body=None, timeout=30, headers=None, method=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, dict({"Content-Type": "application/json"}, **(headers or {})), method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = r.read()
    return content if raw else (json.loads(content) if content.strip() else {})


def ext_of(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return "png"


def index():
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_image(data, meta):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    name = "img_%d_%s.%s" % (int(time.time()), uuid.uuid4().hex[:5], ext_of(data))
    (IMG_DIR / name).write_bytes(data)
    rec = dict(meta, name=name, time=int(time.time()))
    items = [rec] + index()
    INDEX.write_text(json.dumps(items[:500]), encoding="utf-8")
    return rec


def delete_image(name):
    name = os.path.basename(name)
    f = IMG_DIR / name
    if f.is_file():
        f.unlink()
    INDEX.write_text(json.dumps([i for i in index() if i["name"] != name]), encoding="utf-8")


def read_image(name):
    f = IMG_DIR / os.path.basename(name)
    return f.read_bytes() if f.is_file() else None


def forge_info(url):
    url = url.rstrip("/")
    models = http(url + "/sdapi/v1/sd-models", timeout=6)
    try:
        samplers = [s["name"] for s in http(url + "/sdapi/v1/samplers", timeout=6)]
    except Exception:
        samplers = []
    try:
        cur = http(url + "/sdapi/v1/options", timeout=6).get("sd_model_checkpoint", "")
    except Exception:
        cur = ""
    return {"ok": True, "kind": "Forge / A1111", "models": [m.get("title") or m.get("model_name") for m in models], "current": cur, "samplers": samplers}


def comfy_info(url):
    url = url.rstrip("/")
    http(url + "/system_stats", timeout=6)
    models, samplers, schedulers = [], [], []
    try:
        ck = http(url + "/object_info/CheckpointLoaderSimple", timeout=10)
        models = ck["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    except Exception:
        pass
    try:
        ks = http(url + "/object_info/KSampler", timeout=10)["KSampler"]["input"]["required"]
        samplers, schedulers = ks["sampler_name"][0], ks["scheduler"][0]
    except Exception:
        pass
    return {"ok": True, "kind": "ComfyUI", "models": models, "current": models[0] if models else "", "samplers": samplers, "schedulers": schedulers}


def status(settings):
    c = conf(settings)
    out = {"forge": {"ok": False, "url": c["forge_url"]}, "comfyui": {"ok": False, "url": c["comfy_url"]}, "cloud": []}
    for key, fn, url in (("forge", forge_info, c["forge_url"]), ("comfyui", comfy_info, c["comfy_url"])):
        try:
            out[key] = dict(fn(url), url=url)
        except Exception as ex:
            out[key] = {"ok": False, "url": url, "error": providers.err_text(ex)}
    for prov, default_model in IMAGE_PROVIDERS.items():
        pc = (settings.get("providers") or {}).get(prov) or {}
        if pc.get("key") or (prov == "custom" and pc.get("base")):
            out["cloud"].append({"provider": prov, "label": providers.LABELS.get(prov, prov), "model": default_model})
    out["config"] = c
    return out


def default_backend(settings, st=None):
    c = conf(settings)
    st = st or status(settings)
    if c["default"] in ("forge", "comfyui") and st[c["default"]]["ok"]:
        return c["default"]
    if c["default"].startswith("cloud:") and any(x["provider"] == c["default"][6:] for x in st["cloud"]):
        return c["default"]
    for k in ("forge", "comfyui"):
        if st[k]["ok"]:
            return k
    if st["cloud"]:
        return "cloud:" + st["cloud"][0]["provider"]
    return None


def clamp(v, lo, hi, d):
    try:
        return max(lo, min(hi, type(d)(v)))
    except (TypeError, ValueError):
        return d


def norm_params(p):
    seed = int(p.get("seed", -1) or -1)
    return {"prompt": str(p.get("prompt", "")).strip(), "negative": str(p.get("negative", "")),
            "width": clamp(p.get("width", 1024), 64, 2048, 1024), "height": clamp(p.get("height", 1024), 64, 2048, 1024),
            "steps": clamp(p.get("steps", 25), 1, 150, 25), "cfg": clamp(p.get("cfg", 7), 1.0, 30.0, 7.0),
            "sampler": str(p.get("sampler", "")), "scheduler": str(p.get("scheduler", "")), "checkpoint": str(p.get("checkpoint", "")),
            "seed": seed if seed >= 0 else random.randint(0, 2 ** 31 - 1), "count": clamp(p.get("count", 1), 1, 8, 1),
            "init_image": p.get("init_image") or "", "denoise": clamp(p.get("denoise", 0.6), 0.0, 1.0, 0.6)}


def forge_generate(url, p, emit, cancel):
    url = url.rstrip("/")
    if p["checkpoint"]:
        try:
            cur = http(url + "/sdapi/v1/options", timeout=10).get("sd_model_checkpoint", "")
            if cur != p["checkpoint"]:
                emit({"type": "progress", "pct": 2, "text": "Loading checkpoint..."})
                http(url + "/sdapi/v1/options", {"sd_model_checkpoint": p["checkpoint"]}, timeout=300)
        except Exception:
            pass
    payload = {"prompt": p["prompt"], "negative_prompt": p["negative"], "steps": p["steps"], "cfg_scale": p["cfg"],
               "width": p["width"], "height": p["height"], "seed": p["seed"], "batch_size": 1, "n_iter": p["count"]}
    if p["sampler"]:
        payload["sampler_name"] = p["sampler"]
    path = "/sdapi/v1/txt2img"
    if p["init_image"]:
        payload["init_images"] = [p["init_image"]]
        payload["denoising_strength"] = p["denoise"]
        path = "/sdapi/v1/img2img"
    box = {}

    def work():
        try:
            box["res"] = http(url + path, payload, timeout=3600)
        except Exception as ex:
            box["err"] = ex
    th = threading.Thread(target=work, daemon=True)
    th.start()
    while th.is_alive():
        if cancel.is_set():
            try:
                http(url + "/sdapi/v1/interrupt", {}, timeout=5)
            except Exception:
                pass
            raise Cancelled()
        try:
            pr = http(url + "/sdapi/v1/progress?skip_current_image=true", timeout=5)
            emit({"type": "progress", "pct": int(100 * float(pr.get("progress", 0))), "text": "Generating..."})
        except Exception:
            pass
        th.join(0.8)
    if "err" in box:
        raise RuntimeError(providers.err_text(box["err"]))
    return [base64.b64decode(i.split(",", 1)[-1]) for i in box["res"].get("images", [])]


def comfy_workflow(p):
    return {
        "3": {"class_type": "KSampler", "inputs": {"seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
                                                    "sampler_name": p["sampler"] or "euler", "scheduler": p["scheduler"] or "normal", "denoise": 1,
                                                    "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": p["checkpoint"]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": p["width"], "height": p["height"], "batch_size": p["count"]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": p["prompt"], "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": p["negative"], "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "marchand", "images": ["8", 0]}}}


def fill_workflow(text, p):
    tokens = {"%prompt%": p["prompt"], "%negative%": p["negative"], "%seed%": p["seed"], "%steps%": p["steps"], "%cfg%": p["cfg"],
              "%width%": p["width"], "%height%": p["height"], "%checkpoint%": p["checkpoint"], "%sampler%": p["sampler"] or "euler",
              "%scheduler%": p["scheduler"] or "normal", "%count%": p["count"]}

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str):
            if x in tokens:
                return tokens[x]
            for k, v in tokens.items():
                x = x.replace(k, str(v))
        return x
    return walk(json.loads(text))


def comfy_generate(url, p, workflow_text, emit, cancel):
    url = url.rstrip("/")
    if workflow_text.strip():
        wf = fill_workflow(workflow_text, p)
    else:
        if not p["checkpoint"]:
            info = comfy_info(url)
            if not info["models"]:
                raise RuntimeError("ComfyUI has no checkpoint installed. Put a model in ComfyUI/models/checkpoints.")
            p["checkpoint"] = info["models"][0]
        wf = comfy_workflow(p)
    cid = uuid.uuid4().hex
    try:
        res = http(url + "/prompt", {"prompt": wf, "client_id": cid}, timeout=30)
    except urllib.error.HTTPError as ex:
        raise RuntimeError("ComfyUI rejected the workflow: " + providers.err_text(ex))
    pid = res.get("prompt_id")
    if not pid:
        raise RuntimeError("ComfyUI did not accept the job: %s" % res)
    t0 = time.time()
    while True:
        if cancel.is_set():
            try:
                http(url + "/interrupt", {}, timeout=5)
            except Exception:
                pass
            raise Cancelled()
        h = http(url + "/history/" + pid, timeout=15)
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError("ComfyUI error: " + json.dumps(st.get("messages", ""))[:300])
            out = []
            for node in entry.get("outputs", {}).values():
                for im in node.get("images", []):
                    if im.get("type", "output") == "output":
                        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
                        out.append(http(url + "/view?" + q, timeout=60, raw=True))
            if out:
                return out
            if st.get("completed"):
                raise RuntimeError("ComfyUI finished but returned no images. Does the workflow end in a SaveImage node?")
        el = time.time() - t0
        emit({"type": "progress", "pct": min(90, int(el * 3)), "text": "ComfyUI is working... %ds" % el})
        if el > 1800:
            raise RuntimeError("ComfyUI timed out")
        time.sleep(1.0)


def cloud_generate(settings, prov, model, p, emit, cancel):
    pc = providers.provider_cfg(settings, prov)
    if not pc.get("key") and prov != "custom":
        raise RuntimeError("No API key for %s." % providers.LABELS.get(prov, prov))
    size = "%dx%d" % (p["width"], p["height"])
    if prov == "openai" and model.startswith("gpt-image"):
        allowed = ["1024x1024", "1536x1024", "1024x1536"]
        size = size if size in allowed else ("1536x1024" if p["width"] > p["height"] else "1024x1536" if p["height"] > p["width"] else "1024x1024")
    body = {"model": model, "prompt": p["prompt"], "n": p["count"]}
    if prov not in ("xai",):
        body["size"] = size
    if not model.startswith("gpt-image"):
        body["response_format"] = "b64_json"
    emit({"type": "progress", "pct": 15, "text": "Waiting for %s..." % providers.LABELS.get(prov, prov)})
    hdr = {"Authorization": "Bearer " + pc.get("key", "")} if pc.get("key") else {}
    try:
        res = http(pc["base"].rstrip("/") + "/images/generations", body, timeout=600, headers=hdr)
    except urllib.error.HTTPError as ex:
        raise RuntimeError(providers.err_text(ex))
    out = []
    for d in res.get("data", []):
        if d.get("b64_json"):
            out.append(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            out.append(http(d["url"], timeout=120, raw=True))
    return out


def generate(settings, params, emit, cancel):
    p = norm_params(params)
    if not p["prompt"]:
        raise ValueError("Write a prompt first.")
    c = conf(settings)
    backend = params.get("backend") or default_backend(settings)
    if not backend:
        raise RuntimeError("No image generator found. Start Forge or ComfyUI, or add an OpenAI/Grok key. See Images > Setup.")
    emit({"type": "progress", "pct": 1, "text": "Starting..."})
    model = p["checkpoint"]
    if backend == "forge":
        imgs = forge_generate(c["forge_url"], p, emit, cancel)
    elif backend == "comfyui":
        imgs = comfy_generate(c["comfy_url"], p, c.get("comfy_workflow", ""), emit, cancel)
        model = p["checkpoint"]
    elif backend.startswith("cloud:"):
        prov = backend[6:]
        model = params.get("cloud_model") or (c["cloud_model"] if prov == c["cloud_provider"] else IMAGE_PROVIDERS.get(prov, ""))
        imgs = cloud_generate(settings, prov, model, p, emit, cancel)
    else:
        raise ValueError("Unknown image backend: %s" % backend)
    if not imgs:
        raise RuntimeError("The generator returned no images.")
    recs = []
    for i, data in enumerate(imgs):
        rec = save_image(data, {"prompt": p["prompt"], "negative": p["negative"], "backend": backend, "model": model, "seed": p["seed"] + i,
                                "width": p["width"], "height": p["height"], "steps": p["steps"], "cfg": p["cfg"], "sampler": p["sampler"]})
        recs.append(rec)
        emit({"type": "image", "image": rec})
    return recs


def enhance_prompt(settings, model, prompt):
    system = ("You write prompts for Stable Diffusion / FLUX image generators. Rewrite the user's idea as ONE detailed prompt: subject, "
              "setting, lighting, style, camera/lens, quality tags, comma separated. Max 80 words. Reply with the prompt only.")
    return providers.chat_once(settings, model, [{"role": "system", "content": system}, {"role": "user", "content": prompt}], {"temperature": 0.7}).strip()
