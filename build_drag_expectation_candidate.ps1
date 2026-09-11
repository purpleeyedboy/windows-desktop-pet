[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$CleanupOnly
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepositoryRoot = (Resolve-Path $PSScriptRoot).Path
$VirtualEnvPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VirtualEnvPython) { $VirtualEnvPython } else { "python" }
$DistDirectory = Join-Path $RepositoryRoot "dist-drag-expectation-candidate"
$WorkDirectory = Join-Path $RepositoryRoot "build-drag-expectation-candidate"
$MetadataDirectory = Join-Path $RepositoryRoot "build-drag-expectation-candidate-metadata"
$CandidateName = "桌面宠物_期待逐帧与公共基础接入.exe"
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
    $CleanDistDirectory = Get-ValidatedChildPath "dist-drag-expectation-candidate"
    $CleanWorkDirectory = Get-ValidatedChildPath "build-drag-expectation-candidate"
    $CleanMetadataDirectory = Get-ValidatedChildPath "build-drag-expectation-candidate-metadata"
    foreach ($directory in @($CleanDistDirectory, $CleanWorkDirectory, $CleanMetadataDirectory)) {
        Remove-CandidateOutput $directory
    }
}

if ($CleanupOnly) {
    Clear-CandidateOutputs
    return
}

Push-Location $RepositoryRoot
try {
    $basePrefix = & $Python -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Failed to resolve Python base prefix; exit code $LASTEXITCODE." }
    $basePrefix = $basePrefix.Trim()
    $env:TCL_LIBRARY = Join-Path $basePrefix 'tcl\tcl8.6'
    $env:TK_LIBRARY = Join-Path $basePrefix 'tcl\tk8.6'

    Clear-CandidateOutputs

    New-Item -ItemType Directory -Path $MetadataDirectory | Out-Null
    $GitShortHash = if ($env:SOURCE_HEAD_SHA) { $env:SOURCE_HEAD_SHA.Substring(0, 7) } else { (& git rev-parse --short HEAD).Trim() }
    if ($LASTEXITCODE -ne 0 -or [String]::IsNullOrWhiteSpace($GitShortHash)) {
        throw "Failed to resolve the candidate Git commit."
    }
    $BuildInfoPath = Join-Path $MetadataDirectory "DRAG_EXPECTATION_BUILD_INFO.json"
    $BuildInfo = Get-Content -LiteralPath (Join-Path $RepositoryRoot "DRAG_EXPECTATION_BUILD_INFO.json") -Raw | ConvertFrom-Json
    $BuildInfo.git_short_hash = $GitShortHash
    [IO.File]::WriteAllText(
        $BuildInfoPath,
        (($BuildInfo | ConvertTo-Json -Depth 8) + "`n"),
        (New-Object System.Text.UTF8Encoding($false))
    )
    $VersionInfoPath = Join-Path $MetadataDirectory "desktop_pet_drag_version_info.txt"
    $VersionInfo = (Get-Content -LiteralPath (Join-Path $RepositoryRoot "desktop_pet_drag_version_info.txt") -Raw).Replace(
        "build commit required",
        $GitShortHash
    )
    [IO.File]::WriteAllText(
        $VersionInfoPath,
        $VersionInfo,
        (New-Object System.Text.UTF8Encoding($false))
    )
    $env:DESKTOP_PET_BUILD_INFO = $BuildInfoPath
    $env:DESKTOP_PET_VERSION_INFO = $VersionInfoPath

    & $Python tools/build_expectation_assets.py
    if ($LASTEXITCODE -ne 0) { throw "Expectation asset reconstruction failed." }
    if (-not $SkipTests) {
        & $Python tools/verify_drag_runtime.py
        if ($LASTEXITCODE -ne 0) { throw "Shared expectation runtime verification failed." }
        & $Python tools/verify_graphic_animation_contract.py
        if ($LASTEXITCODE -ne 0) { throw "Graphic playback verification failed." }
    }
    & $Python -m PyInstaller --noconfirm --distpath dist-drag-expectation-candidate --workpath build-drag-expectation-candidate desktop_pet_drag_expectation.spec
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
    Write-Host "Candidate EXE: $($CandidateExe.FullName)"
    Write-Host "Candidate size: $($CandidateExe.Length) bytes"
    Write-Host "SHA-256: $($Hash.Hash)"
}
finally {
    Remove-CandidateOutput $MetadataDirectory
    Pop-Location
}
