# ----------------------------
# PyGem Bootstrap Script (Quarkus-inspired)
# ----------------------------

param (
    [string]$Command = "dev",
    [string[]]$Args = @()
)

$ErrorActionPreference = "Stop"

# ----------------------------
# 🎯 Main Functions
# ----------------------------

function Start-Development {
    Write-Host "🚀 Starting PyGem Development Environment..."
    Setup-Environment
    Start-Services -DevMode $true
    Start-Application
}

function Start-Production {
    Write-Host "🏭 Starting PyGem Production Environment..."
    Setup-Environment
    Start-Services -DevMode $false
    Start-Application
}

function Start-Testing {
    Write-Host "🧪 Starting PyGem Testing Environment..."
    Setup-Environment
    Start-Services -DevMode $true
    Run-Tests
}

function Build-Application {
    Write-Host "🔨 Building PyGem Application..."
    Build-DockerImage
}

function Deploy-Application {
    Write-Host "🚀 Deploying PyGem Application..."
    Build-Application
    Deploy-ToProduction
}

# ----------------------------
# 🔧 Environment Setup
# ----------------------------

function Setup-Environment {
    Write-Host "📦 Setting up environment..."
    
    # Check Python
    Ensure-Python
    
    # Setup virtual environment
    Setup-VirtualEnvironment
    
    # Install dependencies
    Install-Dependencies
    
    Write-Host "✅ Environment setup complete"
}

function Ensure-Python {
    $pythonCmd = "python"
    try {
        $version = & $pythonCmd --version 2>$null
        Write-Host "✅ Python is installed: $version"
    } catch {
        Write-Host "⚠️ Python not found. Please install Python 3.11+"
        exit 1
    }
}

function Setup-VirtualEnvironment {
    $venvPath = ".\venv"
    if (-Not (Test-Path $venvPath)) {
        Write-Host "📦 Creating virtual environment..."
        python -m venv $venvPath
        Write-Host "✅ Virtual environment created"
    }
    
    # Activate virtual environment
    $global:PythonExe = "$venvPath\Scripts\python.exe"
    $global:PipExe = "$venvPath\Scripts\pip.exe"
    $env:PATH = "$venvPath\Scripts;$env:PATH"
}

function Install-Dependencies {
    Write-Host "📚 Installing dependencies..."
    
    & $PythonExe -m pip install --upgrade pip --quiet
    & $PipExe install -r requirements.txt --quiet
    
    Write-Host "✅ Dependencies installed"
}

# ----------------------------
# 🐳 Service Management
# ----------------------------

function Start-Services {
    param([bool]$DevMode = $true)
    
    if (-Not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "⚠️ Docker not found. Please install Docker Desktop."
        return
    }
    
    Write-Host "🐳 Starting infrastructure services..."
    
    # Create development config if needed
    if ($DevMode) {
        Create-DevConfig
    }
    
    # Start Docker Compose
    docker compose -f docker-compose.yml up -d
    
    # Wait for services to be ready
    if ($DevMode) {
        Wait-ServicesReady -DevMode $true
    } else {
        Wait-ServicesReady -DevMode $false
    }
    
    Write-Host "✅ Infrastructure services ready"
}

function Create-DevConfig {
    $devConfig = @"
# Development configuration
profile: dev
server:
  host: 0.0.0.0
  port: 8080
messaging:
  transport: memory
logging:
  level: DEBUG
  format: structured
health:
  enabled: true
"@
    
    Set-Content -Path "pygem.yml" -Value $devConfig
    Write-Host "📝 Created development configuration"
}

function Wait-ServicesReady {
    param([bool]$DevMode = $true)
    
    if ($DevMode) {
        # For development, just basic checks
        Wait-PostgresReady
        Wait-RedisReady
    } else {
        # For production, wait for all services
        Wait-PostgresReady
        Wait-RedisReady
        Wait-KafkaReady
    }
}

function Wait-PostgresReady {
    $containerName = "pygem_postgres"
    $maxRetries = 15
    $delay = 3
    
    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            $cid = docker ps -q -f "name=$containerName"
            if ($cid) {
                $res = docker exec -i $cid pg_isready -U myuser 2>$null
                if ($res -match "accepting connections") {
                    Write-Host "✅ PostgreSQL ready"
                    return
                }
            }
        } catch {}
        Write-Host "⏳ Waiting for PostgreSQL... ($i/$maxRetries)"
        Start-Sleep -Seconds $delay
    }
    Write-Warning "⚠️ PostgreSQL not ready, continuing anyway"
}

