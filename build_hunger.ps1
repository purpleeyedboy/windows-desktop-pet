[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-hunger"
$Work = Join-Path $Root "build-hunger"
$Expected = "桌面宠物_修复饥饿衰减与张嘴流泪.exe"
$MaxBytes = 52428800
Push-Location $Root
try {
  $Metadata = [ordered]@{
    version = "2.1.1"
    date = "2026-09-06"
    git_short_hash = (& git rev-parse --short=12 HEAD).Trim()
    baseline_tag = "BASE-001"
    baseline_commit = "c3b218df9dd0cfc84d96231701e771f0382388e1"
    foundation_commit = "PENDING_PR5"
    enabled_features = @("baseline", "hunger_0_100000", "real_utc_decay_120m", "mouth_tongue", "pose_anchored_tears", "unified_state_adapter")
    test_build = $true
    debug_menu = $true
    documentation_baseline = "V2.1"
    automated_tests = $false
    windows_acceptance = "blocked_pending_pr5_then_user_validation"
  }
  $Metadata | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath build_metadata.json -Encoding UTF8
  if ($Metadata.foundation_commit -eq "PENDING_PR5" -or -not (Test-Path -LiteralPath (Join-Path $Root "src\desktop_pet\foundation\services.py"))) {
    throw "BLOCKED: merge the approved PR5 foundation commit and record the same hash before packaging"
  }
  foreach ($path in @($Dist, $Work)) {
    if (Test-Path $path) {
      $full = [IO.Path]::GetFullPath($path)
      if (-not $full.StartsWith($Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe cleanup path: $full" }
      Remove-Item -LiteralPath $full -Recurse -Force
    }
  }
  & $Python -m PyInstaller --noconfirm --distpath dist-hunger --workpath build-hunger desktop_pet_hunger.spec
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
  $Exes = @(Get-ChildItem -LiteralPath $Dist -Filter "*.exe" -File)
  if ($Exes.Count -ne 1 -or $Exes[0].Name -ne $Expected) { throw "Expected exactly one EXE named $Expected; found $($Exes.Name -join ', ')" }
  if ($Exes[0].Length -gt $MaxBytes) { throw "Candidate exceeds 52428800 bytes" }
  $Hash = Get-FileHash -LiteralPath $Exes[0].FullName -Algorithm SHA256
  Write-Warning "BLOCKED repair candidate: pending PR5 foundation integration, then user Windows validation"
  Write-Host "Size: $($Exes[0].Length) bytes"
  Write-Host "SHA-256: $($Hash.Hash)"
} finally { Pop-Location }
