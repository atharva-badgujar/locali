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
MODEL=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --drive|-d) DRIVE="$2"; shift 2 ;;
    --model|-m) MODEL="$2"; shift 2 ;;
    *) err "Unknown argument: $1. Usage: ./setup_unix.sh --drive /path/to/usb --model 1b" ;;
  esac
done

[[ -z "$DRIVE" ]] && err "USB drive path required. Example: --drive /media/user/MYUSB"

if [[ -z "$MODEL" ]]; then
        echo ""
        echo "Choose which model(s) to install:"
        echo "  1) Gemma 3 1B"
        echo "  2) Gemma 3 4B"
        echo "  3) Both"
        read -r -p "Select 1, 2, or 3 [1]: " MODEL_CHOICE
        MODEL_CHOICE="${MODEL_CHOICE:-1}"
        case "$MODEL_CHOICE" in
                1) MODEL="1b" ;;
                2) MODEL="4b" ;;
                3) MODEL="both" ;;
                *) err "Invalid selection. Choose 1, 2, or 3." ;;
        esac
fi

[[ "$MODEL" != "1b" && "$MODEL" != "4b" && "$MODEL" != "both" ]] && err "Model must be '1b', '4b', or 'both'"

INSTALL_ROOT="$DRIVE/locali"

print_banner
echo -e "  ${BOLD}Linux/macOS Setup  |  Model: Gemma 3 ${MODEL}  |  Target: ${INSTALL_ROOT}${NC}\n"

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

if [[ "$MODEL" == "both" ]]; then
    REQUIRED_GB=6
elif [[ "$MODEL" == "4b" ]]; then
    REQUIRED_GB=4
else
    REQUIRED_GB=2
fi
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

for dir in launcher "bin/windows" "bin/linux" "bin/mac" models ui docs setup; do
    mkdir -p "$INSTALL_ROOT/$dir"
done
ok "Directories created"

