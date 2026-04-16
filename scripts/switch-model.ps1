# switch-model.ps1 - toggle between GLM-5.1:cloud and local RTX 4080 inference
#
# Usage:
#   .\scripts\switch-model.ps1                      -> show current config
#   .\scripts\switch-model.ps1 cloud                -> GLM-5.1:cloud (default)
#   .\scripts\switch-model.ps1 local                -> glm-4.7-flash (RTX 4080)
#   .\scripts\switch-model.ps1 local qwen3.5:9b     -> local with override model

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectDir ".env"

$Mode = if ($args.Count -gt 0) { $args[0] } else { "" }
$OverrideModel = if ($args.Count -gt 1) { $args[1] } else { "" }

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args[0]
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

# No argument: show status
if ([string]::IsNullOrEmpty($Mode)) {
    Write-ColorOutput Cyan "Super-Agent - Current Config"
    Write-Output "-------------------------"
    if (Test-Path $EnvFile) {
        Select-String -Path $EnvFile -Pattern "^(MODEL_MODE|ACTIVE_MODEL|LOCAL_MODEL)=" | ForEach-Object {
            Write-Output "  $($_.Line.Trim())"
        }
    } else {
        Write-ColorOutput Yellow "  .env not found - run: Copy .env.example .env"
    }
    Write-Output ""
    Write-Output "Usage: .\scripts\switch-model.ps1 cloud|local [model-override]"
    exit 0
}

Write-ColorOutput Cyan "Super-Agent - Model Switch"
Write-Output "-------------------------"

# Cloud mode
if ($Mode -eq "cloud") {
    $ActiveModel = "glm-5.1:cloud"
    Write-Output "  Mode:  cloud"
    Write-ColorOutput Green "  Model: $ActiveModel"
    Write-ColorOutput Green "  VRAM:  0 GB (proxied by Ollama -> Z.ai)"

# Local mode
} elseif ($Mode -eq "local") {
    if ([string]::IsNullOrEmpty($OverrideModel)) {
        if (Test-Path $EnvFile) {
            $Match = Select-String -Path $EnvFile -Pattern "^LOCAL_MODEL="
            if ($Match) {
                $Value = ($Match.Line -split "=", 2)[1]
                $LocalModel = $Value.Trim().Trim('"')
            }
            if ([string]::IsNullOrEmpty($LocalModel)) {
                $LocalModel = "glm-4.7-flash"
            }
        } else {
            $LocalModel = "glm-4.7-flash"
        }
    } else {
        $LocalModel = $OverrideModel
    }
    $ActiveModel = $LocalModel
    Write-Output "  Mode:  local (RTX 4080 12 GB)"
    Write-ColorOutput Yellow "  Model: $LocalModel"

    # VRAM guidance
    switch ($LocalModel) {
        "glm-4.7-flash" {
            Write-ColorOutput Green "  VRAM:  ~8 GB  (MoE 30B / 3B active) [OK] comfortable"
        }
        "qwen3-coder:14b" {
            Write-ColorOutput Green "  VRAM:  ~9 GB  (14B dense)           [OK] fits"
        }
        "qwen3.5:9b" {
            Write-ColorOutput Green "  VRAM:  ~6 GB  (9B dense)            [OK] headroom"
        }
        "qwen3.5:27b" {
            Write-ColorOutput Red "  VRAM:  ~17 GB (27B dense)           [FAIL] exceeds 12 GB"
            exit 1
        }
        { $_ -match "glm-5.1" } {
            Write-ColorOutput Red "  VRAM:  ~400+ GB (754B MoE)        [FAIL] not runnable locally"
            exit 1
        }
        default {
            Write-ColorOutput Yellow "  VRAM:  unknown - check ollama.com/library/$LocalModel"
        }
    }

    # Pull model if not already present
    Write-Output ""
    Write-Output -NoNewline "  Checking if $LocalModel is in Ollama... "
    $ListResult = docker compose -f "$ProjectDir\docker-compose.yml" exec -T ollama ollama list 2>$null
    if ($ListResult -match $LocalModel) {
        Write-ColorOutput Green "already present"
    } else {
        Write-ColorOutput Yellow "pulling..."
        docker compose -f "$ProjectDir\docker-compose.yml" exec ollama ollama pull $LocalModel
    }

    # Also pull embedding model if missing (used by Mem0)
    Write-Output -NoNewline "  Checking nomic-embed-text... "
    if ($ListResult -match "nomic-embed-text") {
        Write-ColorOutput Green "already present"
    } else {
        Write-ColorOutput Yellow "pulling..."
        docker compose -f "$ProjectDir\docker-compose.yml" exec ollama ollama pull nomic-embed-text
    }

} else {
    Write-ColorOutput Red "Unknown mode $Mode. Use cloud or local."
    exit 1
}

# Update .env
if (Test-Path $EnvFile) {
    $Content = Get-Content $EnvFile
    $NewContent = @()
    $HasActiveModel = $false
    $HasLocalModel = $false
    
    foreach ($Line in $Content) {
        if ($Line -match "^MODEL_MODE=") {
            $NewContent += "MODEL_MODE=$Mode"
        } elseif ($Line -match "^ACTIVE_MODEL=") {
            $NewContent += "ACTIVE_MODEL=$ActiveModel"
            $HasActiveModel = $true
        } elseif ($Line -match "^LOCAL_MODEL=" -and $Mode -eq "local") {
            $NewContent += "LOCAL_MODEL=$LocalModel"
            $HasLocalModel = $true
        } else {
            $NewContent += $Line
        }
    }
    
    if (-not $HasActiveModel) {
        $NewContent += "ACTIVE_MODEL=$ActiveModel"
    }
    if ($Mode -eq "local" -and -not $HasLocalModel) {
        $NewContent += "LOCAL_MODEL=$LocalModel"
    }
    
    $NewContent | Set-Content $EnvFile
    Write-Output ""
    Write-ColorOutput Green "  [OK] .env updated  MODEL_MODE=$Mode  ACTIVE_MODEL=$ActiveModel"
} else {
    Write-Output ""
    Write-ColorOutput Yellow "  Warning: .env not found. Copy .env.example to .env first."
}

# Also update opencode-config.json model field
$OpenCodeCfg = Join-Path $ProjectDir "config\opencode-config.json"
if (Test-Path $OpenCodeCfg) {
    $Cfg = Get-Content $OpenCodeCfg | ConvertFrom-Json
    $Cfg.model = $ActiveModel
    $Cfg | ConvertTo-Json -Depth 10 | Set-Content $OpenCodeCfg
    Write-ColorOutput Green "  [OK] opencode-config.json updated"
}

# Restart affected services
Write-Output ""
Write-Output "  Restarting services..."
docker compose -f "$ProjectDir\docker-compose.yml" up -d --no-deps opencode openclaw orchestrator

Write-Output ""
Write-ColorOutput Green "Done."
Write-Output "  Active model: $ActiveModel  (mode: $Mode)"
Write-Output ""
Write-Output "  Services:"
Write-Output "    Open-WebUI:   http://localhost:3000"
Write-Output "    Orchestrator: http://localhost:8000/docs"
Write-Output "    n8n:          http://localhost:5678"
Write-Output "    Ollama API:   http://localhost:11434/api/tags"
