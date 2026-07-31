$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)

    docker compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker compose @Args
        return
    }

    $DockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($DockerCompose) {
        & docker-compose @Args
        return
    }

    throw "Docker Compose is required. Install Docker Desktop or the docker compose plugin."
}

New-Item -ItemType Directory -Force -Path "db" | Out-Null

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example."
}

$FinallyPort = if ($env:FINALLY_PORT) { $env:FINALLY_PORT } else { "8000" }
$FinallyUrl = "http://localhost:$FinallyPort"

Invoke-Compose up --build -d

Write-Host "Waiting for FinAlly at $FinallyUrl ..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-RestMethod -Uri "$FinallyUrl/api/health" -TimeoutSec 3 | Out-Null
        Write-Host "FinAlly is running at $FinallyUrl"
        Start-Process $FinallyUrl
        exit 0
    } catch {
        Start-Sleep -Seconds 1
    }
}

Write-Error "FinAlly container started, but /api/health did not respond within 30 seconds."
Invoke-Compose ps
exit 1
