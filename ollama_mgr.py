import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

def M(name, gb, tags, tools, desc):
    return {"name": name, "gb": gb, "tags": tags, "tools": tools, "desc": desc}


CATALOG = [
    M("qwen2.5-coder:1.5b", 1.0, ["coding", "tiny"], True, "Very small coder. Fast on any PC, limited skill."),
    M("qwen2.5-coder:3b", 1.9, ["coding", "small"], True, "Small coder for laptops without a graphics card."),
    M("qwen2.5-coder:7b", 4.7, ["coding"], True, "Good everyday coder. Needs about 8 GB of memory."),
    M("qwen2.5-coder:14b", 9.0, ["coding", "recommended"], True, "Best balance for most gaming PCs (12 GB+ VRAM or 16 GB RAM)."),
    M("qwen2.5-coder:32b", 20.0, ["coding", "large"], True, "Strongest Qwen coder. Needs a 24 GB GPU or 32 GB RAM."),
    M("qwen3-coder:30b", 19.0, ["coding", "large"], True, "Newer mixture-of-experts coder, strong tool use."),
    M("devstral:24b", 14.0, ["coding", "agent"], True, "Built for coding agents that edit many files."),
    M("deepseek-coder-v2:16b", 8.9, ["coding"], True, "Fast coder with long context."),
    M("codestral:22b", 12.0, ["coding"], False, "Mistral's coding model, 80+ languages."),
    M("starcoder2:3b", 1.7, ["coding", "small"], False, "Tiny code completion model."),
    M("starcoder2:7b", 4.0, ["coding"], False, "Code completion model."),
    M("starcoder2:15b", 9.1, ["coding"], False, "Larger code completion model."),
    M("granite-code:8b", 4.6, ["coding"], False, "IBM code model with permissive license."),
    M("codellama:13b", 7.4, ["coding"], False, "Older coder, no tool calling."),
    M("gpt-oss:20b", 14.0, ["general", "reasoning"], True, "Open-weight reasoning model with tool use."),
    M("gpt-oss:120b", 65.0, ["general", "reasoning", "large"], True, "Very large open-weight reasoning model."),
    M("qwen3:0.6b", 0.5, ["general", "tiny"], True, "Tiny chat model."),
    M("qwen3:1.7b", 1.4, ["general", "small"], True, "Small chat model with thinking mode."),
    M("qwen3:4b", 2.6, ["general", "small"], True, "Compact general model with thinking mode."),
    M("qwen3:8b", 5.2, ["general", "reasoning"], True, "General assistant with thinking mode."),
    M("qwen3:14b", 9.3, ["general", "reasoning"], True, "Bigger general assistant with thinking mode."),
    M("qwen3:32b", 20.0, ["general", "reasoning", "large"], True, "Large general assistant."),
    M("qwen2.5:7b", 4.7, ["general"], True, "Reliable general model."),
    M("qwen2.5:14b", 9.0, ["general"], True, "Stronger general model."),
    M("qwen2.5:32b", 20.0, ["general", "large"], True, "Large general model."),
    M("llama3.1:8b", 4.9, ["general"], True, "Reliable general chat model."),
    M("llama3.2:1b", 1.3, ["general", "tiny"], True, "Tiny Llama for very weak PCs."),
    M("llama3.2:3b", 2.0, ["general", "small"], True, "Light chat model for low-end PCs."),
    M("llama3.3:70b", 43.0, ["general", "large"], True, "Top open Llama. Needs 48 GB+ of memory."),
    M("mistral:7b", 4.1, ["general"], True, "Classic fast 7B model."),
    M("mistral-nemo:12b", 7.1, ["general"], True, "12B model with long context."),
    M("mistral-small3.2:24b", 15.0, ["general"], True, "Strong all-rounder with tool use."),
    M("gemma3:1b", 0.8, ["general", "tiny"], False, "Google's smallest model."),
    M("gemma3:4b", 3.3, ["general", "small", "vision"], False, "Small Google model that reads images."),
    M("gemma3:12b", 8.1, ["general", "vision"], False, "Google model that can also read images."),
    M("gemma3:27b", 17.0, ["general", "vision", "large"], False, "Large Google model with vision."),
    M("phi4:14b", 9.1, ["general"], False, "Microsoft model, strong at logic and math."),
    M("phi4-mini:3.8b", 2.5, ["general", "small"], True, "Small Microsoft model with tool use."),
    M("deepseek-r1:7b", 4.7, ["reasoning"], False, "Step-by-step reasoning model."),
    M("deepseek-r1:14b", 9.0, ["reasoning"], False, "Bigger reasoning model."),
    M("deepseek-r1:32b", 20.0, ["reasoning", "large"], False, "Large reasoning model."),
    M("hermes3:8b", 4.7, ["general"], True, "Fine-tuned for instruction following and tools."),
    M("command-r:35b", 19.0, ["general", "large"], True, "Cohere model, good with documents."),
    M("dolphin3:8b", 4.9, ["general"], False, "Uncensored-style general assistant."),
    M("smollm2:1.7b", 1.8, ["general", "tiny"], False, "Very small assistant."),
    M("llama3.2-vision:11b", 7.9, ["vision"], False, "Understands screenshots and photos."),
    M("minicpm-v:8b", 5.5, ["vision"], False, "Compact vision model."),
    M("llava:13b", 8.0, ["vision"], False, "Classic image-understanding model."),
    M("moondream:1.8b", 1.7, ["vision", "tiny"], False, "Tiny image-understanding model."),
    M("nomic-embed-text", 0.3, ["embedding"], False, "Text embeddings for search (not a chat model)."),
    M("llama4:scout", 67.0, ["general", "vision", "large"], True, "Meta's newest multimodal model. Needs a workstation."),
    M("gemma3n:e4b", 7.5, ["general", "small"], False, "Efficient Google model for laptops and phones."),
    M("qwen3-vl:8b", 6.1, ["vision", "general"], True, "Qwen vision-language model that reads images and screens."),
    M("qwq:32b", 20.0, ["reasoning", "large"], True, "Qwen reasoning model, strong at math and logic."),
    M("magistral:24b", 14.0, ["reasoning"], True, "Mistral reasoning model."),
    M("mixtral:8x7b", 26.0, ["general", "large"], True, "Mistral mixture-of-experts model."),
    M("phi3:3.8b", 2.2, ["general", "small"], False, "Small Microsoft model, fast on laptops."),
    M("codegemma:7b", 5.0, ["coding"], False, "Google code model."),
    M("yi-coder:9b", 5.0, ["coding"], False, "Coder trained on 50+ languages."),
    M("deepseek-coder:6.7b", 3.8, ["coding"], False, "Compact DeepSeek coder."),
    M("deepseek-coder-v2:236b", 133.0, ["coding", "large"], False, "Huge coder; needs a server."),
    M("opencoder:8b", 4.7, ["coding"], False, "Open coder with reproducible training data."),
    M("cogito:8b", 4.9, ["general", "reasoning"], True, "Hybrid reasoning model."),
    M("granite3.3:8b", 4.9, ["general"], True, "IBM general model with tool use."),
    M("olmo2:7b", 4.5, ["general"], False, "Fully open model from AI2."),
    M("openthinker:7b", 4.7, ["reasoning"], False, "Open reasoning model distilled from DeepSeek-R1."),
    M("glm4:9b", 5.5, ["general"], False, "Zhipu GLM chat model."),
    M("exaone-deep:7.8b", 4.8, ["reasoning"], False, "LG reasoning model."),
    M("nemotron-mini:4b", 2.7, ["general", "small"], True, "NVIDIA small assistant."),
    M("solar:10.7b", 6.1, ["general"], False, "Upstage general model."),
    M("tinyllama:1.1b", 0.64, ["general", "tiny"], False, "Tiny model for very weak PCs."),
    M("wizardlm2:7b", 4.1, ["general"], False, "Microsoft instruction-tuned model."),
    M("deepseek-r1:70b", 43.0, ["reasoning", "large"], False, "Very large reasoning model."),
    M("mxbai-embed-large", 0.67, ["embedding"], False, "Strong text embeddings (not a chat model)."),
]


