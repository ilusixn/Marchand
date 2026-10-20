import base64, io, json, threading, time, http.server
from PIL import Image
LOG = {"txt2img": [], "img2img": [], "comfy_prompts": [], "interrupts": 0, "options": []}
def png(color=(40, 90, 160), size=(64, 64)):
    b = io.BytesIO(); Image.new("RGB", size, color).save(b, "PNG"); return b.getvalue()
class Base(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def j(self, o, code=200):
        d = json.dumps(o).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def raw(self, d, ctype="image/png"):
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0); return json.loads(self.rfile.read(n) or b"{}")
class Forge(Base):
    state = {"ckpt": "mock_v1.safetensors [abc]", "t0": 0, "interrupted": False}
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/sdapi/v1/sd-models": return self.j([{"title": "mock_v1.safetensors [abc]", "model_name": "mock_v1"}, {"title": "mock_v2.safetensors [def]", "model_name": "mock_v2"}])
        if p == "/sdapi/v1/samplers": return self.j([{"name": "Euler a"}, {"name": "DPM++ 2M"}])
        if p == "/sdapi/v1/options": return self.j({"sd_model_checkpoint": self.state["ckpt"]})
        if p == "/sdapi/v1/progress":
            el = time.time() - self.state["t0"]; return self.j({"progress": min(0.95, el / 2.0)})
        self.j({"error": "nf"}, 404)
    def do_POST(self):
        b = self.body(); p = self.path
        if p == "/sdapi/v1/options": LOG["options"].append(b); self.state["ckpt"] = b.get("sd_model_checkpoint", self.state["ckpt"]); return self.j({})
        if p in ("/sdapi/v1/txt2img", "/sdapi/v1/img2img"):
            LOG["txt2img" if p.endswith("txt2img") else "img2img"].append(b)
            self.state["t0"] = time.time(); self.state["interrupted"] = False
            for _ in range(20):
                time.sleep(0.15)
                if self.state["interrupted"]: return self.j({"images": []})
            n = b.get("n_iter", 1)
            return self.j({"images": [base64.b64encode(png((30 * i + 60, 100, 150))).decode() for i in range(n)], "info": "{}"})
        if p == "/sdapi/v1/interrupt": self.state["interrupted"] = True; LOG["interrupts"] += 1; return self.j({})
        self.j({}, 404)
class NoApi(Base):
    def do_GET(self): self.j({"detail": "Not Found"}, 404)
class Comfy(Base):
    jobs = {}
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/system_stats": return self.j({"system": {"os": "posix"}})
        if p == "/object_info/CheckpointLoaderSimple": return self.j({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["sd_xl.safetensors", "flux.safetensors"]]}}}})
        if p == "/object_info/KSampler": return self.j({"KSampler": {"input": {"required": {"sampler_name": [["euler", "dpmpp_2m"]], "scheduler": [["normal", "karras"]]}}}})
        if p.startswith("/history/"):
            pid = p.split("/")[-1]; job = self.jobs.get(pid)
            if not job or time.time() - job["t"] < 1.5: return self.j({})
            return self.j({pid: {"status": {"status_str": "success", "completed": True}, "outputs": {"9": {"images": [{"filename": "m_%d.png" % i, "subfolder": "", "type": "output"} for i in range(job["n"])]}}}})
        if p == "/view": return self.raw(png((160, 60, 90)))
        self.j({}, 404)
    def do_POST(self):
        b = self.body()
        if self.path == "/prompt":
            LOG["comfy_prompts"].append(b["prompt"]); pid = "p%d" % len(LOG["comfy_prompts"])
            n = 1
            for node in b["prompt"].values():
                if node.get("class_type") == "EmptyLatentImage": n = node["inputs"]["batch_size"]
            self.jobs[pid] = {"t": time.time(), "n": n}; return self.j({"prompt_id": pid})
        if self.path == "/interrupt": LOG["interrupts"] += 1; return self.j({})
        self.j({}, 404)
class LMStudio(Base):
    def do_GET(self):
        if self.path == "/v1/models": return self.j({"data": [{"id": "lmstudio-model"}]})
        self.j({}, 404)
    def do_POST(self):
        self.body(); self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: ' + json.dumps({"choices": [{"delta": {"content": "hello from lmstudio"}}]}).encode() + b"\n\ndata: [DONE]\n\n")
class Debug(Base):
    def do_GET(self):
        if self.path == "/log": return self.j(LOG)
        self.j({})
def serve(port, cls):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", port), cls); threading.Thread(target=s.serve_forever, daemon=True).start()
if __name__ == "__main__":
    serve(7860, Forge); serve(7861, NoApi); serve(8188, Comfy); serve(1234, LMStudio)
    http.server.ThreadingHTTPServer(("127.0.0.1", 11557), Debug).serve_forever()
