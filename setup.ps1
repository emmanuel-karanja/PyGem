# ----------------------------
# Modular Monolith Setup Script
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

        # Verify installation
        $version = & $pythonCmd --version 2>$null
        if ($version) {
            Write-Host "✅ Python installed successfully: $version"
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

    # Activate venv for current session
    Write-Host "Activating virtual environment..."
    & "$venvPath\Scripts\Activate.ps1"
}

# ----------------------------
# 2️⃣ Install / Restore Dependencies
# ----------------------------
function Install-Dependencies {
    Write-Host "Upgrading pip..."
    python -m pip install --upgrade pip
    Write-Host "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    Write-Host "✅ Dependencies installed"
}

# ----------------------------
# 3️⃣ Start Docker Compose
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

    Write-Host "Starting Docker containers from $composeFile..."
    docker-compose up -d
    Write-Host "✅ Docker containers started"
}

# ----------------------------
# 4️⃣ Run Tests
# ----------------------------
function Run-Tests {
    Write-Host "Installing pytest dependencies..."
    pip install pytest pytest-asyncio --quiet
    Write-Host "Running tests..."
    pytest tests --maxfail=1 --disable-warnings -q
    Write-Host "✅ Tests completed"
}

# ----------------------------
# 5️⃣ Run Example Project
# ----------------------------
function Run-Project {
    Write-Host "Starting example project..."
    python -m app.main
}

# ----------------------------
# 6️⃣ Menu / Execution
# ----------------------------
switch ($Step.ToLower()) {
    "venv"    { Setup-Venv }
    "deps"    { Setup-Venv; Install-Dependencies }
    "docker"  { Start-Docker }
    "tests"   { Setup-Venv; Install-Dependencies; Run-Tests }
    "run"     { Setup-Venv; Install-Dependencies; Start-Docker; Run-Project }
    "all"     { Setup-Venv; Install-Dependencies; Start-Docker; Run-Tests; Run-Project }
    default   { Write-Host "Unknown step. Valid options: venv, deps, docker, tests, run, all" }
}
