param(
    [Parameter(Mandatory=$true)]
    [string]$USBDrive,

    [Parameter(Mandatory=$false)]
    [string]$Model = ""
)

# ============================================================
#  Locali Setup Script — Windows
#  Prepares your USB drive with Gemma + llama.cpp binaries
#  Nothing is written to the host system.
# ============================================================

$ErrorActionPreference = "Stop"

# --- Colors ---
function Write-Green  { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Yellow { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Red    { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Info   { param($msg) Write-Host "  → $msg" -ForegroundColor Cyan }
function Write-Header { param($msg) Write-Host "`n$msg" -ForegroundColor White }
function Select-Model {
    Write-Host ""
    Write-Host "Choose which model(s) to install:"
    Write-Host "  1) Gemma 3 1B  (~0.8 GB, fastest)"
    Write-Host "  2) Gemma 3 4B  (~2.5 GB, better quality)"
    Write-Host "  3) Both         (~3.3 GB total)"
    $choice = Read-Host "Select 1, 2, or 3 [1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }
    switch ($choice) {
        "1" { return "1b" }
        "2" { return "4b" }
        "3" { return "both" }
        default { Write-Red "Invalid selection. Choose 1, 2, or 3."; exit 1 }
    }
}

if ([string]::IsNullOrWhiteSpace($Model)) {
    $Model = Select-Model
}

Write-Host @"

  ██████╗  ██████╗  ██████╗██╗  ██╗███████╗████████╗██╗     ██╗     ███╗   ███╗
  ██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝██║     ██║     ████╗ ████║
  ██████╔╝██║   ██║██║     █████╔╝ █████╗     ██║   ██║     ██║     ██╔████╔██║
  ██╔═══╝ ██║   ██║██║     ██╔═██╗ ██╔══╝     ██║   ██║     ██║     ██║╚██╔╝██║
  ██║     ╚██████╔╝╚██████╗██║  ██╗███████╗   ██║   ███████╗███████╗██║ ╚═╝ ██║
  ╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚══════╝╚═╝     ╚═╝

  Windows Setup  |  Model: Gemma 3 $Model  |  Target: $USBDrive
"@ -ForegroundColor Blue

# --- Validate USB Drive ---
Write-Header "[ 1/6 ] Validating USB Drive..."

$drivePath = $USBDrive.TrimEnd('\')
if (-not (Test-Path $drivePath)) {
    Write-Red "Drive '$USBDrive' not found. Plug in your USB and try again."
    exit 1
}

$installRoot = Join-Path $drivePath "locali"

$drive = Get-PSDrive -Name $drivePath.TrimEnd(':') -ErrorAction SilentlyContinue
if ($null -eq $drive) {
    Write-Red "Cannot access drive '$USBDrive'."
    exit 1
}

if ($Model -notin @("1b", "4b", "both")) {
    Write-Red "Model must be '1b', '4b', or 'both'."
    exit 1
}

$freeGB = [math]::Round($drive.Free / 1GB, 1)
Write-Green "Drive found. Free space: ${freeGB} GB"

$requiredGB = if ($Model -eq "both") { 6 } elseif ($Model -eq "4b") { 4 } else { 2 }
if ($freeGB -lt $requiredGB) {
    Write-Red "Not enough space. Need ${requiredGB} GB, have ${freeGB} GB."
    exit 1
}

Write-Host ""
Write-Info "This will download llama.cpp binaries and selected model(s) to your USB."
$confirm = Read-Host "Continue? [Y/n]"
if ([string]::IsNullOrWhiteSpace($confirm)) { $confirm = "Y" }
if ($confirm -notmatch "^[Yy]$") {
    Write-Red "Setup cancelled by user."
    exit 1
}

# --- Check USB Speed ---
Write-Header "[ 2/6 ] Checking USB Speed..."

$testFile = Join-Path $drivePath "speedtest_tmp.dat"
$testBytes = 50MB
$buf = New-Object byte[] $testBytes
(New-Object Random).NextBytes($buf)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
[System.IO.File]::WriteAllBytes($testFile, $buf)
$sw.Stop()
Remove-Item $testFile -Force

$speedMBs = [math]::Round($testBytes / $sw.Elapsed.TotalSeconds / 1MB, 1)
Write-Info "Write speed: ${speedMBs} MB/s"

if ($speedMBs -lt 20) {
    Write-Red "USB write speed too slow (${speedMBs} MB/s). USB 3.0 required (min ~80 MB/s)."
    exit 1
} elseif ($speedMBs -lt 80) {
    Write-Yellow "Speed is low (${speedMBs} MB/s). Performance may be poor. USB 3.0 recommended."
} else {
    Write-Green "Speed OK: ${speedMBs} MB/s"
}

# --- Create Directory Structure ---
Write-Header "[ 3/6 ] Creating directory structure on USB..."

$dirs = @("launcher", "bin\windows", "bin\linux", "bin\mac", "models", "ui", "docs", "setup")
foreach ($dir in $dirs) {
    $fullPath = Join-Path $installRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-Green "Directories created"

# --- Download llama.cpp Windows Binary ---
Write-Header "[ 4/6 ] Downloading llama.cpp inference engine..."

Write-Info "Fetching latest llama.cpp release info..."
$releaseApiUrl = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
$releaseJson = Invoke-RestMethod -Uri $releaseApiUrl -UseBasicParsing
$asset = $releaseJson.assets | Where-Object { $_.name -match "bin-win-cpu-x64.zip" -or $_.name -match "bin-win-avx2-x64.zip" } | Select-Object -First 1

if ($null -eq $asset) {
    Write-Red "Could not find a suitable llama.cpp binary in the latest release."
    exit 1
}

$llamaUrl = $asset.browser_download_url
$llamaZip  = Join-Path $env:TEMP "llama_win.zip"
$llamaDir  = Join-Path $env:TEMP "llama_win"

$serverExePath = Join-Path $installRoot "bin\windows\llama-server.exe"
$existingDll = Get-ChildItem -Path (Join-Path $installRoot "bin\windows") -Filter "*.dll" -ErrorAction SilentlyContinue | Select-Object -First 1

if ((Test-Path $serverExePath) -and ($null -ne $existingDll)) {
    Write-Green "llama.cpp engine already installed"
} else {
    Write-Info "Downloading from GitHub releases..."
    Invoke-WebRequest -Uri $llamaUrl -OutFile $llamaZip -UseBasicParsing

    Write-Info "Extracting..."
    if (Test-Path $llamaDir) { Remove-Item $llamaDir -Recurse -Force }
    Expand-Archive -Path $llamaZip -DestinationPath $llamaDir -Force

    $serverExe = Get-ChildItem -Path $llamaDir -Filter "llama-server.exe" -Recurse | Select-Object -First 1
    if ($null -eq $serverExe) {
        Write-Red "Could not find llama-server.exe in the downloaded package."
        exit 1
    }

    Copy-Item $serverExe.FullName -Destination $serverExePath -Force

    # Copy required DLLs
    Get-ChildItem -Path $serverExe.DirectoryName -Filter "*.dll" | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $installRoot "bin\windows\") -Force
    }

    Remove-Item $llamaZip -Force
    Remove-Item $llamaDir -Recurse -Force
    Write-Green "llama.cpp engine installed"
}

# --- Download Gemma Model ---
Write-Header "[ 5/6 ] Downloading Gemma 3 $Model model (GGUF)..."

$modelsToInstall = @()
if ($Model -eq "both") {
    $modelsToInstall = @(
        @{ File = "gemma-3-1b-it-q4_k_m.gguf"; Url = "https://huggingface.co/lmstudio-community/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf" },
        @{ File = "gemma-3-4b-it-q4_k_m.gguf"; Url = "https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf" }
    )
} elseif ($Model -eq "1b") {
    $modelsToInstall = @(
        @{ File = "gemma-3-1b-it-q4_k_m.gguf"; Url = "https://huggingface.co/lmstudio-community/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf" }
    )
} else {
    $modelsToInstall = @(
        @{ File = "gemma-3-4b-it-q4_k_m.gguf"; Url = "https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf" }
    )
}

$modelFiles = @()
foreach ($model in $modelsToInstall) {
    $modelFile = $model.File
    $modelUrl = $model.Url
    $modelPath = Join-Path $installRoot "models\$modelFile"
    $modelFiles += $modelFile

    Write-Info "This may take a few minutes depending on your internet speed..."
    Write-Info "Model: $modelFile"

    if (Test-Path $modelPath) {
        Write-Green "Model already installed: $modelFile"
    } else {
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($modelUrl, $modelPath)
        Write-Green "Model downloaded: $modelFile"
    }
}

$modelFile = $modelFiles[0]

# --- Write Config and Scripts ---
Write-Header "[ 6/6 ] Writing config and launcher scripts..."

# config.json
$config = @{
    model        = $modelFile
    models       = $modelFiles
    context_size = 2048
    port         = 8080
    gpu_layers   = "auto"
    threads      = "auto"
    temperature  = 0.7
    open_browser = $true
} | ConvertTo-Json -Depth 3

$config | Out-File -FilePath (Join-Path $installRoot "config.json") -Encoding UTF8

# start.bat inside the Locali folder
$startBat = @"
@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
echo.
echo  Locali - Starting local AI...
echo.
python launcher\launch.py 2>nul
if errorlevel 1 (
    set "MODEL_FILE="
    for /f "tokens=2 delims=:," %%a in ('findstr /i "\"model\"" config.json') do set "MODEL_FILE=%%a"
    set "MODEL_FILE=!MODEL_FILE:"=!"
    set "MODEL_FILE=!MODEL_FILE: =!"
    if not defined MODEL_FILE set "MODEL_FILE=$modelFile"
    bin\windows\llama-server.exe --model models\!MODEL_FILE! --port 8080 --host 127.0.0.1
)
pause
"@
$startBat | Out-File -FilePath (Join-Path $installRoot "start.bat") -Encoding ASCII

Write-Green "Config and launcher written"

# --- Install optional Python dependencies ---
Write-Header "Installing optional Python dependencies..."
$psutilInstalled = $false
$pythonExes = @("python3", "python", "py")

foreach ($py in $pythonExes) {
    if ((Get-Command $py -ErrorAction SilentlyContinue) -ne $null) {
        Write-Info "Found Python: $py"
        Write-Info "Installing psutil..."
        & $py -m pip install --user psutil 2>&1 | Tee-Object -Variable pipOutput | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Green "psutil installed for resource monitoring"
            $psutilInstalled = $true
            break
        } else {
            Write-Yellow "Installation with $py failed, trying next..."
        }
    }
}

if (-not $psutilInstalled) {
    Write-Red "psutil installation failed - stats will not display in terminal"
    Write-Yellow "To fix, manually run: pip install --user psutil"
}

# --- Done ---
Write-Host @"

  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║   ✅  Locali setup complete!                      ║
  ║                                                      ║
    ║   To start on any Windows machine:                   ║
    ║   → Double-click  locali\start.bat  on the USB drive  ║
    ║   → Or run: .\locali\start.bat                       ║
  ║                                                      ║
  ║   Then open:  http://localhost:8080                  ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Green