def parse_win_gpus(out):
    best = None
    for line in out.splitlines():
        name, _, mem = line.partition("|")
        if re.search(r"\b(AMD|Radeon|ATI)\b", name, re.I):
            gb = round(int(mem) / 2 ** 30, 1) if mem.strip().isdigit() else 0.0
            if not best or gb > best[1]:
                best = (name.strip(), gb, "amd")
    return best


def amd_gpu():
    best = None
    try:
        if sys.platform.startswith("win"):
            ps = ("Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -ErrorAction SilentlyContinue | "
                  "ForEach-Object { $_.DriverDesc + '|' + $_.'HardwareInformation.qwMemorySize' }")
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True, timeout=15,
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            best = parse_win_gpus(out)
        else:
            import glob
            for card in glob.glob("/sys/class/drm/card[0-9]/device"):
                try:
                    if open(card + "/vendor").read().strip() != "0x1002":
                        continue
                except OSError:
                    continue
                try:
                    gb = round(int(open(card + "/mem_info_vram_total").read()) / 2 ** 30, 1)
                except (OSError, ValueError):
                    gb = 0.0
                name = "AMD Radeon"
                try:
                    name = open(card + "/product_name").read().strip() or name
                except OSError:
                    if shutil.which("rocm-smi"):
                        try:
                            o = subprocess.check_output(["rocm-smi", "--showproductname"], text=True, timeout=10)
                            m = re.search(r"Card series:\s*(.+)", o)
                            name = m.group(1).strip() if m else name
                        except Exception:
                            pass
                if not best or gb > best[1]:
                    best = (name, gb, "amd")
    except Exception:
        return None
    return best


