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

Invoke-Compose stop
Write-Host "FinAlly stopped. Local data in db/ is preserved."