function Wait-RedisReady {
    $containerName = "pygem_redis"
    $maxRetries = 10
    $delay = 2
    
    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            $cid = docker ps -q -f "name=$containerName"
            if ($cid) {
                $res = docker exec -i $cid redis-cli ping 2>$null
                if ($res -eq "PONG") {
                    Write-Host "✅ Redis ready"
                    return
                }
            }
        } catch {}
        Write-Host "⏳ Waiting for Redis... ($i/$maxRetries)"
        Start-Sleep -Seconds $delay
    }
    Write-Warning "⚠️ Redis not ready, continuing anyway"
}

function Wait-KafkaReady {
    $containerName = "pygem_kafka"
    $maxRetries = 20
    $delay = 5
    
    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            $cid = docker ps -q -f "name=$containerName"
            if ($cid) {
                $logs = docker logs $cid --tail 10 2>$null
                if ($logs -match "started \(kafka.server.KafkaServer\)") {
                    Write-Host "✅ Kafka ready"
                    return
                }
            }
        } catch {}
        Write-Host "⏳ Waiting for Kafka... ($i/$maxRetries)"
        Start-Sleep -Seconds $delay
    }
    Write-Warning "⚠️ Kafka not ready, continuing anyway"
}

# ----------------------------
# 🚀 Application Management
# ----------------------------

function Start-Application {
    Write-Host "🎯 Starting PyGem application..."
    
    # Set environment for application
    $env:PYTHONPATH = (Get-Location)
    $env:PYGEM_CONFIG = "pygem.yml"
    
    # Start the application
    & $PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
}

function Run-Tests {
    Write-Host "🧪 Running PyGem tests..."
    
    # Install test dependencies
    & $PipExe install pytest pytest-asyncio --quiet
    
    # Set environment for testing
    $env:PYTHONPATH = (Get-Location)
    $env:PYGEM_PROFILE = "test"
    
    # Run tests
    & $PythonExe -m pytest tests -v --tb=short
}

# ----------------------------
# 🐳 Docker Functions
# ----------------------------

function Build-DockerImage {
    Write-Host "🔨 Building PyGem Docker image..."
    
    $imageName = "pygem-app:latest"
    
    docker build -t $imageName .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker image built: $imageName"
    } else {
        Write-Error "❌ Docker build failed"
        exit 1
    }
}

function Deploy-ToProduction {
    Write-Host "🚀 Deploying to production..."
    
    # Tag for production
    docker tag pygem-app:latest pygem-app:prod
    
    # This would typically push to registry and deploy
    Write-Host "📝 Production deployment logic goes here"
    Write-Host "✅ Deployment complete (simulated)"
}

# ----------------------------
# 🎮 Command Router
# ----------------------------

switch ($Command.ToLower()) {
    "dev" {
        Start-Development
    }
    "prod" {
        Start-Production  
    }
    "test" {
        Start-Testing
    }
    "build" {
        Build-Application
    }
    "deploy" {
        Deploy-Application
    }
    "clean" {
        Write-Host "🧹 Cleaning up..."
        Stop-Services
        if (Test-Path ".\venv") {
            Remove-Item -Recurse -Force ".\venv"
            Write-Host "✅ Virtual environment removed"
        }
        if (Test-Path "pygem.yml") {
            Remove-Item "pygem.yml"
            Write-Host "✅ Configuration removed"
        }
    }
    default {
        Write-Host "❌ Unknown command: $Command"
        Write-Host ""
        Write-Host "Available commands:"
        Write-Host "  dev     - Start development environment"
        Write-Host "  prod    - Start production environment"
        Write-Host "  test    - Run tests"
        Write-Host "  build   - Build Docker image"
        Write-Host "  deploy  - Deploy to production"
        Write-Host "  clean   - Clean up environment"
        exit 1
    }
}

# ----------------------------
# Helper: Stop Services
# ----------------------------
function Stop-Services {
    Write-Host "🛑 Stopping services..."
    docker compose -f docker-compose.yml down
    Write-Host "✅ Services stopped"
}