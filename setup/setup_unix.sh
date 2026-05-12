#!/usr/bin/env bash
# ============================================================
#  Locali Setup Script — Linux / macOS
#  Prepares your USB drive with Gemma + llama.cpp binaries
#  Nothing is written to the host system.
# ============================================================

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

print_banner() {
echo -e "${BLUE}"
cat << 'EOF'
  ██████╗  ██████╗  ██████╗██╗  ██╗███████╗████████╗██╗     ██╗     ███╗   ███╗
  ██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝██║     ██║     ████╗ ████║
  ██████╔╝██║   ██║██║     █████╔╝ █████╗     ██║   ██║     ██║     ██╔████╔██║
  ██╔═══╝ ██║   ██║██║     ██╔═██╗ ██╔══╝     ██║   ██║     ██║     ██║╚██╔╝██║
  ██║     ╚██████╔╝╚██████╗██║  ██╗███████╗   ██║   ███████╗███████╗██║ ╚═╝ ██║
  ╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚══════╝╚═╝     ╚═╝
EOF
echo -e "${NC}"
}

# --- Parse Arguments ---
DRIVE=""
MODEL="1b"
while [[ $# -gt 0 ]]; do
  case $1 in
    --drive|-d) DRIVE="$2"; shift 2 ;;
    --model|-m) MODEL="$2"; shift 2 ;;
    *) err "Unknown argument: $1. Usage: ./setup_unix.sh --drive /path/to/usb --model 1b" ;;
  esac
done

[[ -z "$DRIVE" ]] && err "USB drive path required. Example: --drive /media/user/MYUSB"
[[ "$MODEL" != "1b" && "$MODEL" != "4b" ]] && err "Model must be '1b' or '4b'"

print_banner
echo -e "  ${BOLD}Linux/macOS Setup  |  Model: Gemma 3 ${MODEL}  |  Target: ${DRIVE}${NC}\n"

# --- Detect OS ---
OS="linux"
if [[ "$(uname)" == "Darwin" ]]; then OS="mac"; fi

# --- Validate Drive ---
echo -e "${BOLD}[ 1/6 ] Validating USB Drive...${NC}"

[[ ! -d "$DRIVE" ]] && err "Path '$DRIVE' does not exist. Is the USB mounted?"

if [[ "$OS" == "mac" ]]; then
    FREE_BYTES=$(df -k "$DRIVE" | awk 'NR==2 {print $4}')
    FREE_GB=$(echo "scale=1; $FREE_BYTES / 1048576" | bc)
else
    FREE_BYTES=$(df --output=avail -B1 "$DRIVE" | tail -1)
    FREE_GB=$(echo "scale=1; $FREE_BYTES / 1073741824" | bc)
fi

ok "Drive found. Free space: ${FREE_GB} GB"

REQUIRED_GB=$([[ "$MODEL" == "4b" ]] && echo 4 || echo 2)
if (( $(echo "$FREE_GB < $REQUIRED_GB" | bc -l) )); then
    err "Not enough space. Need ${REQUIRED_GB} GB, have ${FREE_GB} GB."
fi

# --- Check USB Speed ---
echo -e "\n${BOLD}[ 2/6 ] Checking USB Speed...${NC}"

TEST_FILE="$DRIVE/.locali_speedtest"
START_TIME=$(date +%s%N)
dd if=/dev/urandom of="$TEST_FILE" bs=1M count=50 2>/dev/null
END_TIME=$(date +%s%N)
rm -f "$TEST_FILE"

ELAPSED_MS=$(( (END_TIME - START_TIME) / 1000000 ))
SPEED_MBS=$(echo "scale=1; 50000 / $ELAPSED_MS" | bc)

info "Write speed: ${SPEED_MBS} MB/s"

if (( $(echo "$SPEED_MBS < 20" | bc -l) )); then
    err "USB too slow (${SPEED_MBS} MB/s). USB 3.0 required (min ~80 MB/s)."
elif (( $(echo "$SPEED_MBS < 80" | bc -l) )); then
    warn "Speed is low (${SPEED_MBS} MB/s). Performance may be poor. Use a USB 3.0 port."
else
    ok "Speed OK: ${SPEED_MBS} MB/s"
fi

# --- Create Directories ---
echo -e "\n${BOLD}[ 3/6 ] Creating directory structure on USB...${NC}"

for dir in launcher "bin/windows" "bin/linux" "bin/mac" models ui docs; do
    mkdir -p "$DRIVE/$dir"
done
ok "Directories created"

# --- Download llama.cpp Binary ---
echo -e "\n${BOLD}[ 4/6 ] Downloading llama.cpp inference engine (${OS})...${NC}"

info "Fetching latest llama.cpp release info..."
RELEASE_JSON=$(curl -sL "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest")

TMP_DIR=$(mktemp -d)

