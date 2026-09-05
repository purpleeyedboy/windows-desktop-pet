[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-hunger"
$Work = Join-Path $Root "build-hunger"
$Expected = "桌面宠物_饥饿值与饥饿动画.exe"
$MaxBytes = 52428800
Push-Location $Root
try {
  $Metadata = [ordered]@{
    version = "2.1.1"
    date = "2026-09-05"
    git_short_hash = (& git rev-parse --short=12 HEAD).Trim()
    baseline_tag = "BASE-001"
    enabled_features = @("baseline", "integer_hunger", "utc_recovery", "hunger_animation", "tears", "atomic_persistence")
    test_build = $true
    debug_menu = $true
    documentation_baseline = "V2.1"
    automated_tests = $false
    windows_acceptance = "pending_user_validation"
  }
  $Metadata | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath build_metadata.json -Encoding UTF8
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
  Write-Warning "UNTESTED candidate: pending user Windows validation"
  Write-Host "Size: $($Exes[0].Length) bytes"
  Write-Host "SHA-256: $($Hash.Hash)"
} finally { Pop-Location }
