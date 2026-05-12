#!/usr/bin/env python3
"""
Locali — Cross-platform launcher
Detects OS, picks the right binary, and starts the llama.cpp server.
Works on Windows, Linux, and macOS with zero host modification.
"""

import os
import sys
import json
import platform
import subprocess
import threading
import webbrowser
import time
import signal
import argparse
import http.client
import shlex
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ─── Colors ───────────────────────────────────────────────
class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def ok(msg):   print(f"  {C.GREEN}✓{C.RESET} {msg}")
def warn(msg): print(f"  {C.YELLOW}⚠{C.RESET} {msg}")
def err(msg):  print(f"  {C.RED}✗{C.RESET} {msg}"); sys.exit(1)
def info(msg): print(f"  {C.CYAN}→{C.RESET} {msg}")


BANNER = f"""
{C.BOLD}{C.CYAN}
  ╔══════════════════════════════════════════════╗
  ║         🧠  Locali  v1.0                 ║
  ║    Local AI — No internet — No traces       ║
  ╚══════════════════════════════════════════════╝
{C.RESET}"""


def detect_os():
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "mac"
    elif system == "Linux":
        return "linux"
    else:
        err(f"Unsupported OS: {system}")


def get_root_dir(args_root=None):
    """Find the root of the USB drive (where config.json lives)."""
    if args_root:
        root = Path(args_root)
    else:
        # Script lives at <root>/launcher/launch.py
        root = Path(__file__).parent.parent.resolve()

    if not (root / "config.json").exists():
        err(f"config.json not found at {root}. Are you running from the USB drive?")
    return root


def load_config(root):
    config_path = root / "config.json"
    with open(config_path) as f:
        return json.load(f)


