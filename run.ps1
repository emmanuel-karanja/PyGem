# ----------------------------
# PyGem Application Runner
# ----------------------------

param (
    [string]$Command = "run",
    [string]$ServerHost = "",
    [int]$ServerPort = 0
)

$ErrorActionPreference = "Stop"

# ----------------------------
# 🚀 Application Commands
# ----------------------------

function Start-Application {
    param([string]$OverrideHost = "", [int]$OverridePort = 0)
    
    Write-Host "🚀 Starting PyGem Application..."
    
    # Setup environment
    Setup-Environment
    
    # Override with parameters
    if ($OverrideHost) {
        $env:PYGEM_SERVER_HOST = $OverrideHost
    }
    if ($OverridePort -gt 0) {
        $env:PYGEM_SERVER_PORT = $OverridePort
    }
    
    # Start application
    $env:PYTHONPATH = (Get-Location)
    $env:PYGEM_CONFIG = "pygem.yml"
    
    Write-Host "🎯 Application starting..."
    Write-Host "   Config: $env:PYGEM_CONFIG"
    Write-Host "   Python: $((Get-Command python).Source)"
    Write-Host "   Profile: $env:PYGEM_PROFILE"
    
    & $global:PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8081
}

function Start-Application-Docker {
    Write-Host "🐳 Starting PyGem Application in Docker..."
    
    Build-DockerImage
    
    $containerName = "pygem-app"
    $imageName = "pygem-app:latest"
    
    # Stop and remove existing container
    $existing = docker ps -aq -f "name=$containerName"
    if ($existing) {
        Write-Host "🛑 Stopping existing container..."
        docker stop $containerName | Out-Null
        docker rm $containerName | Out-Null
    }
    
    # Run new container
    docker run -d `
        --name $containerName `
        -p 8080:8080 `
        --env-file .env `
        $imageName
    
    Write-Host "✅ Container started: http://localhost:8080"
    Write-Host "📜 Following logs..."
    docker logs -f $containerName
}

# ----------------------------
# 🔧 Environment Setup
# ----------------------------

function Setup-Environment {
    # Check virtual environment
    $venvPath = ".\venv"
    if (-Not (Test-Path $venvPath)) {
        Write-Host "⚠️ Virtual environment not found. Run './bootstrap.ps1 dev' first."
        exit 1
    }
    
    $global:PythonExe = "$venvPath\Scripts\python.exe"
    $global:PipExe = "$venvPath\Scripts\pip.exe"
    $env:PATH = "$venvPath\Scripts;$env:PATH"
    
    Write-Host "✅ Environment configured"
}

# ----------------------------
# 🐳 Docker Functions
# ----------------------------

function Build-DockerImage {
    Write-Host "🔨 Building Docker image..."
    
    $imageName = "pygem-app:latest"
    
    docker build -t $imageName --no-cache .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker image built: $imageName"
    } else {
        Write-Error "❌ Docker build failed"
        exit 1
    }
}

# ----------------------------
# 🧪 Test Functions
# ----------------------------

function Run-Tests {
    Write-Host "🧪 Running tests..."
    
    Setup-Environment
    
    # Install test dependencies if needed
    & $global:PipExe install pytest pytest-asyncio --quiet
    
    # Run tests
    $env:PYTHONPATH = (Get-Location)
    & $global:PythonExe -m pytest tests -v
}

function Run-IntegrationTests {
    Write-Host "🧪 Running integration tests..."
    
    # Start services for integration tests
    docker compose -f docker-compose.yml up -d
    Start-Sleep -Seconds 10
    
    try {
        Setup-Environment
        $env:PYGEM_PROFILE = "test"
        
        & $global:PythonExe -m pytest tests/integration -v
    } finally {
        docker compose -f docker-compose.yml down
    }
}

# ----------------------------
# 📊 Monitoring Functions
# ----------------------------

function Show-Logs {
    Write-Host "📜 Showing application logs..."
    
    $containerName = "pygem-app"
    $logs = docker logs $containerName --tail 50
    
    if ($logs) {
        Write-Host $logs
    } else {
        Write-Host "No logs found. Is the container running?"
    }
}

function Show-Status {
    Write-Host "📊 PyGem Application Status"
    Write-Host "================================"
    
    # Check container status
    $containerName = "pygem-app"
    $containerInfo = docker ps -f "name=$containerName" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    if ($containerInfo) {
        Write-Host "✅ Container Status:"
        Write-Host $containerInfo
    } else {
        Write-Host "❌ Container not running"
    }
    
    # Check services
    Write-Host ""
    Write-Host "🐳 Infrastructure Services:"
    $services = docker compose -f docker-compose.yml ps
    Write-Host $services
    
    Write-Host ""
    Write-Host "🌐 Application URLs:"
    Write-Host "   Health: http://localhost:8080/health"
    Write-Host "   API:    http://localhost:8080/docs"
}

# ----------------------------
# 🧹 Cleanup Functions
# ----------------------------

function Cleanup-All {
    Write-Host "🧹 Full cleanup..."
    
    # Stop and remove containers
    Write-Host "🛑 Stopping containers..."
    docker compose -f docker-compose.yml down
    docker stop pygem-app | Out-Null
    docker rm pygem-app | Out-Null
    
    # Remove images
    Write-Host "🗑️ Removing images..."
    docker rmi pygem-app:latest | Out-Null
    
    # Clean up virtual environment (optional)
    Write-Host "🧹 Clean venv? (y/N)"
    $choice = Read-Host
    if ($choice -eq "y") {
        Remove-Item -Recurse -Force ".\venv"
        Write-Host "✅ Virtual environment removed"
    }
    
    Write-Host "✅ Cleanup complete"
}

# ----------------------------
# 🎮 Command Router
# ----------------------------

switch ($Command.ToLower()) {
    "run" {
        Start-Application -OverrideHost $ServerHost -OverridePort $ServerPort
    }
    "docker" {
        Start-Application-Docker
    }
    "test" {
        Run-Tests
    }
    "test-integration" {
        Run-IntegrationTests
    }
    "build" {
        Build-DockerImage
    }
    "logs" {
        Show-Logs
    }
    "status" {
        Show-Status
    }
    "cleanup" {
        Cleanup-All
    }
    default {
        Write-Host "❌ Unknown command: $Command"
        Write-Host ""
        Write-Host "Available commands:"
        Write-Host "  run              - Start application locally"
        Write-Host "  docker           - Start application in Docker"
        Write-Host "  test             - Run unit tests"
        Write-Host "  test-integration - Run integration tests"
        Write-Host "  build            - Build Docker image"
        Write-Host "  logs             - Show application logs"
        Write-Host "  status           - Show application status"
        Write-Host "  cleanup          - Clean up all resources"
        exit 1
    }
}