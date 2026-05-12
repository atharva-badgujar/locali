# 🧠 Locali

> **Portable local AI on a USB drive** — no install on host machine, no cloud dependency after setup.

Locali packages a Gemma model and a private inference engine into a single portable folder. Plug your USB into Windows, macOS, or Linux, run one command, and chat locally.

---

## ✨ UI Highlights

- Clean dark chat interface with message history and model switcher.
- Improved markdown rendering (bold text, inline code, fenced code blocks).
- Code snippet window style for fenced code with clear visual separation.
- Live server status and CPU/RAM usage HUD.
- Conversation persistence to USB (`data/`), so chats follow you.

---

## 🚀 Quick Start (Step-by-step)

### 1) Clone this repository

```bash
git clone https://github.com/atharvabadgujar/locali.git
cd locali
```

### 2) Insert and locate your USB drive

Common mount paths:
- **macOS:** `/Volumes/MYUSB`
- **Linux:** `/media/$USER/MYUSB`
- **Windows:** `E:` (or another drive letter)

### 3) Run setup to copy runtime + models to USB

#### macOS / Linux

```bash
chmod +x setup/setup_unix.sh
./setup/setup_unix.sh --drive /Volumes/MYUSB
```

#### Windows (PowerShell)

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup_windows.ps1 -USBDrive "E:"
```

During setup, choose model option:
- `1` → Gemma 3 1B (~800 MB, fastest)
- `2` → Gemma 3 4B (~2.5 GB, better quality)
- `3` → install both

### 4) Run Locali from USB

#### macOS / Linux

```bash
cd /Volumes/MYUSB/locali
./start.sh
```

#### Windows (CMD)

```cmd
cd E:\locali
start.bat
```

Then open:

```text
http://127.0.0.1:8080
```

---

## 🧭 Daily Usage Flow

1. Plug in USB.
2. Launch `start.sh` (macOS/Linux) or `start.bat` (Windows).
3. Wait until status becomes **ready**.
4. Select a model from the top bar if needed and click **Switch**.
5. Start chatting.
6. Use **Clear Chat** to reset current conversation.

---

## ⚙️ Configuration

Edit `config.json` on the USB:

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

| Key | Meaning |
|---|---|
| `model` | Default model filename |
| `context_size` | Token context window |
| `port` | Local web port |
| `threads` | CPU threads (`auto` or number) |
| `gpu_layers` | GPU acceleration hint (`0` for CPU-only) |
| `temperature` | Creativity control |
| `open_browser` | Auto-open UI at launch |

---

## 💻 System Requirements

| Aspect | Minimum | Recommended |
|---|---|---|
| USB size | 8 GB | 16 GB+ |
| USB speed | USB 3.0 | USB 3.1+ |
| RAM | 4 GB | 8 GB+ |
| OS | Win 10+, macOS 12+, Ubuntu 20.04+ | Latest stable |
| CPU | 64-bit | Multi-core 2 GHz+ |

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| UI shows no response | Restart launcher and verify setup completed |
| Port conflict on `8080` | Change `port` in `config.json` |
| Slow responses | Use USB 3.x port and faster model |
| Memory issues | Close other apps or switch to 1B model |
| Missing stats HUD | `python3 -m pip install --user psutil` |
| macOS security block | `xattr -d com.apple.quarantine /Volumes/MYUSB/locali/bin/mac/llama-server` |

---

## 📁 USB Layout After Setup

```text
YOUR_USB/
└── locali/
    ├── start.sh / start.bat
    ├── config.json
    ├── launcher/launch.py
    ├── bin/
    │   ├── windows/llama-server.exe
    │   ├── linux/llama-server
    │   └── mac/llama-server
    ├── models/
    ├── ui/index.html
    └── data/
        ├── memory.json
        └── profile.json
```

---

## 🔒 Privacy

- All chat data is stored locally on USB.
- Inference runs on localhost.
- No sign-in, cloud sync, or telemetry by default.

---

## 📜 License

MIT License. Gemma model weights follow [Google Gemma Terms](https://ai.google.dev/gemma/terms).
