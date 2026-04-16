# smoke-test.ps1 - verify all services are healthy after docker compose up -d
# Usage: .\scripts\smoke-test.ps1

$ErrorActionPreference = "SilentlyContinue"

$Pass = 0
$Fail = 0

function Test-Service {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Expect
    )
    
    try {
        $Result = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
        $ResultStr = $Result | Out-String
        if ($ResultStr -match $Expect) {
            Write-ColorOutput Green "  [OK] $Name"
            $script:Pass++
        } else {
            Write-ColorOutput Red "  [FAIL] $Name  ($Url)"
            $script:Fail++
        }
    } catch {
        Write-ColorOutput Red "  [FAIL] $Name  ($Url)"
        $script:Fail++
    }
}

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args[0]
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Cyan "Super-Agent - Smoke Test"
Write-Output "-------------------------"

Test-Service "Ollama" "http://localhost:11434/api/tags" "models"
Test-Service "Orchestrator" "http://localhost:8000/health" "ok"
Test-Service "Qdrant" "http://localhost:6333/readyz" "ok"
Test-Service "Open-WebUI" "http://localhost:3000" "html"
Test-Service "n8n" "http://localhost:5678" "n8n"

Write-Output ""
Write-Output "Orchestrator status:"
try {
    $Status = Invoke-RestMethod -Uri "http://localhost:8000/status" -Method Get -TimeoutSec 5
    $Status.PSObject.Properties | ForEach-Object {
        Write-Output "  $($_.Name): $($_.Value)"
    }
} catch {
    Write-Output "  (orchestrator not yet ready)"
}

Write-Output ""
if ($Fail -eq 0) {
    Write-ColorOutput Green "All checks passed ($Pass/$($Pass + $Fail))"
    Write-Output ""
    Write-Output "  Open-WebUI:   http://localhost:3000"
    Write-Output "  Orchestrator: http://localhost:8000/docs"
    Write-Output "  n8n:          http://localhost:5678  [admin / changeme]"
} else {
    Write-ColorOutput Yellow "$Fail service(s) not ready yet. Wait 30s and retry, or:"
    Write-Output "  docker compose ps"
    Write-Output "  docker compose logs --tail=30 <service>"
}