# Ensure macOS dylib symlinks exist (idempotent)
create_mac_symlinks() {
    macdir="$INSTALL_ROOT/bin/mac"
    [[ -d "$macdir" ]] || return 0
    shopt -s nullglob
    for f in "$macdir"/*.dylib; do
        base=$(basename "$f")
        # If a file is versioned like libfoo.0.0.123.dylib, create libfoo.0.dylib -> pointed to it
        if [[ "$base" =~ ^(.+\.0)\..*\.dylib$ ]]; then
            short="${BASH_REMATCH[1]}.dylib"
            if [[ ! -e "$macdir/$short" ]]; then
                ln -sf "$base" "$macdir/$short"
            fi
        fi
    done
    shopt -u nullglob
}

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
    if [[ -x "$INSTALL_ROOT/bin/mac/llama-server" ]] && compgen -G "$INSTALL_ROOT/bin/mac/*.dylib" > /dev/null; then
        create_mac_symlinks
        ok "llama.cpp engine already installed"
    else
        cp "$BINARY" "$INSTALL_ROOT/bin/mac/llama-server"
        chmod +x "$INSTALL_ROOT/bin/mac/llama-server"
        # Copy bundled shared libraries that the macOS binary links against.
        find "$TMP_DIR/extracted" -name "*.dylib" -type f -exec cp {} "$INSTALL_ROOT/bin/mac/" \;
        # Create missing versioned/unversioned symlinks expected by dyld.
        if command -v otool >/dev/null 2>&1; then
            deps=$(otool -L "$BINARY" | awk '/@rpath/ {print $1}' | xargs -n1 basename | sort -u)
            for dep in $deps; do
                target="$INSTALL_ROOT/bin/mac/$dep"
                if [[ ! -e "$target" ]]; then
                    # try to find a candidate file with the same prefix
                    prefix="$(echo "$dep" | sed -E 's/\.[0-9].*//')"
                    candidate=$(find "$TMP_DIR/extracted" -name "$prefix*.dylib" -print -quit)
                    if [[ -n "$candidate" ]]; then
                        cp "$candidate" "$INSTALL_ROOT/bin/mac/"
                        ln -sf "$(basename "$candidate")" "$target"
                    fi
                fi
            done
        fi
        # Remove macOS quarantine to prevent "cannot be opened" errors
        xattr -d com.apple.quarantine "$INSTALL_ROOT/bin/mac/llama-server" 2>/dev/null || true
        # Ensure symlinks for copied dylibs
        create_mac_symlinks
        ok "llama.cpp engine installed"
    fi
else
    if [[ -x "$INSTALL_ROOT/bin/linux/llama-server" ]]; then
        ok "llama.cpp engine already installed"
    else
        cp "$BINARY" "$INSTALL_ROOT/bin/linux/llama-server"
        chmod +x "$INSTALL_ROOT/bin/linux/llama-server"
        ok "llama.cpp engine installed"
    fi
fi

rm -rf "$TMP_DIR"

# --- Download Gemma Model ---
echo -e "\n${BOLD}[ 5/6 ] Downloading Gemma 3 ${MODEL} model (GGUF format)...${NC}"

MODELS_TO_INSTALL=()
if [[ "$MODEL" == "both" ]]; then
    MODELS_TO_INSTALL=("1b" "4b")
elif [[ "$MODEL" == "1b" ]]; then
    MODELS_TO_INSTALL=("1b")
else
    MODELS_TO_INSTALL=("4b")
fi

MODEL_FILES=()
for item in "${MODELS_TO_INSTALL[@]}"; do
    if [[ "$item" == "1b" ]]; then
        model_file="gemma-3-1b-it-q4_k_m.gguf"
        model_url="https://huggingface.co/lmstudio-community/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
    else
        model_file="gemma-3-4b-it-q4_k_m.gguf"
        model_url="https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf"
    fi

    MODEL_FILES+=("$model_file")
    info "Downloading: $model_file"
    info "This may take a few minutes..."

    if [[ -f "$INSTALL_ROOT/models/$model_file" ]]; then
        ok "Model already installed: $model_file"
    else
        curl -L -o "$INSTALL_ROOT/models/$model_file" "$model_url" --progress-bar
        ok "Model downloaded: $model_file"
    fi
done

MODEL_FILE="${MODEL_FILES[0]}"
MODELS_JSON=""
for idx in "${!MODEL_FILES[@]}"; do
    [[ -n "$MODELS_JSON" ]] && MODELS_JSON+=", "
    MODELS_JSON+="\"${MODEL_FILES[$idx]}\""
done

# --- Write Config and Scripts ---
echo -e "\n${BOLD}[ 6/6 ] Writing config and launcher scripts...${NC}"

# config.json
cat > "$INSTALL_ROOT/config.json" <<EOF
{
  "model": "$MODEL_FILE",
    "models": [$MODELS_JSON],
  "context_size": 2048,
  "port": 8080,
  "gpu_layers": "auto",
  "threads": "auto",
  "temperature": 0.7,
  "open_browser": true
}
EOF

# start.sh in the Locali folder
cat > "$INSTALL_ROOT/start.sh" <<'EOF'
#!/usr/bin/env bash
# Locali — quick launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/launcher/launch.py" --root "$SCRIPT_DIR"
    exit 0
fi

if command -v python &>/dev/null; then
    python "$SCRIPT_DIR/launcher/launch.py" --root "$SCRIPT_DIR"
    exit 0
fi

echo "  Python not found. Starting in fallback mode..."

OS="$(uname)"
if [[ "$OS" == "Darwin" ]]; then
    BINARY="$SCRIPT_DIR/bin/mac/llama-server"
    export DYLD_LIBRARY_PATH="$SCRIPT_DIR/bin/mac:${DYLD_LIBRARY_PATH:-}"
else
    BINARY="$SCRIPT_DIR/bin/linux/llama-server"
fi

chmod +x "$BINARY" 2>/dev/null

# read model from config.json (fallback to default filename)
MODEL_FILE=$(awk 'match($0, /"model"[[:space:]]*:[[:space:]]*"([^"]+)"/, m){print m[1]; exit}' "$SCRIPT_DIR/config.json" || echo "gemma-3-1b-it-q4_k_m.gguf")

"$BINARY" \
    --model "$SCRIPT_DIR/models/$MODEL_FILE" \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 2048 \
    --threads 4 \
    --log-disable
EOF
chmod +x "$INSTALL_ROOT/start.sh"

ok "Config and launcher written"

# --- Copy launcher and UI files from repo ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$REPO_DIR/launcher/launch.py" ]]; then
    cp "$REPO_DIR/launcher/launch.py" "$INSTALL_ROOT/launcher/"
    ok "Launcher script copied"
fi

if [[ -f "$REPO_DIR/ui/index.html" ]]; then
    cp "$REPO_DIR/ui/index.html" "$INSTALL_ROOT/ui/"
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
    ║   → Run: ./locali/start.sh from the USB drive        ║
  ║                                                      ║
  ║   Then open:  http://localhost:8080                  ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
