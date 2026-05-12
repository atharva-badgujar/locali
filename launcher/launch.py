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


def get_binary_path(root, os_name):
    if os_name == "windows":
        binary = root / "bin" / "windows" / "llama-server.exe"
    elif os_name == "mac":
        binary = root / "bin" / "mac" / "llama-server"
    else:
        binary = root / "bin" / "linux" / "llama-server"

    if not binary.exists():
        err(
            f"Binary not found: {binary}\n"
            f"  Run setup again, or download from:\n"
            f"  https://github.com/ggerganov/llama.cpp/releases"
        )
    return binary


def get_model_path(root, config):
    model_name = config.get("model", "")
    model_path = root / "models" / model_name
    if not model_path.exists():
        err(
            f"Model not found: {model_path}\n"
            f"  Re-run the setup script to download the model.\n"
            f"  Or update 'model' in config.json to match your GGUF filename."
        )
    return model_path


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


def build_command(binary, model_path, config):
    port    = config.get("port", 8080)
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

    # Set temp dir to USB drive to avoid writing to host
    # llama.cpp doesn't write temp files, but just in case
    return cmd


def wait_for_server(port, timeout=60):
    """Poll until the server is ready."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def open_ui(root, port):
    """Open the bundled chat UI in the default browser."""
    ui_path = root / "ui" / "index.html"
    if ui_path.exists():
        # Open local HTML file with server URL embedded as query param
        url = f"file://{ui_path}?port={port}"
    else:
        url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Locali Launcher")
    parser.add_argument("--root", help="Path to USB root (auto-detected if omitted)")
    args = parser.parse_args()

    print(BANNER)

    # ── Detect environment ──────────────────────────────────
    os_name = detect_os()
    root    = get_root_dir(args.root)
    config  = load_config(root)

    info(f"OS detected: {os_name.capitalize()}")
    info(f"USB root: {root}")
    info(f"Model: {config.get('model', '?')}")

    port = config.get("port", 8080)

    # ── Pre-flight checks ───────────────────────────────────
    print()
    if not check_port(port):
        warn(f"Port {port} is already in use.")
        warn(f"Change 'port' in config.json, or stop the process using port {port}.")
        sys.exit(1)
    ok(f"Port {port} is free")

    binary     = get_binary_path(root, os_name)
    model_path = get_model_path(root, config)
    ok(f"Binary found: bin/{os_name}/{binary.name}")
    ok(f"Model found: {model_path.name}")

    # ── Build and launch server ─────────────────────────────
    cmd = build_command(binary, model_path, config)

    print(f"\n  {C.BOLD}Starting Gemma server...{C.RESET}")
    info(f"Threads: {resolve_threads(config)} | GPU layers: {resolve_gpu_layers(config)} | Port: {port}")
    print()

    # On Windows, set TEMP to USB drive so no host temp files
    env = os.environ.copy()
    if os_name == "windows":
        usb_temp = root / "tmp"
        usb_temp.mkdir(exist_ok=True)
        env["TEMP"] = str(usb_temp)
        env["TMP"]  = str(usb_temp)

    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # ── Wait for server ready ───────────────────────────────
    print(f"  {C.CYAN}Waiting for server to start", end="", flush=True)
    ready = False
    for _ in range(60):
        if process.poll() is not None:
            err("Server process exited unexpectedly. Check your model file.")
        if check_port(port) is False:
            ready = True
            break
        print(".", end="", flush=True)
        time.sleep(1)
    print()

    if not ready:
        process.terminate()
        err("Server did not start in time. Try reducing context_size in config.json.")

    ok("Server is ready!")
    print(f"\n  {C.BOLD}{C.GREEN}🚀 Locali is running!{C.RESET}")
    print(f"  {C.CYAN}Chat UI:{C.RESET}  http://127.0.0.1:{port}")
    print(f"\n  Press  Ctrl+C  to stop.\n")

    # ── Open browser ────────────────────────────────────────
    if config.get("open_browser", True):
        threading.Thread(target=open_ui, args=(root, port), daemon=True).start()

    # ── Wait and handle shutdown ─────────────────────────────
    def shutdown(sig, frame):
        print(f"\n\n  {C.YELLOW}Shutting down...{C.RESET}")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        ok("Server stopped. USB safe to remove.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    process.wait()


if __name__ == "__main__":
    main()
