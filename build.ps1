param(
    [switch]$TkEnvironmentReady
)

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "缺少项目虚拟环境：$python"
}

Set-Location -LiteralPath $projectRoot
$basePrefix = & $python -c "import sys; print(sys.base_prefix)"
$tclLibrary = Join-Path $basePrefix 'tcl\tcl8.6'
$tkLibrary = Join-Path $basePrefix 'tcl\tk8.6'

if (-not $TkEnvironmentReady) {
    $env:TCL_LIBRARY = $tclLibrary
    $env:TK_LIBRARY = $tkLibrary
    $powerShell = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    & $powerShell -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -TkEnvironmentReady
    if ($LASTEXITCODE -ne 0) {
        throw "Build subprocess failed with exit code $LASTEXITCODE"
    }
    return
}

$env:TCL_LIBRARY = $tclLibrary
$env:TK_LIBRARY = $tkLibrary

& $python tools\validate_assets.py assets\pet
if ($LASTEXITCODE -ne 0) { throw '动作素材验证失败' }

& $python -m pytest -q --ignore=tests\test_window.py
if ($LASTEXITCODE -ne 0) { throw '自动测试失败' }

foreach ($relativeTarget in @('build', 'dist')) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $relativeTarget))
    $insideProject = $target.StartsWith(
        $projectRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
    if (-not $insideProject) {
        throw "拒绝清理项目外路径：$target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

& $python -m PyInstaller --noconfirm desktop_pet.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败' }

$exeFiles = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'dist') -Filter '*.exe' -File)
if ($exeFiles.Count -ne 1) {
    throw "Expected exactly one EXE in dist, found $($exeFiles.Count)"
}

$exeFiles[0] | Select-Object FullName, Length, LastWriteTime
