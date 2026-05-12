#!/usr/bin/env python3
"""
Locali — Cross-platform launcher
Starts llama.cpp as a private backend, serves its own control HTTP server,
and opens the offline chat UI. Zero host modification.
"""

import os, sys, json, platform, subprocess, threading, webbrowser
import time, signal, argparse, http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Colour helpers (disabled on Windows CMD if no ANSI support) ────────────
_ANSI = sys.platform != "win32" or "WT_SESSION" in os.environ

class C:
    GREEN  = "\033[92m" if _ANSI else ""
    YELLOW = "\033[93m" if _ANSI else ""
    RED    = "\033[91m" if _ANSI else ""
    CYAN   = "\033[96m" if _ANSI else ""
    BOLD   = "\033[1m"  if _ANSI else ""
    RESET  = "\033[0m"  if _ANSI else ""

def ok(m):   print(f"  {C.GREEN}✓{C.RESET} {m}")
def warn(m): print(f"  {C.YELLOW}⚠{C.RESET} {m}")
def info(m): print(f"  {C.CYAN}→{C.RESET} {m}")
def die(m):  print(f"  {C.RED}✗{C.RESET} {m}"); sys.exit(1)

BANNER = f"""{C.BOLD}{C.CYAN}
  ╔══════════════════════════════════════════════╗
  ║            🧠  Locali  v1.0                 ║
  ║   Local AI · No internet · No traces        ║
  ╚══════════════════════════════════════════════╝
{C.RESET}"""

# ── Locate root ────────────────────────────────────────────────────────────
def get_root(arg_root=None):
    root = Path(arg_root).resolve() if arg_root else Path(__file__).parent.parent.resolve()
    if not (root / "config.json").exists():
        die(f"config.json not found at {root}. Run from the USB drive.")
    return root

# ── Config ────────────────────────────────────────────────────────────────
def load_cfg(root):
    with open(root / "config.json", encoding="utf-8") as f:
        return json.load(f)