def save_config(root, config):
    config_path = root / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def ensure_data_dir(root):
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def load_json_file(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json_file(path, payload):
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def discover_models(root, config):
    configured = config.get("models") or []
    if isinstance(configured, str):
        configured = [configured]

    discovered = []
    for model_name in configured:
        if model_name and (root / "models" / model_name).exists():
            discovered.append(model_name)

    for path in (root / "models").glob("*.gguf"):
        if path.name not in discovered:
            discovered.append(path.name)

    return sorted(discovered)


def normalize_model_name(model_name):
    return Path(model_name).name


def get_binary_path(root, os_name):
    arch = platform.machine().lower()
    candidates = []

    if os_name == "windows":
        candidates = [
            root / "bin" / "windows" / "llama-server.exe",
            root / "bin" / "windows-x64" / "llama-server.exe",
        ]
    elif os_name == "mac":
        if arch in ("arm64", "aarch64"):
            candidates = [
                root / "bin" / "mac-arm64" / "llama-server",
                root / "bin" / "mac" / "llama-server",
            ]
        else:
            candidates = [
                root / "bin" / "mac-x64" / "llama-server",
                root / "bin" / "mac" / "llama-server",
            ]
    else:
        candidates = [
            root / "bin" / "linux-x64" / "llama-server",
            root / "bin" / "linux" / "llama-server",
        ]

    for binary in candidates:
        if binary.exists():
            return binary

    binary = candidates[0]
    err(
        f"Binary not found: {binary}\n"
        f"  Run setup again so the matching platform binary is installed."
    )


def get_model_path(root, model_name):
    model_path = root / "models" / normalize_model_name(model_name)
    if not model_path.exists():
        err(
            f"Model not found: {model_path}\n"
            f"  Re-run the setup script to download the model.\n"
            f"  Or update 'model' in config.json to match your GGUF filename."
        )
    return model_path


def backend_port_for(config):
    return int(config.get("port", 8080)) + 1


def resolve_threads(config):
    val = config.get("threads", "auto")
    if val == "auto":
        import multiprocessing
        return max(1, multiprocessing.cpu_count() - 1)
    return int(val)


def resolve_gpu_layers(config):
    val = config.get("gpu_layers", "auto")
    if val == "auto":
        # Default to 0 (CPU). Users with GPU can set manually.
        # llama.cpp will use GPU if layers > 0 and GPU is available.
        return 0
    return int(val)


def check_port(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(("127.0.0.1", port))
        return result != 0  # True = port is free


def backend_ready(port, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            if resp.status == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def build_command(binary, model_path, config, port):
    ctx     = config.get("context_size", 2048)
    temp    = config.get("temperature", 0.7)
    threads = resolve_threads(config)
    ngl     = resolve_gpu_layers(config)

    cmd = [
        str(binary),
        "--model", str(model_path),
        "--host", "127.0.0.1",     # localhost ONLY — never exposed to network
        "--port", str(port),
        "--ctx-size", str(ctx),
        "--threads", str(threads),
        "--n-gpu-layers", str(ngl),
        "--temp", str(temp),
        "--log-disable",            # suppress verbose llama.cpp logs
    ]

    return cmd


def extract_chat_content(response_json):
    try:
        return response_json["choices"][0]["message"]["content"]
    except Exception:
        return ""


def extract_stream_delta(chunk_json):
    try:
        return chunk_json["choices"][0]["delta"].get("content", "")
    except Exception:
        return ""


def parse_json_block(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    if "{" in content and "}" in content:
        start = content.find("{")
        end = content.rfind("}")
        content = content[start:end + 1]
    return json.loads(content)


class BackendController:
    def __init__(self, root, os_name, config):
        self.root = root
        self.os_name = os_name
        self.config = config
        self.data_dir = ensure_data_dir(root)
        self.memory_path = self.data_dir / "memory.json"
        self.profile_path = self.data_dir / "profile.json"
        self.memory = load_json_file(self.memory_path, {"conversations": []})
        self.profile = load_json_file(self.profile_path, {
            "name": "",
            "role": "Locali is a private offline assistant that keeps data local to the USB drive.",
            "preferences": [],
        })
        self.control_port = int(config.get("port", 8080))
        self.backend_port = backend_port_for(config)
        self.process = None
        self.current_model = normalize_model_name(config.get("model", ""))

    def _env(self):
        env = os.environ.copy()

        if self.os_name == "windows":
            usb_temp = self.root / "tmp"
            usb_temp.mkdir(exist_ok=True)
            env["TEMP"] = str(usb_temp)
            env["TMP"] = str(usb_temp)
            win_bin = str((self.get_binary().parent).resolve())
            env["PATH"] = win_bin + os.pathsep + env.get("PATH", "")

        binary_dir = str(self.get_binary().parent.resolve())
        if self.os_name == "mac":
            env["DYLD_LIBRARY_PATH"] = binary_dir + (":" + env.get("DYLD_LIBRARY_PATH", "") if env.get("DYLD_LIBRARY_PATH") else "")
        elif self.os_name == "linux":
            env["LD_LIBRARY_PATH"] = binary_dir + (":" + env.get("LD_LIBRARY_PATH", "") if env.get("LD_LIBRARY_PATH") else "")

        return env

    def get_binary(self):
        return get_binary_path(self.root, self.os_name)

    def start(self, model_name=None):
        if model_name:
            self.config["model"] = normalize_model_name(model_name)
            save_config(self.root, self.config)
        self.current_model = normalize_model_name(self.config.get("model", ""))

        if self.process and self.process.poll() is None:
            self.stop()

        if not check_port(self.backend_port):
            err(f"Backend port {self.backend_port} is already in use.")

        binary = self.get_binary()
        model_path = get_model_path(self.root, self.current_model)
        cmd = build_command(binary, model_path, self.config, self.backend_port)

        self.process = subprocess.Popen(
            cmd,
            env=self._env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not backend_ready(self.backend_port, timeout=60):
            stderr_output = ""
            if self.process.stderr is not None:
                try:
                    stderr_output, _ = self.process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    stderr_output, _ = self.process.communicate()

            message = "Backend failed to start."
            if stderr_output:
                message += f"\n\n{stderr_output.strip()}"
            err(message)

    def stop(self):
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def select_model(self, model_name):
        model_name = normalize_model_name(model_name)
        available = discover_models(self.root, self.config)
        if model_name not in available:
            err(f"Model not installed: {model_name}")

        self.config["model"] = model_name
        if "models" not in self.config or not self.config["models"]:
            self.config["models"] = available
        save_config(self.root, self.config)
        self.stop()
        self.start(model_name)
        return self.state()

    def state(self):
        return {
            "current_model": self.current_model,
            "available_models": discover_models(self.root, self.config),
            "control_port": self.control_port,
            "profile": self.profile,
        }

    def chat_completion(self, messages, temperature=0.2, max_tokens=512):
        payload = {
            "model": self.current_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        body = json.dumps(payload)
        conn = http.client.HTTPConnection("127.0.0.1", self.backend_port, timeout=120)
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        if resp.status != 200:
            raise RuntimeError(raw or f"backend returned HTTP {resp.status}")
        return json.loads(raw)

    def build_chat_messages(self, user_messages):
        system_prompt = (
            "You are Locali, a private offline assistant running on the user's USB drive. "
            "Never claim to send data to any cloud service. Use the user's profile and memory when helpful."
        )

        profile_bits = []
        if self.profile.get("name"):
            profile_bits.append(f"name: {self.profile['name']}")
        if self.profile.get("role"):
            profile_bits.append(f"role: {self.profile['role']}")
        if self.profile.get("preferences"):
            prefs = ", ".join(str(item) for item in self.profile.get("preferences", []) if item)
            if prefs:
                profile_bits.append(f"preferences: {prefs}")

        memory_summary = []
        for item in self.memory.get("conversations", [])[-5:]:
            if item.get("messages"):
                last_user = next(
                    (msg.get("content", "") for msg in reversed(item["messages"]) if msg.get("role") == "user"),
                    "",
                )
                if last_user:
                    memory_summary.append(last_user[:200])

        messages = [{"role": "system", "content": system_prompt}]
        if profile_bits:
            messages.append({"role": "system", "content": "User profile: " + " | ".join(profile_bits)})
        if memory_summary:
            messages.append({"role": "system", "content": "Recent memory: " + " || ".join(memory_summary)})
        messages.extend(user_messages)
        return messages

    def remember_chat(self, messages, reply):
        conversation = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": self.current_model,
            "messages": messages[-12:],
            "reply": reply,
        }
        conversations = self.memory.setdefault("conversations", [])
        conversations.append(conversation)
        conversations[:] = conversations[-50:]
        save_json_file(self.memory_path, self.memory)

    def chat(self, messages, temperature=0.7, max_tokens=512):
        response = self.chat_completion(
            self.build_chat_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        reply = extract_chat_content(response)
        if reply:
            self.remember_chat(messages, reply)
        return response

    def chat_stream(self, messages, temperature=0.7, max_tokens=512):
        payload = {
            "model": self.current_model,
            "messages": self.build_chat_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        body = json.dumps(payload)
        conn = http.client.HTTPConnection("127.0.0.1", self.backend_port, timeout=120)
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        resp = conn.getresponse()
        if resp.status != 200:
            raw = resp.read().decode("utf-8")
            raise RuntimeError(raw or f"backend returned HTTP {resp.status}")

        chunks = []
        try:
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
                chunk_json = json.loads(data)
                delta = extract_stream_delta(chunk_json)
                if delta:
                    chunks.append(delta)
                    yield delta
        finally:
            reply = "".join(chunks)
            if reply:
                self.remember_chat(messages, reply)

    def plan_agent_task(self, task_text):
        system_prompt = (
            "You are Locali, a permissioned local agent running on the user's machine. "
            "Plan tasks carefully and output STRICT JSON only. "
            "Allowed action types: answer, command. "
            "Use 'answer' for tasks you can solve directly without system access. "
            "Use 'command' only when a shell command is required. "
            "For command actions, include these keys: type, summary, command, cwd, explanation. "
            "Set cwd to '.' unless another directory is clearly needed. "
            "Never run anything yourself. Never include markdown fences."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text},
        ]
        content = extract_chat_content(self.chat_completion(messages, temperature=0.1, max_tokens=512))
        if not content:
            raise RuntimeError("empty agent response")
        return content.strip()

    def execute_command(self, command_text, cwd=None):
        cwd_path = self.root if not cwd else (self.root / cwd).resolve()
        if not str(cwd_path).startswith(str(self.root.resolve())):
            raise RuntimeError("refusing to execute outside the USB root")

        run_kwargs = {
            "cwd": str(cwd_path),
            "capture_output": True,
            "text": True,
            "timeout": 300,
        }

        if self.os_name == "windows":
            result = subprocess.run(command_text, shell=True, **run_kwargs)
        else:
            result = subprocess.run(command_text, shell=True, executable="/bin/sh", **run_kwargs)

        return {
            "command": command_text,
            "cwd": str(cwd_path),
            "exit_code": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-20000:],
        }


def open_ui(port):
    webbrowser.open(f"http://127.0.0.1:{port}/")


class LocaliHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class LocaliRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        return

    @property
    def state(self):
        return self.server.state

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, content_type="text/html; charset=utf-8", status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            ui_path = self.state.root / "ui" / "index.html"
            self._send_text(ui_path.read_text(encoding="utf-8"))
            return

        if path == "/api/state":
            self._send_json(self.state.state())
            return

        if path == "/api/models":
            self._send_json({
                "current": self.state.current_model,
                "available": self.state.state()["available_models"],
            })
            return

        if path == "/api/profile":
            self._send_json({"ok": True, "profile": self.state.profile})
            return

        if path == "/health":
            if backend_ready(self.state.backend_port, timeout=1):
                self._send_json({"ok": True})
            else:
                self._send_json({"ok": False}, status=503)
            return

        if path == "/api/health":
            if backend_ready(self.state.backend_port, timeout=1):
                self._send_json({"ok": True})
            else:
                self._send_json({"ok": False}, status=503)
            return

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/select-model":
            try:
                payload = self._read_body_json()
                model_name = payload.get("model", "")
                if not model_name:
                    self._send_json({"error": "model is required"}, status=400)
                    return

                state = self.state.select_model(model_name)
                self._send_json({"ok": True, "state": state})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/profile":
            try:
                payload = self._read_body_json()
                if not isinstance(payload, dict):
                    self._send_json({"error": "profile must be an object"}, status=400)
                    return

                self.state.profile.update({
                    "name": str(payload.get("name", self.state.profile.get("name", ""))).strip(),
                    "role": str(payload.get("role", self.state.profile.get("role", ""))).strip(),
                    "preferences": payload.get("preferences", self.state.profile.get("preferences", [])),
                })
                save_json_file(self.state.profile_path, self.state.profile)
                self._send_json({"ok": True, "profile": self.state.profile})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/chat":
            try:
                payload = self._read_body_json()
                messages = payload.get("messages", [])
                if not isinstance(messages, list) or not messages:
                    self._send_json({"error": "messages are required"}, status=400)
                    return

                temperature = float(payload.get("temperature", 0.7))
                max_tokens = int(payload.get("max_tokens", 512))
                stream = payload.get("stream", False) is True

                if stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    for chunk in self.state.chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
                        data = json.dumps({"choices": [{"delta": {"content": chunk}}]})
                        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    return

                response = self.state.chat(messages, temperature=temperature, max_tokens=max_tokens)
                self._send_json({"ok": True, "response": response})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/agent/plan":
            try:
                payload = self._read_body_json()
                task = payload.get("task", "").strip()
                if not task:
                    self._send_json({"error": "task is required"}, status=400)
                    return

                content = self.state.plan_agent_task(task)
                try:
                    plan = parse_json_block(content)
                except Exception:
                    plan = {
                        "type": "answer",
                        "summary": "Model response",
                        "answer": content,
                    }

                if "type" not in plan:
                    plan["type"] = "answer"

                self._send_json({"ok": True, "plan": plan})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/agent/execute":
            try:
                payload = self._read_body_json()
                if payload.get("approved") is not True:
                    self._send_json({"error": "approval required"}, status=400)
                    return

                command = payload.get("command", "").strip()
                if not command:
                    self._send_json({"error": "command is required"}, status=400)
                    return

                cwd = payload.get("cwd")
                result = self.state.execute_command(command, cwd=cwd)
                self._send_json({"ok": True, "result": result})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        self._send_json({"error": "not found"}, status=404)


def main():
    parser = argparse.ArgumentParser(description="Locali Launcher")
    parser.add_argument("--root", help="Path to USB root (auto-detected if omitted)")
    args = parser.parse_args()

    print(BANNER)

    # ── Detect environment ──────────────────────────────────
    os_name = detect_os()
    root    = get_root_dir(args.root)
    config  = load_config(root)
    controller = BackendController(root, os_name, config)

    info(f"OS detected: {os_name.capitalize()}")
    info(f"USB root: {root}")
    info(f"Model: {config.get('model', '?')}")

    port = controller.control_port
    backend_port = controller.backend_port

    # ── Pre-flight checks ───────────────────────────────────
    print()
    if not check_port(port):
        warn(f"Port {port} is already in use.")
        warn(f"Change 'port' in config.json, or stop the process using port {port}.")
        sys.exit(1)
    if not check_port(backend_port):
        warn(f"Backend port {backend_port} is already in use.")
        warn("Stop the process using that port or change 'port' in config.json.")
        sys.exit(1)
    ok(f"Ports are free: control {port}, backend {backend_port}")

    binary = get_binary_path(root, os_name)
    available_models = discover_models(root, config)
    current_model = normalize_model_name(config.get("model", ""))
    model_path = get_model_path(root, current_model)
    ok(f"Binary found: {binary.relative_to(root)}")
    ok(f"Model found: {model_path.name}")
    if len(available_models) > 1:
        info(f"Available models: {', '.join(available_models)}")

    print(f"\n  {C.BOLD}Starting Locali control server...{C.RESET}")
    info(f"Threads: {resolve_threads(config)} | GPU layers: {resolve_gpu_layers(config)} | Port: {port} | Backend: {backend_port}")
    print()

    controller.start(current_model)

    server = LocaliHTTPServer(("127.0.0.1", port), LocaliRequestHandler)
    server.state = controller

    def shutdown(sig, frame):
        print(f"\n\n  {C.YELLOW}Shutting down...{C.RESET}")
        controller.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    ok("Backend is ready!")
    print(f"\n  {C.BOLD}{C.GREEN}🚀 Locali is running!{C.RESET}")
    print(f"  {C.CYAN}UI:{C.RESET}  http://127.0.0.1:{port}")
    print(f"  {C.CYAN}Backend:{C.RESET}  http://127.0.0.1:{backend_port}")
    print(f"\n  Press  Ctrl+C  to stop.\n")

    if config.get("open_browser", True):
        threading.Thread(target=open_ui, args=(port,), daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        controller.stop()
        ok("Server stopped. USB safe to remove.")


if __name__ == "__main__":
    main()
