# ----------------------------
# PyGem Force-Rebuild Script
# ----------------------------
param (
    [string]$Step = "run"
)

$ErrorActionPreference = "Stop"

# ----------------------------
# 0️⃣ Build Docker Image
# ----------------------------
function Build-Image {
    $imageName = "pygem-modular-monolith:latest"
    Write-Host "🔨 Building Docker image: $imageName..."
    docker build --no-cache -t $imageName .
    Write-Host "✅ Docker image built successfully"
}

# ----------------------------
# 1️⃣ Start Docker Container (Force Rebuild)
# ----------------------------
function Start-Container {
    $imageName = "pygem-modular-monolith:latest"
    $containerName = "pygem-app"

    # Stop and remove existing container if it exists (running or stopped)
    $existing = docker ps -aq -f "name=$containerName"
    if ($existing) {
        Write-Host "🛑 Stopping and removing existing container $containerName..."
        docker stop $containerName -t 5 | Out-Null -ErrorAction SilentlyContinue
        docker rm $containerName | Out-Null -ErrorAction SilentlyContinue
    }

    # Run new container
    Write-Host "🚀 Starting container $containerName from image $imageName..."
    docker run -d `
        --name $containerName `
        -p 8000:8000 `
        --env-file .env `
        $imageName

    Write-Host "✅ Container started, accessible at http://127.0.0.1:8000"
}

# ----------------------------
# 2️⃣ Follow Logs
# ----------------------------
function Follow-Logs {
    $containerName = "pygem-app"
    Write-Host "📜 Tailing logs for $containerName..."
    docker logs -f $containerName
}

# ----------------------------
# 3️⃣ Menu / Execution
# ----------------------------
switch ($Step.ToLower()) {
    "build" { Build-Image }
    "run"   { Build-Image; Start-Container; Follow-Logs }
    default { Write-Host "❌ Unknown step. Valid options: build, run" }
}
