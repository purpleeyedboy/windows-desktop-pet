[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-hunger"
$Work = Join-Path $Root "build-hunger"
$Expected = "桌面宠物_饥饿真实帧与公共基础接入.exe"
$MaxBytes = 52428800
Push-Location $Root
try {
  & $Python tools/verify_hunger_foundation.py
  if ($LASTEXITCODE -ne 0) { throw "Verified foundation source gate failed" }
  & $Python tools/verify_hunger_shared_state.py
  if ($LASTEXITCODE -ne 0) { throw "Shared hunger state integration gate failed" }
  & $Python tools/verify_graphic_animation_contract.py
  if ($LASTEXITCODE -ne 0) { throw "Coordinated graphic playback gate failed" }
  & $Python scripts/build_hunger_assets.py
  if ($LASTEXITCODE -ne 0) { throw "Hunger frame reconstruction failed" }
  & $Python tools/verify_hunger_graphic_assets.py
  if ($LASTEXITCODE -ne 0) { throw "Hunger graphic loading gate failed" }
  $Provenance = Get-Content -LiteralPath docs/hunger-foundation-provenance.json -Raw | ConvertFrom-Json
  $Metadata = [ordered]@{
    version = "2.1.2"
    date = (Get-Date -AsUTC -Format "yyyy-MM-dd")
    git_short_hash = (& git rev-parse --short=12 HEAD).Trim()
    baseline_tag = "BASE-001"
    baseline_commit = "c3b218df9dd0cfc84d96231701e771f0382388e1"
    foundation_commit = $Provenance.foundation_commit
    graphic_playback_fix_commit = $Provenance.graphic_playback_fix_commit
    activity_recovery_fix_commit = $Provenance.activity_recovery_fix_commit
    enabled_features = @("baseline", "hunger_0_100000", "real_utc_decay_120m", "real_graphic_hunger", "unified_state_adapter")
    test_build = $true
    debug_menu = $true
    documentation_baseline = "V2.1"
    automated_tests = $false
    focused_integration_checks = $true
    windows_acceptance = "pending_user_validation"
  }
  $Metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath build_metadata.json -Encoding UTF8
  $Identity = [ordered]@{
    product_version = $Metadata.version
    build_date = $Metadata.date
    git_short_hash = $Metadata.git_short_hash
    foundation_commit = $Metadata.foundation_commit
    activity_recovery_fix_commit = $Metadata.activity_recovery_fix_commit
    enabled_features = $Metadata.enabled_features
    test_build = $true
    debug_enabled = $true
    debug_menu_enabled = $true
  }
  [IO.File]::WriteAllText((Join-Path $Root "build_identity.json"), ($Identity | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
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
  Write-Warning "Candidate: pending user Windows visual acceptance"
  Write-Host "Size: $($Exes[0].Length) bytes"
  Write-Host "SHA-256: $($Hash.Hash)"
} finally { Pop-Location }
