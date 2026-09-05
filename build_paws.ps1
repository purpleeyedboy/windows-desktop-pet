param()

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
Set-Location -LiteralPath $projectRoot

$pythonCommand = Get-Command python -ErrorAction Stop
$python = $pythonCommand.Source
if ([string]::IsNullOrWhiteSpace($python)) {
    throw '当前 PATH 中没有可用的 Python'
}

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

# This candidate deliberately skips all automated test suites.
# Acceptance is performed by the user on a real Windows desktop.
& $python -m PyInstaller --noconfirm desktop_pet_paws.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败' }

$dist = Join-Path $projectRoot 'dist'
$exeFiles = @(Get-ChildItem -LiteralPath $dist -Filter '*.exe' -File)
if ($exeFiles.Count -ne 1) {
    throw "Expected exactly one EXE in dist, found $($exeFiles.Count)"
}

$expectedExe = Join-Path $dist '桌面宠物_双前肢按压鼠标.exe'
if (-not [System.IO.Path]::GetFullPath($exeFiles[0].FullName).Equals(
    [System.IO.Path]::GetFullPath($expectedExe),
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Unexpected EXE name: $($exeFiles[0].Name)"
}

$result = [PSCustomObject]@{
    Candidate = 'UNTESTED - pending user Windows acceptance'
    FullName = $exeFiles[0].FullName
    Length = $exeFiles[0].Length
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $expectedExe).Hash
}
$result | Format-List
