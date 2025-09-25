# ----------------------------
# PyGem Run Script
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
    Write-Host "Building Docker image: $imageName..."
    docker build -t $imageName .
    Write-Host "✅ Docker image built successfully"
}

# ----------------------------
# 1️⃣ Start Docker Container
# ----------------------------
function Start-Container {
    $imageName = "pygem-modular-monolith:latest"
    $containerName = "pygem-app"

    # Stop existing container if running
    if (docker ps -q -f "name=$containerName") {
        Write-Host "Stopping existing container $containerName..."
        docker stop $containerName | Out-Null
        docker rm $containerName | Out-Null
    }

    # Run new container
    Write-Host "Starting container $containerName from image $imageName..."
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
    Write-Host "Tailing logs for $containerName..."
    docker logs -f $containerName
}

# ----------------------------
# 3️⃣ Menu / Execution
# ----------------------------
switch ($Step.ToLower()) {
    "build" { Build-Image }
    "run"   { Build-Image; Start-Container; Follow-Logs }
    default { Write-Host "Unknown step. Valid options: build, run" }
}
