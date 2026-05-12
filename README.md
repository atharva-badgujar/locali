# 🧠 Locali

> **Carry a local AI in your pocket. Plug in. One command. Done.**
> No internet after setup. No data on the host. No installation. Ever.

---

## What is this?

Locali turns a USB drive into a portable AI assistant powered by Google's Gemma model. You do a **one-time setup** on your own machine, and after that — plug the USB into **any** Windows, Linux, or macOS computer and run one command to start chatting. Everything runs from the USB. The host machine is never touched.

```
Your USB drive
├── Gemma model weights         (~800 MB or ~2.5 GB)
├── llama.cpp inference engine  (pre-built binary, no install)
├── Chat UI                     (offline HTML page)
└── One launcher script         (start.sh / start.bat)
          │
          ▼  plug into any machine

Host machine contributes only:  CPU + RAM
Host machine stores:            nothing
Internet required after setup:  none
```

---

## Before You Begin — What You Need

### A USB Drive
| | Minimum | Recommended |
|---|---|---|
| Capacity | 8 GB | 16 GB+ |
| **USB Version** | **USB 3.0 ← required** | USB 3.1 or 3.2 |
| Read speed | 80 MB/s | 200 MB/s+ |

> ❌ **USB 2.0 will not work.** Model loading would take many minutes. Check your drive — it must say USB 3.0, 3.1, or 3.2.
>
> ✅ How to check: On Windows open Device Manager → Universal Serial Bus controllers. On Mac/Linux run `system_profiler SPUSBDataType` or `lsusb -v`.

### The Machine You Set Up From (one-time only)
- Internet connection to download the model (~800 MB or ~2.5 GB)
- Windows 10+, macOS 12+, or Ubuntu 20.04+
- USB drive plugged in

### Any Machine You Later Plug Into
| | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB+ |
| CPU | Any 64-bit (x86_64) | Multi-core 2GHz+ |
| GPU | Not required | NVIDIA/AMD (auto-detected, speeds things up) |
| OS | Windows 10+, Ubuntu 20.04+, macOS 12+ | Latest version |
| Admin rights | ❌ Not needed | — |
| Disk space | **0 GB** | — |
| Internet | **Not needed** | — |

### Choose Your Model

| Model | USB Space | RAM Needed | Speed | Best For |
|---|---|---|---|---|
| ⭐ **Gemma 3 1B** (recommended) | ~800 MB | 4 GB | Fast | Most tasks, quick answers |
| **Gemma 3 4B** | ~2.5 GB | 8 GB | Moderate | Better reasoning and detail |

**Not sure?** Start with 1B. You can always re-run setup later with `--model 4b`.

---

## ── SETUP ─────────────────────────────────────────────────

> ⏱ One-time setup takes 5–15 minutes (mostly download time).
> After this, the USB works forever — completely offline.

### Step 1 — Download Locali

