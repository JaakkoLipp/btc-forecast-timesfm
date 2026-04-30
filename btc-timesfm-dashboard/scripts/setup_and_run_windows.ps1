param(
    [switch]$SkipTests,
    [switch]$SkipFrontendBuild,
    [switch]$SkipModelWarmup,
    [switch]$NoStart,
    [switch]$FakeForecast,
    [string]$InferenceDevice = $(if ($env:INFERENCE_DEVICE) { $env:INFERENCE_DEVICE } else { "cpu" }),
    [string]$ModelCheckpoint = $(if ($env:MODEL_CHECKPOINT) { $env:MODEL_CHECKPOINT } else { "google/timesfm-2.5-200m-pytorch" }),
    [int]$BackendPort = $(if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }),
    [int]$FrontendPort = $(if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }),
    [string]$NodeVersion = $(if ($env:NODE_VERSION) { $env:NODE_VERSION } else { "20.18.1" })
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VendorDir = Join-Path $ProjectRoot ".vendor"
$TimesFmDir = if ($env:TIMESFM_DIR) { $env:TIMESFM_DIR } else { Join-Path $VendorDir "timesfm" }
$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

$RunTests = -not $SkipTests
$RunFrontendBuild = -not $SkipFrontendBuild
$WarmModel = -not $SkipModelWarmup
$StartServers = -not $NoStart
$DevFakeForecast = if ($FakeForecast) { "true" } elseif ($env:DEV_FAKE_FORECAST) { $env:DEV_FAKE_FORECAST } else { "false" }
if ($DevFakeForecast -eq "true") {
    $WarmModel = $false
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

function Ensure-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        return
    }

    Write-Step "Installing uv"
    $installer = Join-Path $env:TEMP "uv-install.ps1"
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $installer
    powershell -ExecutionPolicy Bypass -File $installer

    $uvBin = Join-Path $env:USERPROFILE ".local\bin"
    $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
    $env:PATH = "$uvBin;$cargoBin;$env:PATH"
    Assert-Command "uv"
}

function Ensure-Node {
    if ((Get-Command node -ErrorAction SilentlyContinue) -and (Get-Command npm -ErrorAction SilentlyContinue)) {
        return
    }

    Write-Step "Installing local Node.js $NodeVersion"
    New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

    $arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
    $nodeName = "node-v$NodeVersion-win-$arch"
    $nodeZip = Join-Path $VendorDir "$nodeName.zip"
    $nodeDir = Join-Path $VendorDir $nodeName

    if (-not (Test-Path (Join-Path $nodeDir "node.exe"))) {
        Invoke-WebRequest -Uri "https://nodejs.org/dist/v$NodeVersion/$nodeName.zip" -OutFile $nodeZip
        if (Test-Path $nodeDir) {
            Remove-Item -LiteralPath $nodeDir -Recurse -Force
        }
        Expand-Archive -LiteralPath $nodeZip -DestinationPath $VendorDir -Force
    }

    $env:PATH = "$nodeDir;$env:PATH"
    Assert-Command "node"
    Assert-Command "npm"
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [string]$Label,
        [int]$Attempts = 60
    )

    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $Url | Out-Null
            Write-Host "$Label is ready: $Url"
            return
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "$Label did not become ready: $Url"
}

function Install-Backend {
    Write-Step "Creating Python 3.11 backend environment"
    uv venv --python 3.11 (Join-Path $BackendDir ".venv")

    Write-Step "Installing backend dependencies"
    uv pip install --python $BackendPython -e "$BackendDir[dev]"
}

function Install-TimesFm {
    if (Test-Path (Join-Path $TimesFmDir ".git")) {
        Write-Step "Updating Google Research TimesFM"
        git -C $TimesFmDir pull --ff-only
    }
    else {
        Write-Step "Cloning Google Research TimesFM"
        New-Item -ItemType Directory -Force -Path (Split-Path $TimesFmDir) | Out-Null
        git clone https://github.com/google-research/timesfm.git $TimesFmDir
    }

    Write-Step "Installing TimesFM with torch support"
    uv pip install --python $BackendPython -e "$TimesFmDir[torch]"
}

function Warm-TimesFmModel {
    if (-not $WarmModel) {
        return
    }

    Write-Step "Downloading and warming TimesFM checkpoint on $InferenceDevice"
    $env:INFERENCE_DEVICE = $InferenceDevice
    $env:MODEL_CHECKPOINT = $ModelCheckpoint

    @'
import os

import numpy as np
import torch
import timesfm

device = os.environ.get("INFERENCE_DEVICE", "cpu")
checkpoint = os.environ.get("MODEL_CHECKPOINT", "google/timesfm-2.5-200m-pytorch")

if device == "cuda" and not torch.cuda.is_available():
    raise SystemExit(
        "INFERENCE_DEVICE=cuda was requested, but CUDA is unavailable. "
        "Use INFERENCE_DEVICE=cpu for CPU-only evaluation."
    )

torch.set_float32_matmul_precision("high")
model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint)
model.compile(
    timesfm.ForecastConfig(
        max_context=128,
        max_horizon=8,
        normalize_inputs=True,
        use_continuous_quantile_head=True,
        force_flip_invariance=True,
        infer_is_positive=True,
        fix_quantile_crossing=True,
    )
)
point_forecast, quantile_forecast = model.forecast(
    horizon=1,
    inputs=[np.linspace(0, 1, 64)],
)
print(f"TimesFM warmup complete: point={float(point_forecast[0][0]):.6f}")
print(f"Quantiles available: {quantile_forecast is not None}")
'@ | & $BackendPython -
}