def gpu_backend(hw):
    v = hw.get("vendor")
    if v == "nvidia":
        return "NVIDIA GPU: Ollama uses CUDA automatically."
    if v == "amd":
        return ("AMD GPU: Ollama uses ROCm on supported Radeon cards (RX 6000/7000/9000 and many Pro cards). "
                "Other Radeon cards can use Ollama's experimental Vulkan mode (set OLLAMA_VULKAN=1 and restart Ollama), "
                "or LM Studio / KoboldCpp, which run on AMD through Vulkan. Without GPU support models run on the CPU, only slower.")
    if v == "apple":
        return "Apple Silicon: Ollama uses the GPU (Metal) automatically."
    return "No dedicated GPU found: models run on the CPU, so pick small models."


def hardware():
    info = {"os": sys.platform, "ram_gb": 0.0, "gpu": "", "vram_gb": 0.0}
    try:
        if sys.platform.startswith("win"):
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                            ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong), ("f", ctypes.c_ulonglong)]
            s = MS()
            s.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            info["ram_gb"] = round(s.total / 2 ** 30, 1)
        elif sys.platform == "darwin":
            info["ram_gb"] = round(int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()) / 2 ** 30, 1)
        else:
            for line in open("/proc/meminfo"):
                if line.startswith("MemTotal"):
                    info["ram_gb"] = round(int(line.split()[1]) / 2 ** 20, 1)
                    break
    except Exception:
        pass
    info["vendor"] = ""
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=10)
            name, mem = out.strip().splitlines()[0].split(",")
            info["gpu"], info["vram_gb"], info["vendor"] = name.strip(), round(float(mem) / 1024, 1), "nvidia"
        except Exception:
            pass
    if not info["gpu"]:
        amd = amd_gpu()
        if amd:
            info["gpu"], info["vram_gb"], info["vendor"] = amd
    if sys.platform == "darwin" and not info["gpu"]:
        info["gpu"], info["vram_gb"], info["vendor"] = "Apple Silicon (shared memory)", round(info["ram_gb"] * 0.7, 1), "apple"
    info["backend"] = gpu_backend(info)
    return info


_HW = {}


def hardware_cached():
    import time
    if not _HW or time.time() - _HW["t"] > 120:
        _HW.update(t=time.time(), v=hardware())
    return _HW["v"]


def fit(gb, hw):
    need = gb * 1.25
    if hw["vram_gb"] and need <= hw["vram_gb"]:
        return "great"
    if hw["ram_gb"] and need <= hw["ram_gb"] * 0.6:
        return "ok"
    return "too big" if hw["ram_gb"] else "unknown"


def catalog():
    hw = hardware_cached()
    return {"hardware": hw, "models": [dict(m, fit=fit(m["gb"], hw), url="https://ollama.com/library/" + m["name"].split(":")[0]) for m in CATALOG],
            "library": "https://ollama.com/search", "gguf": "https://huggingface.co/models?library=gguf&sort=trending"}


def vtuple(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:3])


def get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Marchand"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(host):
    out = {"current": None, "latest": None, "update": False, "installed": bool(shutil.which("ollama")), "error": ""}
    try:
        out["current"] = json.loads(get(host.rstrip("/") + "/api/version", 4)).get("version")
    except Exception as ex:
        out["error"] = "Ollama is not running (%s)" % ex
    try:
        out["latest"] = json.loads(get("https://api.github.com/repos/ollama/ollama/releases/latest")).get("tag_name", "").lstrip("v")
    except Exception:
        out["latest"] = None
    if out["current"] and out["latest"]:
        out["update"] = vtuple(out["latest"]) > vtuple(out["current"])
    return out


def start_ollama():
    exe = shutil.which("ollama")
    if not exe:
        raise RuntimeError("Ollama is not installed. Use Update/Install in Models.")
    kw = {"creationflags": 0x00000008 | 0x00000200} if sys.platform.startswith("win") else {"start_new_session": True}
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


def update_stream(emit):
    if sys.platform.startswith("win"):
        url = "https://ollama.com/download/OllamaSetup.exe"
        dest = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
        emit("Downloading the latest installer...")
        req = urllib.request.Request(url, headers={"User-Agent": "Marchand"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                done += len(b)
                pct = int(100 * done / total) if total else 0
                if pct != last:
                    emit("Downloading... %d%%" % pct, pct)
                    last = pct
        emit("Installing (a progress window may appear)...")
        rc = subprocess.call([dest, "/SILENT", "/NORESTART"])
        emit("Installer finished (exit code %d). Ollama restarts by itself; use Refresh in a few seconds." % rc, 100)
    elif sys.platform == "darwin":
        if shutil.which("brew") and "ollama" in subprocess.run(["brew", "list"], capture_output=True, text=True).stdout:
            emit("Running: brew upgrade ollama")
            p = subprocess.Popen(["brew", "upgrade", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                emit(line.strip())
            p.wait()
        else:
            emit("Download the latest Ollama for macOS from https://ollama.com/download and replace the app, then restart it.")
    else:
        if os.geteuid() == 0 and shutil.which("curl"):
            emit("Running the official install script...")
            p = subprocess.Popen("curl -fsSL https://ollama.com/install.sh | sh", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                emit(line.strip())
            p.wait()
        else:
            emit("Run this in a terminal (it needs sudo):  curl -fsSL https://ollama.com/install.sh | sh")
