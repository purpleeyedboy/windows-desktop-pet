[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }
$dist = Join-Path $root "dist-v21-core"
$work = Join-Path $root "build-v21-core"
$name = "桌面宠物_V2.1公共基础架构.exe"
Push-Location $root
try {
    if (-not $SkipTests) { & $python -m pytest -q; if ($LASTEXITCODE -ne 0) { throw "Tests failed" } }
    Remove-Item -LiteralPath $dist,$work -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $work | Out-Null
    $shortHash = (& git rev-parse --short HEAD).Trim()
    $buildDate = (Get-Date -AsUTC -Format "yyyy-MM-dd")
    $description = "V2.1-CORE; common-foundation; Test build: false; Debug menu: false; BASE-001; Build $buildDate; Git $shortHash"
    $versionText = @"
VSVersionInfo(ffi=FixedFileInfo(filevers=(2,1,0,0), prodvers=(2,1,0,0), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), kids=[StringFileInfo([StringTable('080404b0', [StringStruct('CompanyName', 'Desktop Pet'), StringStruct('FileDescription', '$description'), StringStruct('FileVersion', '2.1.0'), StringStruct('InternalName', 'V2.1-CORE'), StringStruct('OriginalFilename', '$name'), StringStruct('ProductName', 'Desktop Pet common-foundation'), StringStruct('ProductVersion', '2.1.0')])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])])
"@
    [IO.File]::WriteAllText((Join-Path $work "version_info.txt"), $versionText, [Text.UTF8Encoding]::new($false))
    & $python -m PyInstaller --noconfirm --distpath $dist --workpath $work desktop_pet_v21_core.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    $exes = @(Get-ChildItem -LiteralPath $dist -Filter "*.exe" -File)
    if ($exes.Count -ne 1 -or $exes[0].Name -ne $name) { throw "Expected exactly one EXE named $name" }
    $hash = Get-FileHash -LiteralPath $exes[0].FullName -Algorithm SHA256
    Write-Host "Candidate EXE: $($exes[0].FullName)"
    Write-Host "Candidate size: $($exes[0].Length) bytes"
    Write-Host "SHA-256: $($hash.Hash)"
} finally { Pop-Location }