function Write-BackendEnv {
    $envPath = Join-Path $BackendDir ".env"
    if (-not (Test-Path $envPath)) {
        Write-Step "Creating backend\.env"
        Copy-Item -LiteralPath (Join-Path $BackendDir ".env.example") -Destination $envPath
    }
}

function Install-Frontend {
    Write-Step "Installing frontend dependencies"
    Push-Location $FrontendDir
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

function Run-Checks {
    if ($RunTests) {
        Write-Step "Running backend ruff and pytest"
        Push-Location $BackendDir
        try {
            & $BackendPython -m ruff check .
            & $BackendPython -m pytest
        }
        finally {
            Pop-Location
        }
    }

    if ($RunFrontendBuild) {
        Write-Step "Building frontend"
        Push-Location $FrontendDir
        try {
            npm run build
        }
        finally {
            Pop-Location
        }
    }
}

function Start-Servers {
    if (-not $StartServers) {
        Write-Step "Setup complete. Server start skipped."
        return
    }

    Write-Step "Starting backend"
    $backendEnv = @{
        APP_NAME = "BTC TimesFM Dashboard"
        CORS_ORIGINS = "http://localhost:$FrontendPort"
        DEV_FAKE_FORECAST = $DevFakeForecast
        INFERENCE_DEVICE = $InferenceDevice
        MODEL_CHECKPOINT = $ModelCheckpoint
        SQLITE_PATH = (Join-Path $BackendDir "btc_timesfm.db")
    }

    $backendCommand = @"
`$env:APP_NAME='$($backendEnv.APP_NAME)'
`$env:CORS_ORIGINS='$($backendEnv.CORS_ORIGINS)'
`$env:DEV_FAKE_FORECAST='$($backendEnv.DEV_FAKE_FORECAST)'
`$env:INFERENCE_DEVICE='$($backendEnv.INFERENCE_DEVICE)'
`$env:MODEL_CHECKPOINT='$($backendEnv.MODEL_CHECKPOINT)'
`$env:SQLITE_PATH='$($backendEnv.SQLITE_PATH)'
& '$BackendPython' -m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort
"@
    $backendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $BackendDir -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $backendCommand
    ) -PassThru

    Wait-ForHttp -Url "http://localhost:$BackendPort/health" -Label "Backend"

    Write-Step "Starting frontend"
    $frontendCommand = @"
`$env:VITE_API_BASE_URL='http://localhost:$BackendPort'
npm run dev -- --host 0.0.0.0 --port $FrontendPort
"@
    $frontendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $FrontendDir -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $frontendCommand
    ) -PassThru

    Wait-ForHttp -Url "http://localhost:$FrontendPort" -Label "Frontend"

    Write-Host ""
    Write-Host "Dashboard is running." -ForegroundColor Green
    Write-Host "  Frontend: http://localhost:$FrontendPort"
    Write-Host "  Backend:  http://localhost:$BackendPort"
    Write-Host "  API docs: http://localhost:$BackendPort/docs"
    Write-Host ""
    Write-Host "DEV_FAKE_FORECAST=$DevFakeForecast"
    Write-Host "INFERENCE_DEVICE=$InferenceDevice"
    Write-Host "MODEL_CHECKPOINT=$ModelCheckpoint"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both servers."

    try {
        while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
            Start-Sleep -Seconds 1
            $backendProcess.Refresh()
            $frontendProcess.Refresh()
        }
    }
    finally {
        if (-not $backendProcess.HasExited) {
            Stop-Process -Id $backendProcess.Id -Force
        }
        if (-not $frontendProcess.HasExited) {
            Stop-Process -Id $frontendProcess.Id -Force
        }
    }
}

if ($InferenceDevice -notin @("cpu", "cuda")) {
    throw "InferenceDevice must be 'cpu' or 'cuda'."
}

Assert-Command "git"
Ensure-Uv
Ensure-Node
Write-BackendEnv
Install-Backend

if ($DevFakeForecast -ne "true") {
    Install-TimesFm
    Warm-TimesFmModel
}
else {
    Write-Step "Skipping TimesFM install/warmup because DEV_FAKE_FORECAST=true"
}

Install-Frontend
Run-Checks
Start-Servers

