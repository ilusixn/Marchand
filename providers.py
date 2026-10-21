import base64
import json
import re
import urllib.error
import urllib.request

OPENAI_COMPAT = {
    "xai": ("Grok (xAI)", "https://api.x.ai/v1"),
    "openai": ("OpenAI", "https://api.openai.com/v1"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1"),
    "gemini": ("Gemini (Google)", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com"),
    "groq": ("Groq", "https://api.groq.com/openai/v1"),
    "mistral": ("Mistral", "https://api.mistral.ai/v1"),
    "together": ("Together AI", "https://api.together.xyz/v1"),
    "fireworks": ("Fireworks AI", "https://api.fireworks.ai/inference/v1"),
    "cerebras": ("Cerebras", "https://api.cerebras.ai/v1"),
    "nvidia": ("NVIDIA NIM", "https://integrate.api.nvidia.com/v1"),
    "huggingface": ("Hugging Face", "https://router.huggingface.co/v1"),
    "perplexity": ("Perplexity", "https://api.perplexity.ai"),
    "cohere": ("Cohere", "https://api.cohere.ai/compatibility/v1"),
    "github": ("GitHub Models", "https://models.github.ai/inference"),
    "custom": ("Custom server", ""),
}
LOCAL_SERVERS = {
    "lmstudio": ("LM Studio", "http://127.0.0.1:1234/v1"),
    "jan": ("Jan", "http://127.0.0.1:1337/v1"),
    "koboldcpp": ("KoboldCpp", "http://127.0.0.1:5001/v1"),
    "textgen": ("text-generation-webui", "http://127.0.0.1:5000/v1"),
    "llamacpp": ("llama.cpp server", "http://127.0.0.1:8080/v1"),
    "vllm": ("vLLM", "http://127.0.0.1:8000/v1"),
    "gpt4all": ("GPT4All", "http://127.0.0.1:4891/v1"),
    "localai": ("LocalAI", "http://127.0.0.1:8081/v1"),
}
OPENAI_COMPAT.update(LOCAL_SERVERS)
LABELS = {"ollama": "Local (Ollama)", "anthropic": "Claude API (Anthropic key)", "claude-code": "Claude (your subscription)"}
LABELS.update({k: v[0] for k, v in OPENAI_COMPAT.items()})
FALLBACK_MODELS = {
    "together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-Coder-32B-Instruct"],
    "fireworks": ["accounts/fireworks/models/llama-v3p3-70b-instruct"],
    "cerebras": ["llama3.3-70b"],
    "perplexity": ["sonar", "sonar-pro"],
    "mistral": ["mistral-large-latest", "codestral-latest"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "groq": ["llama-3.3-70b-versatile"],
    "anthropic": ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
    "xai": ["grok-4", "grok-code-fast-1"],
    "openai": ["gpt-5", "gpt-5-codex", "gpt-5-mini"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
}
SEP = "::"


def split_model(model_id):
    if SEP in (model_id or ""):
        p, m = model_id.split(SEP, 1)
        return p, m
    return "ollama", model_id


def provider_cfg(settings, provider):
    pc = dict((settings.get("providers") or {}).get(provider) or {})
    if provider == "anthropic":
        pc.setdefault("base", "https://api.anthropic.com")
    elif provider in OPENAI_COMPAT:
        pc["base"] = pc.get("base") or OPENAI_COMPAT[provider][1]
    return pc


def http_json(url, headers=None, body=None, timeout=30):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def list_models(settings, provider):
    pc = provider_cfg(settings, provider)
    if not pc.get("key") and provider != "custom" and provider not in LOCAL_SERVERS:
        return []
    if provider in LOCAL_SERVERS and not pc.get("enabled"):
        return []
    try:
        if provider == "anthropic":
            data = http_json(pc["base"] + "/v1/models?limit=100", {"x-api-key": pc["key"], "anthropic-version": "2023-06-01"})
            ids = [m["id"] for m in data.get("data", [])]
        else:
            hdr = {"Authorization": "Bearer " + pc["key"]} if pc.get("key") else {}
            data = http_json(pc["base"].rstrip("/") + "/models", hdr)
            ids = [m["id"] for m in data.get("data", [])]
        ids = [i.replace("models/", "") for i in ids]
        return sorted(ids) or FALLBACK_MODELS.get(provider, [])
    except Exception:
        return FALLBACK_MODELS.get(provider, [])


def err_text(ex):
    if isinstance(ex, urllib.error.HTTPError):
        try:
            return "HTTP %d: %s" % (ex.code, ex.read().decode(errors="replace")[:400])
        except Exception:
            return "HTTP %d" % ex.code
    return str(ex)


def parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def sse_lines(resp, cancel):
    for raw in resp:
        if cancel.is_set():
            from engine import Cancelled
            raise Cancelled()
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            yield line[5:].strip()


def tools_openai(tools):
    return tools


def tools_anthropic(tools):
    return [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
             "input_schema": t["function"].get("parameters") or {"type": "object", "properties": {}}} for t in tools]


def to_openai_messages(messages):
    out, pending = [], []
    for i, m in enumerate(messages):
        role = m["role"]
        if role == "assistant":
            msg = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                pending = []
                msg["tool_calls"] = []
                for k, c in enumerate(m["tool_calls"]):
                    cid = "call_%d_%d" % (i, k)
                    pending.append(cid)
                    fn = c.get("function", {})
                    a = fn.get("arguments", {})
                    msg["tool_calls"].append({"id": cid, "type": "function", "function": {
                        "name": fn.get("name", ""), "arguments": a if isinstance(a, str) else json.dumps(a)}})
            out.append(msg)
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": pending.pop(0) if pending else "call_x", "content": m.get("content", "")})
        elif role == "user" and m.get("images"):
            parts = [{"type": "text", "text": m.get("content", "")}]
            parts += [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}} for b in m["images"]]
            out.append({"role": "user", "content": parts})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


