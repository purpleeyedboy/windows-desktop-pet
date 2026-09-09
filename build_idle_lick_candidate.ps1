[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-idle-lick"
$Work = Join-Path $Root "build-idle-lick"
$Metadata = Join-Path $Root "build-idle-lick-metadata"
$CandidateName = "桌面宠物_舔手逐帧动画恢复.exe"
$MaxCandidateBytes = 52428800

Push-Location $Root
try {
    $Foundation = Join-Path $Root "src\desktop_pet\eye_runtime.py"
    $GroomManifest = Join-Path $Root "assets\groom\v2.1\manifest.json"
    if (-not (Test-Path -LiteralPath $Foundation) -or -not (Test-Path -LiteralPath $GroomManifest)) {
        throw "Refusing to publish: runtime activity arbitration and reviewed grooming assets are required."
    }
    Remove-Item -LiteralPath $Dist,$Work,$Metadata -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $Metadata | Out-Null
    & $Python tools/import_groom_frames.py --output (Join-Path $Metadata "groom-frames")
    if ($LASTEXITCODE -ne 0 -or @(Get-ChildItem (Join-Path $Metadata "groom-frames") -Filter "*.png").Count -ne 12) { throw "Approved groom frame rebuild failed" }
    $SourceHead = if ($env:SOURCE_HEAD_SHA) { $env:SOURCE_HEAD_SHA.Trim() } else { (& git rev-parse HEAD).Trim() }
    $SourceShortHash = $SourceHead.Substring(0, [Math]::Min(7, $SourceHead.Length))
    $FoundationHash = (& git log -1 --format=%h -- src/desktop_pet/eye_runtime.py).Trim()
    $BuildDate = (Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ")
    @{
        version = "2.1-LICK"; date_utc = $BuildDate; git_short_hash = $SourceShortHash
        base_tag = "BASE-001"; enabled_feature = "approved-cat-left-paw-groom-frames"
        foundation_git_short_hash = $FoundationHash
        automated_tests = "automated_tests=false"
        acceptance_status = "acceptance_status=awaiting-user-windows-validation"
        debug_menu = "debug_menu=false"
        document_baseline = "V2.1_LICK_BUILD.md"
    } | ConvertTo-Json | Set-Content -LiteralPath "$Metadata\build-info.json" -Encoding UTF8

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