👉 Go to: **[github.com/YOUR_USERNAME/locali/releases/latest](https://github.com/YOUR_USERNAME/locali/releases/latest)**

Download the file named:
```
locali-v1.0.zip
```

This zip has everything **except** the model weights (those are downloaded in Step 3).

---

### Step 2 — Extract to Your USB Drive

Plug in your USB. Extract the zip **directly onto the USB root**, not into a subfolder.

After extraction, your USB should look exactly like this:
```
YOUR_USB_DRIVE/
├── start.bat          ← Windows launcher (double-click this later)
├── start.sh           ← Linux/macOS launcher (run this later)
├── setup/
│   ├── setup_windows.ps1
│   └── setup_unix.sh
├── launcher/
│   └── launch.py
├── bin/
│   ├── windows/
│   ├── linux/
│   └── mac/
├── models/            ← empty folder — model goes here next
├── ui/
│   └── index.html
└── config.json
```

---

### Step 3 — Download the Gemma Model onto the USB

This is the only step that uses the internet. Run the setup script for your OS.
It downloads Gemma and saves it directly onto your USB drive.

**On Windows** — open PowerShell (no admin needed) and run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
E:\setup\setup_windows.ps1 -USBDrive "E:" -Model "1b"
```
> Replace `E:` with your actual USB drive letter (check File Explorer).

**On macOS** — open Terminal and run:
```bash
chmod +x /Volumes/MYUSB/setup/setup_unix.sh
/Volumes/MYUSB/setup/setup_unix.sh --drive /Volumes/MYUSB --model 1b
```
> Replace `MYUSB` with your USB volume name (visible in Finder sidebar).

**On Linux** — open Terminal and run:
```bash
chmod +x /media/$USER/MYUSB/setup/setup_unix.sh
/media/$USER/MYUSB/setup/setup_unix.sh --drive /media/$USER/MYUSB --model 1b
```
> Replace `MYUSB` with your USB name (check with `lsblk` or your file manager).

The script will check your USB speed, download the model (~800 MB for 1B), and confirm everything is ready. You'll see a green success box when done.

**✅ Eject the USB. Setup is complete. Internet no longer needed.**

---

## ── USING IT ──────────────────────────────────────────────

This is what you do every time, on any machine. **No internet. One command.**

### 1. Plug in the USB

### 2. Open a terminal and run:

**Windows:**
```powershell
E:\start.bat
```
Or just **double-click `start.bat`** in File Explorer on the USB.

**macOS:**
```bash
cd /Volumes/MYUSB
./start.sh
```

**Linux:**
```bash
cd /media/$USER/MYUSB
./start.sh
```

### 3. Chat

Your browser opens automatically to the chat interface.
If it doesn't, go to: **http://localhost:8080**

### 4. Stop

Press `Ctrl+C` in the terminal. Server stops, RAM is freed. USB is safe to remove.

---

## What Happens Under the Hood

```
./start.sh
  │
  ├─ Detects OS (Windows / Linux / macOS)
  ├─ Selects the right llama.cpp binary from USB/bin/
  ├─ Loads the Gemma model into the host machine's RAM
  ├─ Starts server at 127.0.0.1:8080 (localhost only, never network-exposed)
  ├─ Opens browser to USB/ui/index.html
  │
  └─ You chat. All inference runs on host CPU/RAM.
     Nothing written to host disk. No network calls.
     
Ctrl+C
  │
  └─ Server stops. RAM freed. Zero traces on host.
```

---

## Host Machine Safety

| | Locali |
|---|---|
| Writes files to host disk | ❌ Never |
| Modifies Windows registry | ❌ Never |
| Requires admin / sudo | ❌ Never |
| Makes network requests | ❌ Never |
| Exposes server beyond localhost | ❌ Never |
| Installs software on host | ❌ Never |
| Leaves anything after exit | ❌ Never |
| Uses CPU/RAM while running | ✅ Yes (like any normal app) |

---

## Configuration

Edit `config.json` on the USB to customise behaviour. No restart of setup needed — just rerun `start.sh`.

```json
{
  "model": "gemma-3-1b-it-q4_k_m.gguf",
  "context_size": 2048,
  "port": 8080,
  "gpu_layers": "auto",
  "threads": "auto",
  "temperature": 0.7,
  "open_browser": true
}
```

| Setting | What it does |
|---|---|
| `model` | GGUF filename in the `/models` folder |
| `context_size` | Memory window in tokens. Higher = slower but more context |
| `port` | Change if 8080 is already taken on the host |
| `gpu_layers` | `"auto"` uses GPU if found, else CPU. Set `0` to force CPU-only |
| `threads` | `"auto"` uses all CPU cores. Set a number to limit |
| `temperature` | 0.1 = precise, 0.7 = balanced, 1.0 = creative |
| `open_browser` | `false` to disable auto browser opening |

---

## Troubleshooting

**Model loading is very slow (takes minutes)**
Your USB is too slow or it's plugged into a USB 2.0 port. USB 3.0 ports have a blue plastic tab inside, or an `SS` (SuperSpeed) label. Try a different port.

**"Port 8080 already in use"**
Change `"port"` in `config.json` to `8181` or any free port, then open `http://localhost:8181`.

**Process killed / "out of memory"**
Not enough free RAM on the host. Close other apps, or switch to the 1B model by changing `"model"` in `config.json`.

**macOS: "llama-server cannot be opened" security warning**
Run once on your USB (this just removes the quarantine flag):
```bash
xattr -d com.apple.quarantine /Volumes/MYUSB/bin/mac/llama-server
```

**Windows: antivirus flags llama-server.exe**
False positive — common with compiled ML binaries. Add a Windows Security exclusion for the USB drive, or build from source: see `docs/build-from-source.md`.

**"Python not found" message on startup**
No problem — the launcher falls back to running the binary directly. Python only adds a nicer startup experience. Everything still works.

**Chat UI shows "Connection failed"**
The server may still be loading. Wait 10–20 seconds and refresh. On slow CPUs or large models, first load takes longer.

---

## FAQ

**Do I need an account anywhere?**
No. No GitHub account, no Google account, no Hugging Face account. The setup script downloads from public URLs.

**Can I use this on a work, school, or library computer?**
Yes. No admin rights needed, nothing installed, nothing left behind.

**Can I use a model other than Gemma?**
Yes — any GGUF format model works. Put it in the `models/` folder on the USB and update `"model"` in `config.json`.

**What if the USB is pulled out mid-conversation?**
The server crashes cleanly. Nothing is lost or damaged on the host. Your USB model files are only read, never written during runtime.

**Does this work on Apple Silicon (M1/M2/M3)?**
The Intel binary runs via Rosetta 2. For best performance, build a native ARM binary — see `docs/build-from-source.md`.

**Can multiple people use different USBs on the same machine?**
Yes, as long as they use different port numbers (set in `config.json`).

---

## Project Structure

```
locali/
├── README.md
├── start.bat                   # Windows: double-click or run from terminal
├── start.sh                    # Linux/macOS: ./start.sh
├── config.json                 # Edit to change model, port, etc.
│
├── setup/
│   ├── setup_windows.ps1       # One-time setup (downloads model to USB)
│   └── setup_unix.sh           # Same for Linux/macOS
│
├── launcher/
│   └── launch.py               # OS detection, binary selection, server start
│
├── bin/                        # Pre-built llama.cpp (no installation on host)
│   ├── windows/llama-server.exe
│   ├── linux/llama-server
│   └── mac/llama-server
│
├── models/                     # GGUF model files (downloaded by setup, gitignored)
│
├── ui/
│   └── index.html              # Offline chat UI (zero external requests)
│
└── docs/
    ├── contributing.md
    └── build-from-source.md
```

---

## Contributing

PRs welcome — see `docs/contributing.md`. Most needed:
- Native ARM Linux binaries (Raspberry Pi, ARM servers)
- Native Apple Silicon binary
- Download progress bar during setup
- More model presets (CodeGemma, Gemma 3n E4B)

---

## License

MIT. Gemma model weights are subject to [Google's Gemma Terms of Use](https://ai.google.dev/gemma/terms).

## Credits

- [llama.cpp](https://github.com/ggml-org/llama.cpp) — inference engine
- [Google Gemma](https://ai.google.dev/gemma) — open model family
- [Hugging Face](https://huggingface.co) — model hosting