def to_anthropic_messages(messages):
    system, out, pending = "", [], []
    for i, m in enumerate(messages):
        role = m["role"]
        if role == "system":
            system += (m.get("content") or "") + "\n"
        elif role == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            pending = []
            for k, c in enumerate(m.get("tool_calls") or []):
                cid = "toolu_%d_%d" % (i, k)
                pending.append(cid)
                fn = c.get("function", {})
                blocks.append({"type": "tool_use", "id": cid, "name": fn.get("name", ""), "input": parse_args(fn.get("arguments"))})
            if blocks:
                out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": pending.pop(0) if pending else "toolu_x", "content": m.get("content", "")}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            blocks = [{"type": "text", "text": m.get("content", "")}]
            blocks += [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b}} for b in m.get("images") or []]
            out.append({"role": "user", "content": blocks})
    return system.strip(), out


def stream_openai(pc, model, messages, tools, opts, on_piece, cancel):
    body = {"model": model, "messages": to_openai_messages(messages), "stream": True, "temperature": opts.get("temperature", 0.2)}
    if tools:
        body["tools"] = tools_openai(tools)
    hdr = {"Authorization": "Bearer " + pc.get("key", "")} if pc.get("key") else {}
    req = urllib.request.Request(pc["base"].rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 dict({"Content-Type": "application/json"}, **hdr))
    content, calls = "", {}
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            for data in sse_lines(resp, cancel):
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                for ch in chunk.get("choices", []):
                    d = ch.get("delta", {})
                    if d.get("reasoning_content"):
                        on_piece("thinking", d["reasoning_content"])
                    if d.get("content"):
                        content += d["content"]
                        on_piece("token", d["content"])
                    for tc in d.get("tool_calls") or []:
                        slot = calls.setdefault(tc.get("index", 0), {"name": "", "args": ""})
                        fn = tc.get("function", {})
                        slot["name"] += fn.get("name") or ""
                        slot["args"] += fn.get("arguments") or ""
    except urllib.error.URLError as ex:
        raise RuntimeError(err_text(ex))
    return content, [{"function": {"name": s["name"], "arguments": parse_args(s["args"])}} for _, s in sorted(calls.items())]


def stream_anthropic(pc, model, messages, tools, opts, on_piece, cancel):
    system, msgs = to_anthropic_messages(messages)
    body = {"model": model, "max_tokens": int(opts.get("max_tokens", 8192)), "messages": msgs, "stream": True,
            "temperature": opts.get("temperature", 0.2)}
    if system:
        body["system"] = system
    if tools:
        body["tools"] = tools_anthropic(tools)
    req = urllib.request.Request(pc["base"].rstrip("/") + "/v1/messages", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "x-api-key": pc.get("key", ""), "anthropic-version": "2023-06-01"})
    content, blocks = "", {}
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            for data in sse_lines(resp, cancel):
                ev = json.loads(data)
                t = ev.get("type")
                if t == "content_block_start":
                    cb = ev.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        blocks[ev["index"]] = {"name": cb.get("name", ""), "args": ""}
                elif t == "content_block_delta":
                    d = ev.get("delta", {})
                    if d.get("type") == "text_delta":
                        content += d["text"]
                        on_piece("token", d["text"])
                    elif d.get("type") == "thinking_delta":
                        on_piece("thinking", d.get("thinking", ""))
                    elif d.get("type") == "input_json_delta" and ev["index"] in blocks:
                        blocks[ev["index"]]["args"] += d.get("partial_json", "")
                elif t == "error":
                    raise RuntimeError(ev.get("error", {}).get("message", "Anthropic error"))
    except urllib.error.URLError as ex:
        raise RuntimeError(err_text(ex))
    return content, [{"function": {"name": b["name"], "arguments": parse_args(b["args"])}} for _, b in sorted(blocks.items())]


def stream_ollama(pc, model, messages, tools, opts, on_piece, cancel):
    from engine import ollama_stream
    body = {"model": model, "messages": messages, "stream": True,
            "options": {"num_ctx": opts.get("num_ctx", 16384), "temperature": opts.get("temperature", 0.2)}}
    if tools:
        body["tools"] = tools
    return ollama_stream(pc["base"], body, on_piece, cancel)


def chat_stream(settings, model_id, messages, tools, opts, on_piece, cancel):
    provider, model = split_model(model_id)
    if provider == "claude-code":
        import claude_code
        return claude_code.chat_stream(model, messages, on_piece, cancel, effort=opts.get("effort"))
    if provider == "ollama":
        return stream_ollama({"base": settings["host"]}, model, messages, tools, opts, on_piece, cancel)
    pc = provider_cfg(settings, provider)
    if provider in LOCAL_SERVERS:
        if not pc.get("enabled"):
            raise RuntimeError("%s is not enabled. Turn it on in Models > Cloud and local servers." % LABELS.get(provider, provider))
    elif provider != "custom" and not pc.get("key"):
        raise RuntimeError("No API key for %s. Add one in Models > Cloud and local servers." % LABELS.get(provider, provider))
    fn = stream_anthropic if provider == "anthropic" else stream_openai
    return fn(pc, model, messages, tools, opts, on_piece, cancel)


def chat_once(settings, model_id, messages, opts=None):
    import threading
    content, _ = chat_stream(settings, model_id, messages, None, opts or {}, lambda k, t: None, threading.Event())
    return content
