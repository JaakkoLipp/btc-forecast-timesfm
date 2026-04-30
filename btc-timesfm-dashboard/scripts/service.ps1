#Requires -Version 5.1
<#
.SYNOPSIS
  Start, stop, restart, inspect, or tail logs of the BTC TimesFM dashboard.

.DESCRIPTION
  Lightweight wrapper around the existing setup_and_run_windows.ps1. Assumes
  the backend venv and frontend node_modules already exist (run setup first).
  PIDs and logs live in <project>\.runtime\.

.PARAMETER Action
  start | stop | restart | status | logs

.EXAMPLE
  .\scripts\service.ps1 start
  .\scripts\service.ps1 stop
  .\scripts\service.ps1 status
  .\scripts\service.ps1 logs -Follow
  .\scripts\service.ps1 start -FakeForecast
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs")]
    [string]$Action,

    [int]$BackendPort = $(if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }),
    [int]$FrontendPort = $(if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }),
    [string]$InferenceDevice = $(if ($env:INFERENCE_DEVICE) { $env:INFERENCE_DEVICE } else { "cpu" }),
    [string]$ModelCheckpoint = $(if ($env:MODEL_CHECKPOINT) { $env:MODEL_CHECKPOINT } else { "google/timesfm-2.5-200m-pytorch" }),
    [switch]$FakeForecast,
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

$BackendPidFile = Join-Path $RuntimeDir "backend.pid"
$FrontendPidFile = Join-Path $RuntimeDir "frontend.pid"
$BackendLog = Join-Path $RuntimeDir "backend.log"
$FrontendLog = Join-Path $RuntimeDir "frontend.log"

$DevFakeForecast = if ($FakeForecast) { "true" } elseif ($env:DEV_FAKE_FORECAST) { $env:DEV_FAKE_FORECAST } else { "false" }

function Read-PidFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $content = (Get-Content -LiteralPath $Path -Raw).Trim()
    if (-not $content) { return $null }
    return [int]$content
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    if (-not $ProcessId) { return $false }
    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    if (-not $ProcessId) { return }
    if (-not (Test-ProcessAlive -ProcessId $ProcessId)) { return }
    & taskkill.exe /F /T /PID $ProcessId 2>&1 | Out-Null
}

function Test-Port {
    param([int]$Port)
    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if ($task.Wait(500) -and $client.Connected) {
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        if ($client) { $client.Close() }
    }
}

