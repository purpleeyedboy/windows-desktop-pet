[CmdletBinding()]
param(
    [switch]$CleanupOnly
)

$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path $PSScriptRoot).Path
$VirtualEnvPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VirtualEnvPython) { $VirtualEnvPython } else { "python" }
$DistDirectory = Join-Path $RepositoryRoot "dist-ears-candidate"
$WorkDirectory = Join-Path $RepositoryRoot "build-ears-candidate"
$CandidateName = "桌面宠物_双耳点击反馈.exe"
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
    $basePrefix = & $Python -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Failed to resolve Python base prefix; exit code $LASTEXITCODE." }
    $basePrefix = $basePrefix.Trim()
    $env:TCL_LIBRARY = Join-Path $basePrefix 'tcl\tcl8.6'
    $env:TK_LIBRARY = Join-Path $basePrefix 'tcl\tk8.6'

    Clear-CandidateOutputs
    New-Item -ItemType Directory -Path $WorkDirectory | Out-Null
    $BuildDate = Get-Date -Format 'yyyy-MM-dd'
    $GitShortHash = (git rev-parse --short HEAD).Trim()
    $BuildMetadata = @{
        product_version = "2.1.1-test"
        build_date = $BuildDate
        git_short_hash = $GitShortHash
        baseline = "BASE-001"
        enabled_features = @("既有基线", "双耳点击反馈")
        channel = "未自动测试；等待用户 Windows 实机验收的候选版"
        documentation_baseline = "V2.1-EARS"
    } | ConvertTo-Json -Depth 3
    $MetadataPath = Join-Path $WorkDirectory "build-metadata.json"
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
