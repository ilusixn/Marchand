import json
import socket
import threading
import os
import urllib.error
import urllib.request

HOST = "127.0.0.1"

LINKS = [
    {"id": "ollama", "name": "Ollama", "what": "Runs AI models on your PC (needed for local models)", "url": "https://ollama.com/download"},
    {"id": "lmstudio", "name": "LM Studio", "what": "Friendly local model runner, supports AMD through Vulkan", "url": "https://lmstudio.ai"},
    {"id": "jan", "name": "Jan", "what": "Open-source local chat app", "url": "https://jan.ai"},
    {"id": "koboldcpp", "name": "KoboldCpp", "what": "Single-file runner with Vulkan support for AMD", "url": "https://github.com/LostRuins/koboldcpp/releases"},
    {"id": "textgen", "name": "text-generation-webui", "what": "Feature-rich model web UI", "url": "https://github.com/oobabooga/text-generation-webui"},
    {"id": "llamacpp", "name": "llama.cpp", "what": "The engine behind many local runners", "url": "https://github.com/ggml-org/llama.cpp"},
    {"id": "gpt4all", "name": "GPT4All", "what": "Desktop local chat app", "url": "https://www.nomic.ai/gpt4all"},
    {"id": "strata", "name": "Strata", "what": "Runs very large models (a 125B model) on a gaming PC; free, MIT license", "url": "https://github.com/Niko1221/Strata/releases/latest"},
    {"id": "localai", "name": "LocalAI", "what": "OpenAI-compatible local server", "url": "https://localai.io"},
    {"id": "forge", "name": "Stable Diffusion WebUI Forge", "what": "Make pictures (fast, low memory)", "url": "https://github.com/lllyasviel/stable-diffusion-webui-forge",
     "amd": "https://github.com/lshqqytiger/stable-diffusion-webui-amdgpu-forge", "amd_note": "AMD build (DirectML / ZLUDA)"},
    {"id": "a1111", "name": "Automatic1111 WebUI", "what": "The classic picture-making web UI", "url": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
     "amd": "https://github.com/lshqqytiger/stable-diffusion-webui-amdgpu", "amd_note": "AMD build (DirectML / ZLUDA)"},
    {"id": "sdnext", "name": "SD.Next", "what": "Picture-making web UI with AMD, Intel and NVIDIA backends", "url": "https://github.com/vladmandic/sdnext"},
    {"id": "comfyui", "name": "ComfyUI", "what": "Node-based picture and video workflows", "url": "https://www.comfy.org/download",
     "amd": "https://github.com/comfyanonymous/ComfyUI#amd-gpus-linux-and-windows", "amd_note": "AMD instructions (ROCm)"},
    {"id": "invokeai", "name": "InvokeAI", "what": "Polished picture-making studio", "url": "https://github.com/invoke-ai/InvokeAI"},
    {"id": "fooocus", "name": "Fooocus", "what": "Simple one-prompt picture maker", "url": "https://github.com/lllyasviel/Fooocus"},
    {"id": "openwebui", "name": "Open WebUI", "what": "Web chat front-end for local models", "url": "https://openwebui.com"},
    {"id": "claude-code", "name": "Claude Code", "what": "Use Claude on your subscription inside Marchand", "url": "https://claude.ai/code"},
    {"id": "ffmpeg", "name": "FFmpeg", "what": "Lets AIs look at videos", "url": "https://ffmpeg.org/download.html"},
    {"id": "git", "name": "Git", "what": "Branch names, diffs and commits in Code", "url": "https://git-scm.com/downloads"},
    {"id": "python", "name": "Python", "what": "Runs tests and scripts in your projects", "url": "https://www.python.org/downloads/"},
    {"id": "unsloth", "name": "Unsloth", "what": "GPU fine-tuning (NVIDIA only)", "url": "https://github.com/unslothai/unsloth"},
    {"id": "ollama-library", "name": "Ollama model library", "what": "Every model you can download", "url": "https://ollama.com/search"},
    {"id": "hf-gguf", "name": "Hugging Face GGUF models", "what": "Thousands more models", "url": "https://huggingface.co/models?library=gguf&sort=trending"},
    {"id": "ollama-gpu", "name": "Ollama GPU support", "what": "Which AMD and NVIDIA cards work", "url": "https://docs.ollama.com/gpu"},
]
OPEN_HOSTS = {"ollama.com", "docs.ollama.com", "lmstudio.ai", "jan.ai", "github.com", "www.nomic.ai", "localai.io", "www.comfy.org", "openwebui.com",
              "claude.ai", "aider.chat", "block.github.io", "opencode.ai", "ffmpeg.org", "git-scm.com", "www.python.org", "huggingface.co", "buymeacoffee.com", "polyformproject.org"}


def links(vendor=""):
    out = []
    for l in LINKS:
        d = dict(l)
        if vendor == "amd" and l.get("amd"):
            d["url"], d["note"] = l["amd"], l["amd_note"]
            d["nvidia_url"] = l["url"]
        out.append(d)
    return out


