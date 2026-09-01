[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$CleanupOnly
)

$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path $PSScriptRoot).Path
$VirtualEnvPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VirtualEnvPython) { $VirtualEnvPython } else { "python" }
$DistDirectory = Join-Path $RepositoryRoot "dist-eye-follow-candidate"
$WorkDirectory = Join-Path $RepositoryRoot "build-eye-follow-candidate"
$CandidateName = "桌面宠物-自然跟随候选版.exe"
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
    $CleanDistDirectory = Get-ValidatedChildPath "dist-eye-follow-candidate"
    $CleanWorkDirectory = Get-ValidatedChildPath "build-eye-follow-candidate"
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
    $basePrefix = & $Python -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Failed to resolve Python base prefix; exit code $LASTEXITCODE." }
    $basePrefix = $basePrefix.Trim()
    $env:TCL_LIBRARY = Join-Path $basePrefix 'tcl\tcl8.6'
    $env:TK_LIBRARY = Join-Path $basePrefix 'tcl\tk8.6'

    & $Python tools\validate_assets.py assets\keyframes --keyframe-root assets\keyframes --frame-count 6 --keyframe-layout direct --report qa\six-frame-alpha-validation.json
    if ($LASTEXITCODE -ne 0) { throw "Asset validation failed with exit code $LASTEXITCODE." }
    & $Python tools/validate_dialogue.py
    if ($LASTEXITCODE -ne 0) { throw "Dialogue validation failed with exit code $LASTEXITCODE." }

    if (-not $SkipTests) {
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Test suite failed with exit code $LASTEXITCODE." }
    }

    Clear-CandidateOutputs

    & $Python -m PyInstaller --noconfirm --distpath dist-eye-follow-candidate --workpath build-eye-follow-candidate desktop_pet_eye_follow.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

    $CandidateExes = @(Get-ChildItem -LiteralPath $DistDirectory -Filter "*.exe" -File)
    if ($CandidateExes.Count -ne 1 -or $CandidateExes[0].Name -ne $CandidateName) {
        throw "Expected exactly one candidate EXE named $CandidateName; found: $($CandidateExes.Name -join ', ')"
    }

    $CandidateExe = $CandidateExes[0]
    & $Python tools/verify_eye_follow_candidate_archive.py $CandidateExe.FullName
    if ($LASTEXITCODE -ne 0) { throw "Archive verification failed with exit code $LASTEXITCODE." }

    if ($CandidateExe.Length -gt $MaxCandidateBytes) {
        throw "Candidate EXE is $($CandidateExe.Length) bytes; limit is $MaxCandidateBytes bytes (50 MiB)."
    }

    $Hash = Get-FileHash -LiteralPath $CandidateExe.FullName -Algorithm SHA256
    Write-Host "Candidate EXE: $($CandidateExe.FullName)"
    Write-Host "Candidate size: $($CandidateExe.Length) bytes"
    Write-Host "SHA-256: $($Hash.Hash)"
}
finally {
    Pop-Location
}
