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
$CandidateName = "桌面宠物_文件拖动期待反馈.exe"
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

    Clear-CandidateOutputs

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
    Pop-Location
}
