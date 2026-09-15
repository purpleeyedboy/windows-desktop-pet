[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-idle-lick"
$Work = Join-Path $Root "build-idle-lick"
$Metadata = Join-Path $Root "build-idle-lick-metadata"
$CandidateName = "桌面宠物_双侧舔手与中断恢复.exe"
$MaxCandidateBytes = 52428800

Push-Location $Root
try {
    $Foundation = Join-Path $Root "src\desktop_pet\foundation\services.py"
    $GroomManifest = Join-Path $Root "assets\groom\v2.1\manifest.json"
    $RightManifest = Join-Path $Root "assets\groom\v2.1\manifest-right.json"
    if (-not (Test-Path -LiteralPath $Foundation) -or -not (Test-Path -LiteralPath $GroomManifest) -or -not (Test-Path -LiteralPath $RightManifest)) {
        throw "Refusing to publish: runtime activity arbitration and reviewed grooming assets are required."
    }
    & $Python tools/verify_graphic_animation_contract.py
    if ($LASTEXITCODE -ne 0) { throw "Shared graphic runtime verification failed" }
    & $Python tools/verify_groom_side_selection.py
    if ($LASTEXITCODE -ne 0) { throw "Authored grooming side selection verification failed" }
    & $Python tools/verify_groom_foundation_runtime.py
    if ($LASTEXITCODE -ne 0) { throw "Groom activity verification failed" }
    & $Python tools/verify_groom_foundation_recovery.py
    if ($LASTEXITCODE -ne 0) { throw "Shared state recovery verification failed" }
    Remove-Item -LiteralPath $Dist,$Work,$Metadata -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $Metadata | Out-Null
    & $Python tools/import_groom_frames.py --output (Join-Path $Metadata "groom-frames")
    if ($LASTEXITCODE -ne 0 -or @(Get-ChildItem (Join-Path $Metadata "groom-frames") -Filter "*.png").Count -ne 12) { throw "Approved groom frame rebuild failed" }
    & $Python tools/import_groom_frames.py --manifest $RightManifest --output (Join-Path $Metadata "groom-frames-right")
    if ($LASTEXITCODE -ne 0 -or @(Get-ChildItem (Join-Path $Metadata "groom-frames-right") -Filter "*.png").Count -ne 12) { throw "Right groom frame rebuild failed" }
    $SourceHead = if ($env:SOURCE_HEAD_SHA) { $env:SOURCE_HEAD_SHA.Trim() } else { (& git rev-parse HEAD).Trim() }
    $SourceShortHash = $SourceHead.Substring(0, [Math]::Min(7, $SourceHead.Length))
    $FoundationHash = (Get-Content -LiteralPath "docs/groom-foundation-source.json" -Raw | ConvertFrom-Json).source_commit
    $BuildDate = (Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ")
    @{
        version = "2.1-LICK"; date_utc = $BuildDate; git_short_hash = $SourceShortHash; source_head_sha = $SourceHead
        base_tag = "BASE-001"; enabled_feature = "approved-cat-bilateral-groom-frames"
        foundation_git_short_hash = $FoundationHash
        groom_sides = @("left", "right")
        groom_paw_colors = @{ left = "white"; right = "orange" }
        automated_tests = "focused-runtime-gates-passed"
        acceptance_status = "acceptance_status=awaiting-user-windows-validation"
        test_build = $true
        debug_menu = $true
        document_baseline = "V2.1_LICK_BUILD.md"
    } | ConvertTo-Json | Set-Content -LiteralPath "$Metadata\build-info.json" -Encoding UTF8

    @{
        product_version = "2.1-LICK"; build_date = (Get-Date -AsUTC -Format "yyyy-MM-dd")
        git_short_hash = $SourceShortHash; source_head_sha = $SourceHead; foundation_commit = $FoundationHash
        enabled_features = @("common-foundation", "approved-cat-bilateral-groom-frames")
        groom_sides = @("left", "right")
        test_build = $true; debug_enabled = $true; debug_menu_enabled = $true
    } | ConvertTo-Json | Set-Content -LiteralPath "$Metadata\build_identity.json" -Encoding UTF8
    & $Python -m PyInstaller --noconfirm --distpath $Dist --workpath $Work desktop_pet_idle_lick.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $CandidateExes = @(Get-ChildItem -LiteralPath $Dist -Filter "*.exe" -File)
    if ($CandidateExes.Count -ne 1 -or $CandidateExes[0].Name -ne $CandidateName) {
        throw "Expected exactly one EXE named $CandidateName; found $($CandidateExes.Name -join ', ')"
    }
    if ($CandidateExes[0].Length -gt $MaxCandidateBytes) { throw "Candidate exceeds MaxCandidateBytes=$MaxCandidateBytes" }
    $Hash = Get-FileHash -LiteralPath $CandidateExes[0].FullName -Algorithm SHA256
    Write-Host "Candidate size: $($CandidateExes[0].Length) bytes"
    Write-Host "SHA-256: $($Hash.Hash)"
}
finally { Pop-Location }