if [[ "$OS" == "mac" ]]; then
    ARCH=$(uname -m)
    if [[ "$ARCH" == "arm64" ]]; then
        LLAMA_URL=$(echo "$RELEASE_JSON" | grep -oE '"browser_download_url": "[^"]+bin-macos-arm64\.(zip|tar\.gz)"' | cut -d'"' -f4 | head -1)
    else
        LLAMA_URL=$(echo "$RELEASE_JSON" | grep -oE '"browser_download_url": "[^"]+bin-macos-x64\.(zip|tar\.gz)"' | cut -d'"' -f4 | head -1)
    fi
    info "Downloading for macOS (${ARCH})..."
else
    LLAMA_URL=$(echo "$RELEASE_JSON" | grep -oE '"browser_download_url": "[^"]+bin-ubuntu-x64\.(zip|tar\.gz)"' | cut -d'"' -f4 | head -1)
    info "Downloading for Linux..."
fi

if [[ -z "$LLAMA_URL" ]]; then
    err "Could not find a suitable llama.cpp binary in the latest release."
fi

EXT="${LLAMA_URL##*.}"
if [[ "$EXT" == "gz" ]]; then EXT="tar.gz"; fi

ARCHIVE_FILE="$TMP_DIR/llama_archive.$EXT"
curl -L -o "$ARCHIVE_FILE" "$LLAMA_URL" --progress-bar

if [[ "$EXT" == "zip" ]]; then
    unzip -q "$ARCHIVE_FILE" -d "$TMP_DIR/extracted"
else
    mkdir -p "$TMP_DIR/extracted"
    tar -xzf "$ARCHIVE_FILE" -C "$TMP_DIR/extracted"
fi

BINARY=$(find "$TMP_DIR/extracted" -name "llama-server" -type f | head -1)
if [[ -z "$BINARY" ]]; then
    err "llama-server binary not found in the downloaded archive."
fi

if [[ "$OS" == "mac" ]]; then
    cp "$BINARY" "$DRIVE/bin/mac/llama-server"
    chmod +x "$DRIVE/bin/mac/llama-server"
    # Copy bundled shared libraries that the macOS binary links against.
    find "$TMP_DIR/extracted" -name "*.dylib" -type f -exec cp {} "$DRIVE/bin/mac/" \;
    # Remove macOS quarantine to prevent "cannot be opened" errors
    xattr -d com.apple.quarantine "$DRIVE/bin/mac/llama-server" 2>/dev/null || true
else
    cp "$BINARY" "$DRIVE/bin/linux/llama-server"
    chmod +x "$DRIVE/bin/linux/llama-server"
fi

rm -rf "$TMP_DIR"
ok "llama.cpp engine installed"

# --- Download Gemma Model ---
echo -e "\n${BOLD}[ 5/6 ] Downloading Gemma 3 ${MODEL} model (GGUF format)...${NC}"

if [[ "$MODEL" == "1b" ]]; then
    MODEL_FILE="gemma-3-1b-it-q4_k_m.gguf"
    MODEL_URL="https://huggingface.co/lmstudio-community/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
else
    MODEL_FILE="gemma-3-4b-it-q4_k_m.gguf"
    MODEL_URL="https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf"
fi

info "Downloading: $MODEL_FILE"
info "This may take a few minutes..."
curl -L -o "$DRIVE/models/$MODEL_FILE" "$MODEL_URL" --progress-bar
ok "Model downloaded: $MODEL_FILE"

# --- Write Config and Scripts ---
echo -e "\n${BOLD}[ 6/6 ] Writing config and launcher scripts...${NC}"

# config.json
cat > "$DRIVE/config.json" <<EOF
{
  "model": "$MODEL_FILE",
  "context_size": 2048,
  "port": 8080,
  "gpu_layers": "auto",
  "threads": "auto",
  "temperature": 0.7,
  "open_browser": true
}
EOF

# start.sh at root of USB
cat > "$DRIVE/start.sh" <<'EOF'
#!/usr/bin/env bash
# Locali — quick launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "$SCRIPT_DIR/launcher/launch.py" 2>/dev/null || true
python3 "$SCRIPT_DIR/launcher/launch.py" --root "$SCRIPT_DIR"
EOF
chmod +x "$DRIVE/start.sh"

ok "Config and launcher written"

# --- Copy launcher and UI files from repo ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$REPO_DIR/launcher/launch.py" ]]; then
    cp "$REPO_DIR/launcher/launch.py" "$DRIVE/launcher/"
    ok "Launcher script copied"
fi

if [[ -f "$REPO_DIR/ui/index.html" ]]; then
    cp "$REPO_DIR/ui/index.html" "$DRIVE/ui/"
    ok "Chat UI copied"
fi

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}"
cat << 'EOF'
  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║   ✅  Locali setup complete!                      ║
  ║                                                      ║
  ║   To start on any Linux/macOS machine:               ║
  ║   → Run: ./start.sh  from the USB drive              ║
  ║                                                      ║
  ║   Then open:  http://localhost:8080                  ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