def open_url(url):
    import webbrowser
    from urllib.parse import urlparse
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in OPEN_HOSTS:
        raise ValueError("link not allowed")
    log = os.environ.get("MARCHAND_OPEN_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(url + "\n")
        return
    webbrowser.open(url)


APPS = [
    {"id": "ollama", "name": "Ollama", "kind": "llm", "port": 11434, "path": "/api/version", "need": "version"},
    {"id": "lmstudio", "name": "LM Studio", "kind": "llm-openai", "port": 1234, "path": "/v1/models", "need": "data"},
    {"id": "jan", "name": "Jan", "kind": "llm-openai", "port": 1337, "path": "/v1/models", "need": "data"},
    {"id": "koboldcpp", "name": "KoboldCpp", "kind": "llm-openai", "port": 5001, "path": "/api/v1/model", "need": "result", "base": "http://127.0.0.1:5001/v1"},
    {"id": "textgen", "name": "text-generation-webui", "kind": "llm-openai", "port": 5000, "path": "/v1/models", "need": "data"},
    {"id": "llamacpp", "name": "llama.cpp server", "kind": "llm-openai", "port": 8080, "path": "/v1/models", "need": "data"},
    {"id": "vllm", "name": "vLLM", "kind": "llm-openai", "port": 8000, "path": "/v1/models", "need": "data"},
    {"id": "gpt4all", "name": "GPT4All", "kind": "llm-openai", "port": 4891, "path": "/v1/models", "need": "data"},
    {"id": "localai", "name": "LocalAI", "kind": "llm-openai", "port": 8081, "path": "/v1/models", "need": "data"},
    {"id": "forge", "name": "Forge / Automatic1111 / SD.Next", "kind": "image", "port": 7860, "path": "/sdapi/v1/options", "need": "json", "image": "forge"},
    {"id": "forge2", "name": "Forge / Automatic1111 (port 7861)", "kind": "image", "port": 7861, "path": "/sdapi/v1/options", "need": "json", "image": "forge"},
    {"id": "comfyui", "name": "ComfyUI", "kind": "image", "port": 8188, "path": "/system_stats", "need": "json", "image": "comfyui"},
    {"id": "comfydesktop", "name": "ComfyUI Desktop", "kind": "image", "port": 8000, "path": "/system_stats", "need": "json", "image": "comfyui"},
    {"id": "invokeai", "name": "InvokeAI", "kind": "image-other", "port": 9090, "path": "/api/v1/app/version", "need": "version"},
    {"id": "fooocus", "name": "Fooocus-API", "kind": "image-other", "port": 8888, "path": "/ping", "need": "any"},
    {"id": "openwebui", "name": "Open WebUI", "kind": "other", "port": 3000, "path": "/api/config", "need": "json"},
]


def get(host, port, path, timeout=1.2):
    req = urllib.request.Request("http://%s:%d%s" % (host, port, path), headers={"User-Agent": "Marchand"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(200000)


def probe(app, host=HOST):
    try:
        s = socket.create_connection((host, app["port"]), timeout=0.6)
        s.close()
    except OSError:
        return None
    try:
        status, body = get(host, app["port"], app["path"])
    except urllib.error.HTTPError as ex:
        if app["kind"] == "image" and ex.code in (404, 405):
            return {"app": app["id"], "name": app["name"], "kind": app["kind"], "url": "http://%s:%d" % (host, app["port"]),
                    "hint": "Something is running here but the API is off. Start it with the --api option (Forge/A1111: add --api to the launch arguments).",
                    "api": False, "image": app.get("image")}
        return None
    except Exception:
        return None
    detail = ""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        data = None
    need = app["need"]
    if need == "data" and not (isinstance(data, dict) and "data" in data):
        return None
    if need == "version" and not (isinstance(data, dict) and ("version" in data)):
        return None
    if need == "result" and not (isinstance(data, dict) and "result" in data):
        return None
    if need == "json" and data is None:
        return None
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            detail = "%d models" % len(data["data"])
        elif "version" in data:
            detail = "version %s" % data["version"]
    return {"app": app["id"], "name": app["name"], "kind": app["kind"], "url": "http://%s:%d" % (host, app["port"]), "detail": detail,
            "api": True, "image": app.get("image"), "base": app.get("base") or ("http://%s:%d/v1" % (host, app["port"]) if app["kind"] == "llm-openai" else "")}


def scan(host=HOST):
    found, lock = [], threading.Lock()

    def run(app):
        r = probe(app, host)
        if r:
            with lock:
                found.append(r)
    threads = [threading.Thread(target=run, args=(a,), daemon=True) for a in APPS]
    for t in threads:
        t.start()
    for t in threads:
        t.join(6)
    order = {a["id"]: i for i, a in enumerate(APPS)}
    return sorted(found, key=lambda r: order[r["app"]])
