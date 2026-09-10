[CmdletBinding()]
param(
    [switch]$CleanupOnly,
    [string]$FoundationCommit = $env:V21_FOUNDATION_COMMIT
)

$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path $PSScriptRoot).Path
$VirtualEnvPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VirtualEnvPython) { $VirtualEnvPython } else { "python" }
$DistDirectory = Join-Path $RepositoryRoot "dist-ears-candidate"
$WorkDirectory = Join-Path $RepositoryRoot "build-ears-candidate"
$CandidateName = "桌面宠物_耳朵防触摸系统_单次躲闪-20260910.exe"
$MaxCandidateBytes = 52428800

function Get-ValidatedChildPath([string]$ChildPath) {
    $rootWithSeparator = $RepositoryRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    $resolved = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot $ChildPath))
    if (-not $resolved.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the repository root: $resolved"
    }
    return $resolved
}

function Remove-CandidateOutput([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        return
    }
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        if ($item.PSIsContainer) {
            [IO.Directory]::Delete($Path, $false)
        }
        else {
            [IO.File]::Delete($Path)
        }
        return
    }
    if ($item.PSIsContainer) {
        foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) {
            Remove-CandidateOutput $child.FullName
        }
        [IO.Directory]::Delete($Path, $false)
    }
    else {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Clear-CandidateOutputs() {
    $CleanDistDirectory = Get-ValidatedChildPath "dist-ears-candidate"
    $CleanWorkDirectory = Get-ValidatedChildPath "build-ears-candidate"
    foreach ($directory in @($CleanDistDirectory, $CleanWorkDirectory)) {
        Remove-CandidateOutput $directory
    }
}

if ($CleanupOnly) {
    Clear-CandidateOutputs
    return
}

Push-Location $RepositoryRoot
try {
    $env:PYTHONPATH = Join-Path $RepositoryRoot "src"
    if ([string]::IsNullOrWhiteSpace($FoundationCommit)) {
        $FoundationCommit = "4eda8964ccee8ccd0bd0e2bddb9670618924f90e"
    }
    $RuntimeApi = Join-Path $RepositoryRoot "docs\v21-runtime-api.md"
    if (-not (Test-Path -LiteralPath $RuntimeApi -PathType Leaf)) {
        throw "PR5 docs/v21-runtime-api.md is unavailable; refusing to package without the real API."
    }
    & $Python tools/verify_ears_foundation_recovery.py
    if ($LASTEXITCODE -ne 0) { throw "Shared persistence recovery verification failed." }
    & $Python tools/verify_graphic_animation_contract.py
    if ($LASTEXITCODE -ne 0) { throw "Shared graphic playback verification failed." }
    & $Python tools/verify_ears_runtime_wiring.py
    if ($LASTEXITCODE -ne 0) { throw "Ear raster/runtime verification failed; refusing to package." }
    $basePrefix = & $Python -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Failed to resolve Python base prefix; exit code $LASTEXITCODE." }
    $basePrefix = $basePrefix.Trim()
    $env:TCL_LIBRARY = Join-Path $basePrefix 'tcl\tcl8.6'
    $env:TK_LIBRARY = Join-Path $basePrefix 'tcl\tk8.6'

    Clear-CandidateOutputs
    New-Item -ItemType Directory -Path $WorkDirectory | Out-Null
    $BuildDate = Get-Date -Format 'yyyy-MM-dd'
    $SourceHead = if ($env:SOURCE_HEAD_SHA) { $env:SOURCE_HEAD_SHA } else { (git rev-parse HEAD).Trim() }
    if ($SourceHead -notmatch '^[0-9a-fA-F]{40}$') { throw "Invalid source head SHA." }
    $GitShortHash = $SourceHead.Substring(0, 7)
    $BuildMetadata = @{
        product_version = "2.1.1-test"
        build_date = $BuildDate
        git_short_hash = $GitShortHash
        source_head_sha = $SourceHead
        baseline = "BASE-001"
        foundation_commit = $FoundationCommit
        enabled_features = @("common-foundation", "ears")
        channel = "未自动测试；等待用户 Windows 实机验收的候选版"
        documentation_baseline = "V2.1-EARS"
    } | ConvertTo-Json -Depth 3
    $BuildMetadataObject = $BuildMetadata | ConvertFrom-Json
    $BuildMetadataObject | Add-Member -NotePropertyName test_build -NotePropertyValue $true
    $BuildMetadataObject | Add-Member -NotePropertyName debug_enabled -NotePropertyValue $true
    $BuildMetadataObject | Add-Member -NotePropertyName debug_menu_enabled -NotePropertyValue $true
    $BuildMetadata = $BuildMetadataObject | ConvertTo-Json -Depth 3
    $MetadataPath = Join-Path $WorkDirectory "build_identity.json"
    [IO.File]::WriteAllText($MetadataPath, $BuildMetadata, (New-Object Text.UTF8Encoding($false)))
    $env:DESKTOP_PET_BUILD_METADATA = $MetadataPath

    & $Python -m PyInstaller --noconfirm --distpath dist-ears-candidate --workpath build-ears-candidate desktop_pet_ears.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

    $CandidateExes = @(Get-ChildItem -LiteralPath $DistDirectory -Filter "*.exe" -File)
    if ($CandidateExes.Count -ne 1 -or $CandidateExes[0].Name -ne $CandidateName) {
        throw "Expected exactly one candidate EXE named $CandidateName; found: $($CandidateExes.Name -join ', ')"
    }

    $CandidateExe = $CandidateExes[0]

    if ($CandidateExe.Length -gt $MaxCandidateBytes) {
        throw "Candidate EXE is $($CandidateExe.Length) bytes; limit is $MaxCandidateBytes bytes (50 MiB)."
    }

    $Hash = Get-FileHash -LiteralPath $CandidateExe.FullName -Algorithm SHA256
    Write-Warning "This candidate was not automatically tested; Windows desktop acceptance is pending."
    Write-Host "Candidate EXE: $($CandidateExe.FullName)"
    Write-Host "Candidate size: $($CandidateExe.Length) bytes"
    Write-Host "SHA-256: $($Hash.Hash)"
}
finally {
    Pop-Location
}
