# 🧠 Locali

Local AI on a USB drive. No installation, no internet after setup.

Locali packages a Gemma model and a private inference engine into a portable folder. Plug your USB into any Windows, macOS, or Linux machine, run one command, and start chatting. All data stays on the USB.

---

## Installation & Setup

### Step 1: Clone the repository

```bash
git clone https://github.com/atharvabadgujar/locali.git
cd locali
```

### Step 2: Plug in your USB drive

Mount the USB and note its path:
- **macOS**: `/Volumes/MYUSB` (visible in Finder)
- **Windows**: `E:` or `F:` (visible in File Explorer)
- **Linux**: `/media/$USER/MYUSB` (from `lsblk` or mount point)

### Step 3: Run setup script

The setup script asks which models to install, then downloads everything (~1–2 GB).

**macOS / Linux:**
```bash
chmod +x setup/setup_unix.sh
./setup/setup_unix.sh --drive /Volumes/MYUSB
```

**Windows (PowerShell):**
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup_windows.ps1 -USBDrive "E:"
```

When prompted, select:
- **1** for Gemma 3 1B (recommended, ~800 MB)
- **2** for Gemma 3 4B (~2.5 GB, better quality)
- **3** for both

Setup completes in a few minutes. It skips re-downloading files if they already exist.

### Step 4: Use Locali on any machine

Safely eject the USB and plug it into any Windows/macOS/Linux machine.

**macOS / Linux:**
```bash
cd /Volumes/MYUSB/locali
./start.sh
```

**Windows:**
```cmd
cd E:\locali
start.bat
```

Or double-click `start.bat` from File Explorer.

Your browser opens to `http://127.0.0.1:8080`. Start chatting.

---

## System Requirements

| Aspect | Minimum | Recommended |
|---|---|---|
| **USB Size** | 8 GB | 16 GB+ |
| **USB Speed** | USB 3.0 | USB 3.1+ |
| **RAM** | 4 GB | 8 GB+ |
| **OS** | Windows 10+, macOS 12+, Ubuntu 20.04+ | Latest stable |
| **CPU** | Any 64-bit | Multi-core 2GHz+ |
| **Admin Rights** | Not needed | Not needed |
| **Internet (after setup)** | Not needed | Not needed |

---

## Features

- **Chat Interface**: Modern dark UI with conversation history
- **Model Switching**: Switch between installed models without restarting
- **Offline**: Works completely offline after setup
- **Private**: All data stays on the USB; no cloud sync
- **Cross-Platform**: Works on Windows, macOS, Linux
- **Resource Stats**: Live CPU/RAM usage display in header (requires `psutil`)

---

## Common Issues

| Issue | Solution |
|---|---|
| Model doesn't reply | Restart launcher; ensure setup completed |
| USB too slow | Use USB 3.0+ ports, not USB 2.0 |
| Out of memory | Close other apps or switch to 1B model |
| Port 8080 in use | Edit `config.json`: change `"port": 8080` and restart |
| Resource stats missing | Install `python3 -m pip install --user psutil` |
| macOS security warning | Run `xattr -d com.apple.quarantine /Volumes/MYUSB/locali/bin/mac/llama-server` |
| Windows antivirus blocks | Add USB folder to antivirus exclusions |

---

## What Gets Downloaded

- **Gemma 3 1B Model**: ~800 MB
- **Gemma 3 4B Model**: ~2.5 GB (if selected)
- **llama.cpp Binary**: ~50–100 MB per OS
- **Runtime Libraries**: ~100–200 MB

Total: 1–5 GB depending on model selection.

---

## USB Layout After Setup

```
YOUR_USB/
└── locali/
    ├── start.sh / start.bat          (launcher)
    ├── config.json                   (settings)
    ├── launcher/
    │   └── launch.py                 (control server)
    ├── bin/
    │   ├── windows/llama-server.exe
    │   ├── linux/llama-server
    │   └── mac/llama-server
    ├── models/
    │   └── gemma-3-1b-it-q4_k_m.gguf
    ├── ui/
    │   └── index.html                (web interface)
    └── data/
        └── (chat history, profile)
```

---

## Configuration

Edit `locali/config.json` on the USB to customize (optional):

```json
{
  "model": "gemma-3-1b-it-q4_k_m.gguf",
  "context_size": 2048,
  "port": 8080,
  "threads": "auto",
  "gpu_layers": "auto",
  "temperature": 0.7,
  "open_browser": true
}
```

| Setting | Default | Notes |
|---|---|---|
| `model` | 1B GGUF | Current active model |
| `context_size` | 2048 | Token window size |
| `port` | 8080 | Local server port |
| `threads` | `"auto"` | CPU threads (or number) |
| `gpu_layers` | `"auto"` | GPU acceleration (0 = CPU only) |
| `temperature` | 0.7 | Lower = deterministic, higher = creative |
| `open_browser` | true | Auto-open browser on start |

---

## Data Privacy

- **Chat history** stored locally in `data/memory.json` on the USB
- **User profile** stored locally in `data/profile.json` on the USB
- **No external calls** — everything runs on localhost
- **Nothing on host machine** — no installation, no registry changes, no temp files persist

---

## License

MIT. Gemma model weights are subject to [Google's Gemma Terms of Use](https://ai.google.dev/gemma/terms).
