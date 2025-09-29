# ----------------------------
# PyGem Full Setup Script (Fixed)
# ----------------------------

param (
    [string]$Step = "all"
)

$ErrorActionPreference = "Stop"

# ----------------------------
# 0️⃣ Ensure Python is Installed
# ----------------------------
function Ensure-Python {
    $pythonCmd = "python"
    try {
        $version = & $pythonCmd --version 2>$null
        Write-Host "✅ Python is installed: $version"
    } catch {
        Write-Host "⚠️ Python not found. Installing Python..."
        $pythonInstaller = "$env:TEMP\python-installer.exe"
        $pythonUrl = "https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe"

        Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
        Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
        Remove-Item $pythonInstaller

        $version = & $pythonCmd --version 2>$null
        if ($version) {
            Write-Host "✅ Python installed successfully: $version"
            set PYTHONUTF8=1
            python -m pytest
            python app/main.py

        } else {
            Write-Error "❌ Python installation failed. Please install manually."
            exit 1
        }
    }
}

# ----------------------------
# 1️⃣ Create / Activate Virtual Environment
# ----------------------------
function Setup-Venv {
    Ensure-Python

    $venvPath = ".\venv"
    if (-Not (Test-Path $venvPath)) {
        python -m venv $venvPath
        Write-Host "✅ Created virtual environment at $venvPath"
    } else {
        Write-Host "✅ Virtual environment already exists"
    }

    $global:PythonExe = "$venvPath\Scripts\python.exe"
    $global:PipExe    = "$venvPath\Scripts\pip.exe"

    # Ensure the current session uses venv
    $env:PATH = "$venvPath\Scripts;$env:PATH"
}

# ----------------------------
# 2️⃣ Install / Restore Dependencies
# ----------------------------
function Install-Dependencies {
    Setup-Venv
    Write-Host "Upgrading pip..."
    & $PythonExe -m pip install --upgrade pip
    Write-Host "Installing dependencies from requirements.txt..."
    & $PipExe install -r requirements.txt
    Write-Host "✅ Dependencies installed"
}

# ----------------------------
# 3️⃣ Start Docker Compose and Wait for Services
# ----------------------------
function Start-Docker {
    if (-Not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker CLI not found. Please install Docker Desktop."
        exit 1
    }

    $composeFile = "docker-compose.yml"
    if (-Not (Test-Path $composeFile)) {
        Write-Error "❌ docker-compose.yml not found."
        exit 1
    }

    $services = @("pygem_postgres", "pygem_redis", "pygem_kafka", "pygem_zookeeper")
    $toStart = $false

    foreach ($svc in $services) {
        $running = docker ps -q -f "name=$svc"
        if ($running) {
            Write-Host "⚡ Container '$svc' is already running. Skipping start."
        } else {
            Write-Host "ℹ️ Container '$svc' not running. Will start services."
            $toStart = $true
        }
    }

    if ($toStart) {
        Write-Host "📥 Pulling Docker images from $composeFile..."
        docker compose -f $composeFile pull

        Write-Host "🚀 Starting Docker containers from $composeFile..."
        docker compose -f $composeFile up -d

        Write-Host "✅ Docker containers started"
    } else {
        Write-Host "All containers are already running."
    }

    docker ps

    # Wait for services
    Wait-PostgresReady -ContainerName "pygem_postgres" -Retries 15 -Delay 3
    Wait-RedisReady -ContainerName "pygem_redis" -Retries 15 -Delay 2
    Wait-KafkaReady -ContainerName "pygem_kafka" -Retries 20 -Delay 5
}

# ----------------------------
# Helper: Wait for PostgreSQL
# ----------------------------
function Wait-PostgresReady {
    param([string]$ContainerName, [int]$Retries=10, [int]$Delay=3)
    for ($i=1; $i -le $Retries; $i++) {
        try {
            $cid = docker ps -q -f "name=$ContainerName"
            if (-not $cid) { throw "Container not found" }
            $res = docker exec -i $cid pg_isready -U myuser
            if ($res -match "accepting connections") {
                Write-Host "✅ PostgreSQL is ready"
                return
            }
        } catch { Write-Host "[$i/$Retries] Waiting for PostgreSQL..." ; Start-Sleep -Seconds $Delay }
    }
    Write-Error "❌ PostgreSQL did not become ready in time"; exit 1
}

# ----------------------------
# Helper: Wait for Redis
# ----------------------------
function Wait-RedisReady {
    param([string]$ContainerName, [int]$Retries=10, [int]$Delay=2)
    for ($i=1; $i -le $Retries; $i++) {
        try {
            $cid = docker ps -q -f "name=$ContainerName"
            if (-not $cid) { throw "Container not found" }
            $res = docker exec -i $cid redis-cli ping
            if ($res -eq "PONG") {
                Write-Host "✅ Redis is ready"
                return
            }
        } catch { Write-Host "[$i/$Retries] Waiting for Redis..." ; Start-Sleep -Seconds $Delay }
    }
    Write-Error "❌ Redis did not become ready in time"; exit 1
}

# ----------------------------
# Helper: Wait for Kafka
# ----------------------------
function Wait-KafkaReady {
    param([string]$ContainerName, [int]$Retries=20, [int]$Delay=5)
    Write-Host "⏳ Waiting for Kafka to be ready..."
    for ($i=1; $i -le $Retries; $i++) {
        try {
            $cid = docker ps -q -f "name=$ContainerName"
            if (-not $cid) { throw "Container not found" }
            $logs = docker logs $cid --tail 20 2>$null
            if ($logs -match "started \(kafka.server.KafkaServer\)") {
                Write-Host "`n✅ Kafka is ready"
                return
            }
        } catch { }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds $Delay
    }
    Write-Host
    Write-Error "❌ Kafka did not become ready in time"; exit 1
}

# ----------------------------
# 4️⃣ Run Tests
# ----------------------------
function Run-Tests {
    # Ensure pytest & asyncio plugin installed in venv
    & $PipExe install pytest pytest-asyncio --quiet

    # Set PYTHONPATH so 'app' is discoverable
    $env:PYTHONPATH = (Get-Location)

    Write-Host "Running tests..."
    & $PythonExe -m pytest tests --maxfail=1 --disable-warnings -q
    Write-Host "✅ Tests completed"
}

# ----------------------------
# 5️⃣ Run Example Project
# ----------------------------
function Run-Project {
    $env:PYTHONPATH = (Get-Location)
    Write-Host "Starting example project..."
    & $PythonExe -m app.main
}

# ----------------------------
# 6️⃣ Menu / Execution
# ----------------------------
switch ($Step.ToLower()) {
    "venv"    { Setup-Venv }
    "deps"    { Install-Dependencies }
    "docker"  { Start-Docker }
    "tests"   { Install-Dependencies; Start-Docker; Run-Tests }
    "run"     { Install-Dependencies; Start-Docker; Run-Project }
    "all"     { Install-Dependencies; Start-Docker; Run-Tests; Run-Project }
    default   { Write-Host "Unknown step. Valid options: venv, deps, docker, tests, run, all" }
}
