$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($PSScriptRoot); Set-Location $root
$venvPython=Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) { $python=$venvPython } else { $python=(Get-Command python -ErrorAction Stop).Source }
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ("desktop-pet-feed-core-tests-"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
try { & $python -m pytest -q -p no:cacheprovider --basetemp $testRoot tests\test_feed_core.py tests\test_feed_core_revision.py tests\test_windows_recycle_contract.py tests\test_feed_core_packaging.py; if ($LASTEXITCODE -ne 0) { throw '自动测试失败' } }
finally { if ($testRoot.StartsWith([IO.Path]::GetTempPath()) -and (Test-Path $testRoot)) { Remove-Item -LiteralPath $testRoot -Recurse -Force } }
$buildInfoDir=Join-Path $root 'build-feed-core-metadata'; New-Item -ItemType Directory -Path $buildInfoDir -Force | Out-Null
$buildInfo=Get-Content BUILD_INFO_FEED_CORE.json -Raw | ConvertFrom-Json
$buildInfo.git_short_hash=(& git rev-parse --short HEAD).Trim()
$generatedInfo=Join-Path $buildInfoDir 'BUILD_INFO_FEED_CORE.json'
$buildInfo | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $generatedInfo -Encoding utf8
$env:DESKTOP_PET_FEED_BUILD_INFO=$generatedInfo
Remove-Item build-feed-core,dist-feed-core -Recurse -Force -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --workpath build-feed-core --distpath dist-feed-core desktop_pet_feed_core.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败' }
$exes=@(Get-ChildItem dist-feed-core -Filter *.exe -File)
if ($exes.Count -ne 1) { throw "Expected exactly one EXE; found $($exes.Count)" }
if ($exes[0].Name -ne '桌面宠物_文件喂食与回收站事务.exe') { throw "Unexpected EXE: $($exes[0].Name)" }
& $python tools\verify_feed_core_archive.py $exes[0].FullName
if ($LASTEXITCODE -ne 0) { throw '冻结归档缺少 feed_core 模块' }
$selfTestReport=Join-Path $buildInfoDir 'frozen-self-test.json'
& $exes[0].FullName --self-test-output $selfTestReport
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $selfTestReport) -or (Get-Content $selfTestReport -Raw) -notmatch '"mode": "SIMULATION"') { throw '冻结候选模拟自检失败' }
$hash=Get-FileHash -LiteralPath $exes[0].FullName -Algorithm SHA256
$exes[0] | Select-Object Name,Length
"SHA256: $($hash.Hash)"
