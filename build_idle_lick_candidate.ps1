[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }
$Dist = Join-Path $Root "dist-idle-lick"
$Work = Join-Path $Root "build-idle-lick"
$Metadata = Join-Path $Root "build-idle-lick-metadata"
$CandidateName = "桌面宠物_空闲随机舔手.exe"
$MaxCandidateBytes = 52428800

Push-Location $Root
try {
    if (-not $SkipTests) {
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed: $LASTEXITCODE" }
    }
    Remove-Item -LiteralPath $Dist,$Work,$Metadata -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $Metadata | Out-Null
    $ShortHash = (& git rev-parse --short HEAD).Trim()
    $BuildDate = (Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ")
    @{
        version = "2.1-LICK"; date_utc = $BuildDate; git_short_hash = $ShortHash
        base_tag = "BASE-001"; enabled_feature = "idle-random-left-right-hand-lick"
        test_build = "test_build=true"; debug_menu = "debug_menu=false"
        document_baseline = "V2.1_LICK_BUILD.md"
    } | ConvertTo-Json | Set-Content -LiteralPath "$Metadata\build-info.json" -Encoding UTF8

    & $Python -m PyInstaller --noconfirm --distpath $Dist --workpath $Work desktop_pet_idle_lick.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $CandidateExes = @(Get-ChildItem -LiteralPath $Dist -Filter "*.exe" -File)
    if ($CandidateExes.Count -ne 1 -or $CandidateExes[0].Name -ne $CandidateName) {
        throw "Expected exactly one EXE named $CandidateName; found $($CandidateExes.Name -join ', ')"
    }
    & $Python tools\verify_eye_follow_candidate_archive.py $CandidateExes[0].FullName
    if ($LASTEXITCODE -ne 0) { throw "Archive verification failed: $LASTEXITCODE" }
    if ($CandidateExes[0].Length -gt $MaxCandidateBytes) { throw "Candidate exceeds MaxCandidateBytes=$MaxCandidateBytes" }
    $Hash = Get-FileHash -LiteralPath $CandidateExes[0].FullName -Algorithm SHA256
    Write-Host "Candidate size: $($CandidateExes[0].Length) bytes"
    Write-Host "SHA-256: $($Hash.Hash)"
}
finally { Pop-Location }
