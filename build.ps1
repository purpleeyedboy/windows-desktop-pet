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

& $python tools\validate_assets.py assets\keyframes --keyframe-root assets\keyframes --frame-count 6 --keyframe-layout direct --report qa\six-frame-alpha-validation.json
if ($LASTEXITCODE -ne 0) { throw '动作素材验证失败' }

& $python tools\validate_dialogue.py
if ($LASTEXITCODE -ne 0) { throw '600 句台词、生产字体缺字或像素宽度验证失败' }

$pytestTempRoot = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("desktop-pet-release-tests-" + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $pytestTempRoot | Out-Null

& $python -m pytest -q -p no:cacheprovider --basetemp (Join-Path $pytestTempRoot 'core') --ignore=tests\test_window.py --ignore=tests\test_layered_window.py
if ($LASTEXITCODE -ne 0) { throw '自动测试失败' }

# Keep every Tk interaction test in the release gate, but isolate Tcl
# interpreters so one suite cannot leak GUI state into the next.
& $python -m pytest -q -p no:cacheprovider --basetemp (Join-Path $pytestTempRoot 'layered-window') tests\test_layered_window.py
if ($LASTEXITCODE -ne 0) { throw '逐像素透明窗口测试失败' }

& $python -m pytest -q -p no:cacheprovider --basetemp (Join-Path $pytestTempRoot 'window') tests\test_window.py
if ($LASTEXITCODE -ne 0) { throw '桌宠交互测试失败' }

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

$expectedExe = Join-Path $projectRoot 'dist\桌面宠物-6帧猫耳气泡版.exe'
if (-not [System.IO.Path]::GetFullPath($exeFiles[0].FullName).Equals(
    [System.IO.Path]::GetFullPath($expectedExe),
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Unexpected EXE name: $($exeFiles[0].Name)"
}

$exeFiles[0] | Select-Object FullName, Length, LastWriteTime