function Wait-ForPort {
    param([int]$Port, [string]$Label, [int]$Attempts = 60)
    for ($i = 0; $i -lt $Attempts; $i++) {
        if (Test-Port -Port $Port) {
            Write-Host "$Label is ready on port $Port" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "$Label did not become ready on port $Port (check logs)" -ForegroundColor Yellow
    return $false
}

function Write-StatusLine {
    param([string]$Label, [int]$ProcessId, [int]$Port)
    $alive = Test-ProcessAlive -ProcessId $ProcessId
    $listening = Test-Port -Port $Port

    if ($alive -and $listening) {
        Write-Host ("  {0,-9} running (pid {1}, port {2})" -f $Label, $ProcessId, $Port) -ForegroundColor Green
    } elseif ($alive) {
        Write-Host ("  {0,-9} process up, not yet listening (pid {1}, port {2})" -f $Label, $ProcessId, $Port) -ForegroundColor Yellow
    } elseif ($listening) {
        Write-Host ("  {0,-9} port {1} in use but no PID file (started elsewhere?)" -f $Label, $Port) -ForegroundColor Yellow
    } else {
        Write-Host ("  {0,-9} stopped" -f $Label) -ForegroundColor DarkGray
    }
}

function Invoke-Status {
    $backendPid = Read-PidFile $BackendPidFile
    $frontendPid = Read-PidFile $FrontendPidFile
    Write-Host "BTC TimesFM Dashboard:"
    Write-StatusLine -Label "Backend"  -ProcessId $backendPid  -Port $BackendPort
    Write-StatusLine -Label "Frontend" -ProcessId $frontendPid -Port $FrontendPort
}

function Invoke-Start {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
        throw "Backend venv not found at $BackendPython. Run scripts\setup_and_run_windows.ps1 -NoStart first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
        throw "Frontend deps missing. Run scripts\setup_and_run_windows.ps1 -NoStart first."
    }

    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

    $existing = Read-PidFile $BackendPidFile
    if (Test-ProcessAlive -ProcessId $existing) {
        Write-Host "Backend already running (pid $existing). Use 'restart' to bounce it." -ForegroundColor Yellow
    } else {
        Write-Host "Starting backend..."
        $backendCommand = @"
`$ErrorActionPreference = 'Continue'
`$env:APP_NAME = 'BTC TimesFM Dashboard'
`$env:CORS_ORIGINS = 'http://localhost:$FrontendPort'
`$env:DEV_FAKE_FORECAST = '$DevFakeForecast'
`$env:INFERENCE_DEVICE = '$InferenceDevice'
`$env:MODEL_CHECKPOINT = '$ModelCheckpoint'
`$env:SQLITE_PATH = '$($BackendDir -replace "'", "''")\btc_timesfm.db'
& '$BackendPython' -m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort *>&1 | Tee-Object -FilePath '$BackendLog'
"@
        $proc = Start-Process powershell.exe `
            -WindowStyle Hidden `
            -WorkingDirectory $BackendDir `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) `
            -PassThru
        Set-Content -LiteralPath $BackendPidFile -Value $proc.Id -Encoding ascii
        Wait-ForPort -Port $BackendPort -Label "Backend" | Out-Null
    }

    $existing = Read-PidFile $FrontendPidFile
    if (Test-ProcessAlive -ProcessId $existing) {
        Write-Host "Frontend already running (pid $existing)." -ForegroundColor Yellow
    } else {
        Write-Host "Starting frontend..."
        $frontendCommand = @"
`$ErrorActionPreference = 'Continue'
`$env:VITE_API_BASE_URL = 'http://localhost:$BackendPort'
npm run dev -- --host 0.0.0.0 --port $FrontendPort *>&1 | Tee-Object -FilePath '$FrontendLog'
"@
        $proc = Start-Process powershell.exe `
            -WindowStyle Hidden `
            -WorkingDirectory $FrontendDir `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) `
            -PassThru
        Set-Content -LiteralPath $FrontendPidFile -Value $proc.Id -Encoding ascii
        Wait-ForPort -Port $FrontendPort -Label "Frontend" | Out-Null
    }

    Write-Host ""
    Invoke-Status
    Write-Host ""
    Write-Host "  http://localhost:$FrontendPort  (frontend)"
    Write-Host "  http://localhost:$BackendPort   (backend)"
    Write-Host "  http://localhost:$BackendPort/docs   (API docs)"
    Write-Host ""
    Write-Host "  DEV_FAKE_FORECAST=$DevFakeForecast  INFERENCE_DEVICE=$InferenceDevice"
    Write-Host ""
    Write-Host "  Logs:    .\scripts\service.ps1 logs -Follow"
    Write-Host "  Stop:    .\scripts\service.ps1 stop"
}

function Invoke-Stop {
    $frontendPid = Read-PidFile $FrontendPidFile
    if ($frontendPid) {
        Write-Host "Stopping frontend (pid $frontendPid)..."
        Stop-ProcessTree -ProcessId $frontendPid
        Remove-Item -LiteralPath $FrontendPidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "Frontend not tracked."
    }

    $backendPid = Read-PidFile $BackendPidFile
    if ($backendPid) {
        Write-Host "Stopping backend (pid $backendPid)..."
        Stop-ProcessTree -ProcessId $backendPid
        Remove-Item -LiteralPath $BackendPidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "Backend not tracked."
    }

    Write-Host ""
    Invoke-Status
}

function Invoke-Restart {
    Invoke-Stop
    Start-Sleep -Seconds 1
    Invoke-Start
}

function Invoke-Logs {
    $haveBackend = Test-Path -LiteralPath $BackendLog
    $haveFrontend = Test-Path -LiteralPath $FrontendLog
    if (-not $haveBackend -and -not $haveFrontend) {
        Write-Host "No logs found in $RuntimeDir. Has the service been started?" -ForegroundColor Yellow
        return
    }

    if ($Follow) {
        if ($haveBackend) {
            Write-Host "--- backend.log (last 20) ---" -ForegroundColor Cyan
            Get-Content -LiteralPath $BackendLog -Tail 20
        }
        if ($haveFrontend) {
            Write-Host ""
            Write-Host "--- frontend.log (last 20) ---" -ForegroundColor Cyan
            Get-Content -LiteralPath $FrontendLog -Tail 20
        }
        Write-Host ""
        Write-Host "Following backend log (Ctrl+C to exit). Frontend log: $FrontendLog" -ForegroundColor Cyan
        Get-Content -LiteralPath $BackendLog -Tail 0 -Wait
    } else {
        if ($haveBackend) {
            Write-Host "--- backend.log (last 50) ---" -ForegroundColor Cyan
            Get-Content -LiteralPath $BackendLog -Tail 50
        }
        if ($haveFrontend) {
            Write-Host ""
            Write-Host "--- frontend.log (last 50) ---" -ForegroundColor Cyan
            Get-Content -LiteralPath $FrontendLog -Tail 50
        }
    }
}

if (-not $Action) {
    Write-Host "Usage: .\scripts\service.ps1 <start|stop|restart|status|logs> [-FakeForecast] [-Follow]"
    Write-Host "       .\scripts\service.ps1 -BackendPort 9000 -FrontendPort 4000 start"
    exit 1
}

switch ($Action) {
    "start"   { Invoke-Start }
    "stop"    { Invoke-Stop }
    "restart" { Invoke-Restart }
    "status"  { Invoke-Status }
    "logs"    { Invoke-Logs }
}