def save_cfg(root, cfg):
    with open(root / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")

# ── Model helpers ─────────────────────────────────────────────────────────
def norm(name):
    return Path(name).name  # strip any directory prefix

def discover_models(root, cfg):
    """Return all .gguf files present in models/, preserving config order."""
    listed = [norm(m) for m in (cfg.get("models") or []) if m]
    found  = {p.name for p in (root / "models").glob("*.gguf")}
    # listed first (if they exist), then any extras on disk
    ordered = [m for m in listed if m in found]
    for m in sorted(found):
        if m not in ordered:
            ordered.append(m)
    return ordered

# ── OS / binary ──────────────────────────────────────────────────────────
def detect_os():
    s = platform.system()
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(s) or die(f"Unsupported OS: {s}")

def get_binary(root, os_name):
    arch = platform.machine().lower()
    candidates = {
        "windows": [root/"bin"/"windows"/"llama-server.exe"],
        "mac":     [root/"bin"/"mac"/"llama-server",
                    root/"bin"/"mac"/"llama-server-x64"] if arch != "arm64"
                   else [root/"bin"/"mac"/"llama-server"],
        "linux":   [root/"bin"/"linux"/"llama-server"],
    }[os_name]
    for b in candidates:
        if b.exists():
            return b
    die(f"Binary not found at {candidates[0]}.\nRe-run the setup script to download it.")

def get_model_path(root, model_name):
    p = root / "models" / norm(model_name)
    if not p.exists():
        die(f"Model not found: {p}\nRe-run setup or update 'model' in config.json.")
    return p

# ── Port helpers ──────────────────────────────────────────────────────────
def port_free(port):
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0

def wait_backend(port, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            c.request("GET", "/health")
            if c.getresponse().status == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False

# ── Resolve runtime settings ──────────────────────────────────────────────
def resolve_threads(cfg):
    v = cfg.get("threads", "auto")
    if v == "auto":
        import multiprocessing
        return max(1, multiprocessing.cpu_count() - 1)
    return int(v)

def resolve_ngl(cfg):
    v = cfg.get("gpu_layers", "auto")
    return 0 if v == "auto" else int(v)

# ── Data persistence (stays on USB) ──────────────────────────────────────
def load_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

# ── Backend controller ────────────────────────────────────────────────────
class Backend:
    def __init__(self, root, os_name, cfg):
        self.root     = root
        self.os_name  = os_name
        self.cfg      = cfg
        self.data_dir = root / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.memory  = load_json(self.data_dir / "memory.json",  {"conversations": []})
        self.profile = load_json(self.data_dir / "profile.json", {
            "name": "", "role": "", "preferences": []
        })
        self.ctrl_port    = int(cfg.get("port", 8080))
        self.backend_port = self.ctrl_port + 1
        self.process      = None
        self.current      = norm(cfg.get("model", ""))
        self._lock        = threading.Lock()

    # ── Environment for subprocess ────────────────────────
    def _env(self):
        env = os.environ.copy()
        bin_dir = str(get_binary(self.root, self.os_name).parent.resolve())
        if self.os_name == "windows":
            tmp = self.root / "tmp"
            tmp.mkdir(exist_ok=True)
            env["TEMP"] = env["TMP"] = str(tmp)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        elif self.os_name == "mac":
            env["DYLD_LIBRARY_PATH"] = bin_dir + (":" + env["DYLD_LIBRARY_PATH"] if env.get("DYLD_LIBRARY_PATH") else "")
        else:
            env["LD_LIBRARY_PATH"] = bin_dir + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        return env

    # ── Start llama-server ────────────────────────────────
    def start(self, model_name=None):
        with self._lock:
            if model_name:
                self.current = norm(model_name)
                self.cfg["model"] = self.current
                save_cfg(self.root, self.cfg)

            self._stop_process()

            if not port_free(self.backend_port):
                die(f"Backend port {self.backend_port} already in use. Change 'port' in config.json.")

            binary = get_binary(self.root, self.os_name)
            mpath  = get_model_path(self.root, self.current)

            cmd = [
                str(binary),
                "--model",        str(mpath),
                "--host",         "127.0.0.1",
                "--port",         str(self.backend_port),
                "--ctx-size",     str(self.cfg.get("context_size", 2048)),
                "--threads",      str(resolve_threads(self.cfg)),
                "--n-gpu-layers", str(resolve_ngl(self.cfg)),
                "--temp",         str(self.cfg.get("temperature", 0.7)),
                "--log-disable",
            ]

            self.process = subprocess.Popen(
                cmd, env=self._env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if not wait_backend(self.backend_port, timeout=90):
            self._stop_process()
            die("llama-server failed to start. Check your model file and available RAM.")

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def stop(self):
        with self._lock:
            self._stop_process()

    # ── Model switching ───────────────────────────────────
    def switch_model(self, model_name):
        model_name = norm(model_name)
        available = discover_models(self.root, self.cfg)
        if model_name not in available:
            raise ValueError(f"Model not installed: {model_name}")
        self.start(model_name)
        return self.state()

    def state(self):
        return {
            "current_model":    self.current,
            "available_models": discover_models(self.root, self.cfg),
            "ctrl_port":        self.ctrl_port,
        }

    # ── LLM calls (non-streaming) ─────────────────────────
    def _post(self, payload, timeout=120):
        body = json.dumps(payload).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.backend_port, timeout=timeout)
        conn.request("POST", "/v1/chat/completions", body,
                     {"Content-Type": "application/json", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        raw  = resp.read().decode()
        if resp.status != 200:
            raise RuntimeError(raw or f"backend HTTP {resp.status}")
        return json.loads(raw)

    def _system_messages(self):
        msgs = [{"role": "system", "content":
            "You are Locali, a private offline AI assistant running from the user's USB drive. "
            "Never claim to send data externally. Be concise and helpful."}]
        if self.profile.get("name"):
            msgs.append({"role": "system", "content": f"User name: {self.profile['name']}"})
        if self.profile.get("role"):
            msgs.append({"role": "system", "content": f"Context: {self.profile['role']}"})
        recent = [c.get("summary","") for c in self.memory["conversations"][-5:] if c.get("summary")]
        if recent:
            msgs.append({"role": "system", "content": "Recent topics: " + " | ".join(recent)})
        return msgs

    def chat(self, messages, temperature=0.7, max_tokens=1024):
        full = self._system_messages() + messages
        resp = self._post({"model": self.current, "messages": full,
                           "temperature": temperature, "max_tokens": max_tokens, "stream": False})
        content = resp["choices"][0]["message"]["content"]
        # Save summary to memory
        if messages:
            summary = messages[-1]["content"][:120]
            self.memory["conversations"].append({"summary": summary, "reply": content[:120],
                                                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            self.memory["conversations"] = self.memory["conversations"][-50:]
            save_json(self.data_dir / "memory.json", self.memory)
        return resp

    def chat_stream(self, messages, temperature=0.7, max_tokens=1024):
        full = self._system_messages() + messages
        payload = {"model": self.current, "messages": full,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        body = json.dumps(payload).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.backend_port, timeout=120)
        conn.request("POST", "/v1/chat/completions", body,
                     {"Content-Type": "application/json", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(resp.read().decode() or f"backend HTTP {resp.status}")
        chunks = []
        while True:
            line = resp.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").strip()
            if not text.startswith("data: "):
                continue
            data = text[6:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                if delta:
                    chunks.append(delta)
                    yield delta
            except Exception:
                continue
        # persist summary
        if messages and chunks:
            content = "".join(chunks)
            self.memory["conversations"].append({
                "summary": messages[-1]["content"][:120],
                "reply":   content[:120],
                "ts":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            self.memory["conversations"] = self.memory["conversations"][-50:]
            save_json(self.data_dir / "memory.json", self.memory)

    # ── Agent ─────────────────────────────────────────────
    def plan(self, task):
        system = (
            "You are a cautious local agent. "
            "Respond ONLY with valid JSON, no markdown fences. "
            "Use type 'answer' for tasks you can solve with text. "
            "Use type 'command' for tasks needing a shell command. "
            "For commands include: type, summary, command, cwd (use '.'), explanation."
        )
        resp = self._post({"model": self.current, "stream": False, "temperature": 0.1, "max_tokens": 512,
                           "messages": [{"role":"system","content":system}, {"role":"user","content":task}]})
        raw = resp["choices"][0]["message"]["content"].strip()
        # strip accidental code fences
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        return json.loads(raw)

    def execute(self, command, cwd=None):
        safe_root = self.root.resolve()
        cwd_path  = (safe_root / (cwd or ".")).resolve()
        # SAFETY: never execute outside USB root
        if not str(cwd_path).startswith(str(safe_root)):
            raise RuntimeError("Refused: cwd is outside the USB drive.")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=str(cwd_path), timeout=60,
            executable=(None if sys.platform == "win32" else "/bin/sh"),
        )
        return {"command": command, "cwd": str(cwd_path),
                "exit_code": result.returncode,
                "stdout": result.stdout[-8000:],
                "stderr": result.stderr[-2000:]}

# ── HTTP server ───────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_): pass   # silence access log

    @property
    def backend(self): return self.server.backend

    # helpers
    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path in ("/", "/index.html"):
            ui = self.backend.root / "ui" / "index.html"
            self._html(ui.read_text(encoding="utf-8"))
            return

        routes = {
            "/health":      lambda: {"ok": True},
            "/api/state":   lambda: self.backend.state(),
            "/api/models":  lambda: {"current": self.backend.current,
                                     "available": discover_models(self.backend.root, self.backend.cfg)},
            "/api/profile": lambda: {"ok": True, "profile": self.backend.profile},
        }
        if path in routes:
            self._json(routes[path]())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/select-model":
            try:
                name = self._body_json().get("model","").strip()
                if not name: raise ValueError("model required")
                state = self.backend.switch_model(name)
                self._json({"ok": True, "state": state})
            except Exception as e:
                self._json({"error": str(e)}, 400)
            return

        if path == "/api/profile":
            try:
                p = self._body_json()
                self.backend.profile.update({k: p[k] for k in ("name","role","preferences") if k in p})
                save_json(self.backend.data_dir / "profile.json", self.backend.profile)
                self._json({"ok": True, "profile": self.backend.profile})
            except Exception as e:
                self._json({"error": str(e)}, 400)
            return

        if path == "/api/chat":
            try:
                body    = self._body_json()
                msgs    = body.get("messages", [])
                temp    = float(body.get("temperature", 0.7))
                maxtok  = int(body.get("max_tokens", 1024))
                stream  = body.get("stream") is True

                if not msgs:
                    self._json({"error": "messages required"}, 400); return

                if stream:
                    self.send_response(200)
                    self.send_header("Content-Type",  "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection",    "keep-alive")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    try:
                        for chunk in self.backend.chat_stream(msgs, temp, maxtok):
                            data = json.dumps({"choices":[{"delta":{"content":chunk}}]})
                            self.wfile.write(f"data: {data}\n\n".encode())
                            self.wfile.flush()
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                    except Exception as e:
                        err_data = json.dumps({"error": str(e)})
                        self.wfile.write(f"data: {err_data}\n\n".encode())
                    return

                resp = self.backend.chat(msgs, temp, maxtok)
                self._json({"ok": True, "response": resp})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/agent/plan":
            try:
                task = self._body_json().get("task","").strip()
                if not task: raise ValueError("task required")
                plan = self.backend.plan(task)
                self._json({"ok": True, "plan": plan})
            except json.JSONDecodeError:
                self._json({"error": "Model returned invalid JSON for plan"}, 500)
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/agent/execute":
            try:
                body = self._body_json()
                if body.get("approved") is not True:
                    self._json({"error": "approval required"}, 400); return
                cmd = body.get("command","").strip()
                if not cmd: raise ValueError("command required")
                result = self.backend.execute(cmd, body.get("cwd"))
                self._json({"ok": True, "result": result})
            except Exception as e:
                self._json({"error": str(e)}, 400)
            return

        self._json({"error": "not found"}, 404)

# ── Main ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", help="USB root path (auto-detected if omitted)")
    args = parser.parse_args()

    print(BANNER)

    os_name = detect_os()
    root    = get_root(args.root)
    cfg     = load_cfg(root)
    backend = Backend(root, os_name, cfg)

    info(f"OS: {os_name.capitalize()}")
    info(f"Root: {root}")
    info(f"Model: {backend.current}")

    ctrl_port = backend.ctrl_port
    back_port = backend.backend_port

    print()
    for port, label in [(ctrl_port, "control"), (back_port, "backend")]:
        if not port_free(port):
            die(f"Port {port} ({label}) is in use. Change 'port' in config.json.")
    ok(f"Ports free — control: {ctrl_port}  backend: {back_port}")

    binary = get_binary(root, os_name)
    ok(f"Binary: {binary.relative_to(root)}")

    models = discover_models(root, cfg)
    if not models:
        die("No .gguf model files found in models/. Re-run setup.")
    ok(f"Model: {backend.current}")
    if len(models) > 1:
        info(f"All installed: {', '.join(models)}")

    print(f"\n  {C.BOLD}Starting backend...{C.RESET}")
    info(f"Threads: {resolve_threads(cfg)}  GPU layers: {resolve_ngl(cfg)}")

    backend.start()

    # ── HTTP control server ──────────────────────────────
    class LS(ThreadingHTTPServer):
        allow_reuse_address = True
    server = LS(("127.0.0.1", ctrl_port), Handler)
    server.backend = backend

    def shutdown(sig, frame):
        print(f"\n\n  {C.YELLOW}Shutting down...{C.RESET}")
        backend.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    ok("Backend ready!")
    print(f"\n  {C.BOLD}{C.GREEN}🚀 Locali is running!{C.RESET}")
    print(f"  {C.CYAN}Open:{C.RESET}  http://127.0.0.1:{ctrl_port}")
    print(f"\n  Press Ctrl+C to stop.\n")

    if cfg.get("open_browser", True):
        threading.Thread(target=webbrowser.open,
                         args=(f"http://127.0.0.1:{ctrl_port}",), daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        backend.stop()
        ok("Stopped. USB safe to remove.")

if __name__ == "__main__":
    main()
