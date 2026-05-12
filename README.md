# 🧠 Locali

> Carry a local AI in your pocket. Plug in. One command. Done.
> Setup downloads the runtime binary and Gemma model once, then the USB works fully offline.

Locali turns a USB drive into a portable AI assistant powered by Google’s Gemma model. You prepare the USB once on your own machine, then you can plug it into a Windows, Linux, or macOS computer and start chatting without installing anything on the host.

## What You Get

```text
USB drive
└── locali/
    ├── Gemma model file         downloaded during setup
    ├── llama.cpp server binary  downloaded during setup
    ├── launcher script          start.sh / start.bat
    ├── chat UI                  offline HTML interface
    └── config.json              model and runtime settings

Host machine contributes only: CPU + RAM
Host machine stores:          nothing
Internet required after setup: no
```

## Requirements

You need one machine with internet access to do setup, plus the USB drive itself.

| Item | Minimum | Recommended |
|---|---|---|
| USB capacity | 8 GB | 16 GB+ |
| USB speed | USB 3.0 | USB 3.1 / 3.2 |
| Setup machine OS | Windows 10+, macOS 12+, Ubuntu 20.04+ | Latest stable release |
| Target machine RAM | 4 GB | 8 GB+ |
| Target machine CPU | Any 64-bit CPU | Multi-core 2GHz+ |
| Admin rights | Not required | Not required |
| Internet after setup | Not required | Not required |

USB 2.0 is too slow for a good experience.

## Model Choice

| Model | USB Space | RAM Needed | Best For |
|---|---|---|---|
| Gemma 3 1B | ~800 MB | 4 GB | Fast, light usage, best default |
| Gemma 3 4B | ~2.5 GB | 8 GB | Better answers, more memory needed |

If you are unsure, use 1B first. You can rerun setup later with `--model 4b`.

## Setup

There is no separate Locali release download required anymore. Use the files in this repository, then run the setup script for your operating system. The setup script will:

- create a top-level `locali` folder on the USB
- download the llama.cpp server binary and its required support libraries on macOS
- download the selected Gemma model
- write `config.json` and launch files onto the USB

### 1. Clone or download this repository

Open a terminal in the repository folder on your setup machine.

### 2. Plug in the USB drive

Identify the mounted USB path before running the setup command.

### 3. Run the setup script

#### Windows

Open PowerShell and run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup_windows.ps1 -USBDrive "E:" -Model "1b"
```

Replace `E:` with your USB drive letter.

#### macOS

Open Terminal and run:

```bash
chmod +x setup/setup_unix.sh
./setup/setup_unix.sh --drive /Volumes/MYUSB --model 1b
```

Replace `MYUSB` with your USB volume name.

#### Linux

Open Terminal and run:

```bash
chmod +x setup/setup_unix.sh
./setup/setup_unix.sh --drive /media/$USER/MYUSB --model 1b
```

Replace `MYUSB` with the mounted USB folder name used by your system.

### 4. Wait for setup to finish

The script checks your USB speed, downloads the required files, and prints a success message when everything is ready.

Yes, this automatically downloads the Gemma model too. If the model file already exists in `locali/models`, setup skips downloading it again.

## First Run

After setup is complete, safely eject the USB and use it on any supported machine.

### Windows

Run:

```powershell
E:\locali\start.bat
```

Or just double-click `locali\start.bat` from File Explorer on the USB drive.

### macOS

Run:

```bash
cd /Volumes/MYUSB/locali
./start.sh
```

### Linux

Run:

```bash
cd /media/$USER/MYUSB/locali
./start.sh
```

Your browser opens automatically. If it does not, open:

```text
http://127.0.0.1:8080
```

Press `Ctrl+C` in the terminal to stop the server.

## What Happens At Runtime

```text
locali/start.sh / locali/start.bat
  ├─ detects the operating system
  ├─ loads config.json from the USB drive
  ├─ starts the bundled llama.cpp server
  ├─ serves the model from the USB
  ├─ opens the local chat UI in your browser
  └─ keeps everything on localhost only
```

The host machine does not get software installed, registry changes, or persistent files. The only thing used from the host is CPU and RAM while the server is running.

## Expected USB Layout

After setup, the USB should look like this:

```text
YOUR_USB_DRIVE/
└── locali/
    ├── start.bat
    ├── start.sh
    ├── setup/
    │   ├── setup_windows.ps1
    │   └── setup_unix.sh
    ├── launcher/
    │   └── launch.py
    ├── bin/
    │   ├── windows/
    │   ├── linux/
    │   └── mac/
    ├── models/
    ├── ui/
    │   └── index.html
    └── config.json
```

## Configuration

Edit `locali/config.json` on the USB to change model and runtime settings.

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

| Setting | Meaning |
|---|---|
| `model` | GGUF filename stored in `/models` |
| `context_size` | Context window size in tokens |
| `port` | Port used by the local server |
| `gpu_layers` | `auto` uses CPU by default unless you set otherwise |
| `threads` | `auto` uses available CPU cores |
| `temperature` | Lower values are more deterministic |
| `open_browser` | Set to `false` to skip auto-opening the browser |

## Troubleshooting

- Model loading is slow: use a USB 3.x port, not USB 2.0.
- Port already in use: change `port` in `locali/config.json` and rerun `locali/start.sh` or `locali/start.bat`.
- Out of memory: close other apps or switch to the 1B model.
- macOS security warning: clear quarantine on the mac binary with `xattr -d com.apple.quarantine /Volumes/MYUSB/locali/bin/mac/llama-server`.
- Windows antivirus warning: compiled ML binaries can trigger false positives; add an exclusion or build from source.
- Connection failed in the browser: wait for the first load to finish and refresh.

## Project Structure

```text
locali/
├── README.md
├── start.bat
├── start.sh
├── config.json
├── setup/
│   ├── setup_windows.ps1
│   └── setup_unix.sh
├── launcher/
│   └── launch.py
├── bin/
│   ├── windows/llama-server.exe
│   ├── linux/llama-server
│   └── mac/llama-server
├── models/
├── ui/
│   └── index.html
└── docs/
    ├── contributing.md
    └── build-from-source.md
```

## Contributing

See `docs/contributing.md`. Helpful additions include native ARM Linux binaries, a native Apple Silicon build, progress feedback during setup, and more model presets.

## License

MIT. Gemma model weights are subject to [Google’s Gemma Terms of Use](https://ai.google.dev/gemma/terms).

## Credits

- [llama.cpp](https://github.com/ggml-org/llama.cpp) — inference engine
- [Google Gemma](https://ai.google.dev/gemma) — model family
- [Hugging Face](https://huggingface.co) — model hosting
