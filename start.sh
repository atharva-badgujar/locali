#!/usr/bin/env bash
# Locali — Linux/macOS Quick Launcher
# Run: ./start.sh from the USB drive

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   🧠  Locali — Starting...       ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Try Python launcher (best experience)
if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/launcher/launch.py" --root "$SCRIPT_DIR"
    exit 0
fi

if command -v python &>/dev/null; then
    python "$SCRIPT_DIR/launcher/launch.py" --root "$SCRIPT_DIR"
    exit 0
fi

# Fallback: detect OS and run binary directly
echo "  Python not found. Starting in fallback mode..."

OS="$(uname)"
if [[ "$OS" == "Darwin" ]]; then
    BINARY="$SCRIPT_DIR/bin/mac/llama-server"
else
    BINARY="$SCRIPT_DIR/bin/linux/llama-server"
fi

MODEL_FILE="gemma-3-1b-it-q4_k_m.gguf"
PORT="8080"
if command -v python3 &>/dev/null; then
  while IFS='=' read -r k v; do
    [[ "$k" == "model" ]] && MODEL_FILE="$v"
    [[ "$k" == "port" ]] && PORT="$v"
  done < <(python3 - <<'PY' "$SCRIPT_DIR/config.json"
import json,sys
cfg=json.load(open(sys.argv[1],encoding='utf-8'))
print(f"model={cfg.get('model','gemma-3-1b-it-q4_k_m.gguf')}")
print(f"port={cfg.get('port',8080)}")
PY
)
fi

chmod +x "$BINARY" 2>/dev/null
"$BINARY" \
    --model "$SCRIPT_DIR/models/$MODEL_FILE" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --ctx-size 2048 \
    --threads 4 \
    --log-disable
