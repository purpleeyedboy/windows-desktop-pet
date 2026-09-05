$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($PSScriptRoot); Set-Location $root
$python=if(Test-Path '.venv\Scripts\python.exe'){'.venv\Scripts\python.exe'}else{(Get-Command python -ErrorAction Stop).Source}
& $python -m compileall -q src run_desktop_pet.py tools\verify_feed_core_archive.py
if($LASTEXITCODE -ne 0){throw 'Python compile check failed'}
foreach($required in @('assets\keyframes','assets\bubble','assets\fonts','assets\dialogue','assets\rig\v1\source\eye-neutral-v1','THIRD_PARTY_NOTICES.txt')){if(-not(Test-Path $required)){throw "Missing resource: $required"}}
$meta=Join-Path $root 'build-feed-core-metadata';New-Item -ItemType Directory -Path $meta -Force|Out-Null
$info=Get-Content BUILD_INFO_FEED_CORE.json -Raw|ConvertFrom-Json;$info.git_short_hash=(& git rev-parse --short HEAD).Trim();$generated=Join-Path $meta 'BUILD_INFO_FEED_CORE.json';$info|ConvertTo-Json -Depth 5|Set-Content $generated -Encoding utf8;$env:DESKTOP_PET_FEED_BUILD_INFO=$generated
Remove-Item build-feed-core,dist-feed-core -Recurse -Force -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --workpath build-feed-core --distpath dist-feed-core desktop_pet_feed_core.spec
if($LASTEXITCODE -ne 0){throw 'PyInstaller build failed'}
$exes=@(Get-ChildItem dist-feed-core -Filter *.exe -File);if($exes.Count -ne 1){throw "Expected exactly one EXE; found $($exes.Count)"};if($exes[0].Name -ne '桌面宠物_文件喂食与回收站事务.exe'){throw 'Unexpected EXE'}
& $python tools\verify_eye_follow_candidate_archive.py $exes[0].FullName;if($LASTEXITCODE -ne 0){throw 'Resource archive check failed'}
& $python tools\verify_feed_core_archive.py $exes[0].FullName;if($LASTEXITCODE -ne 0){throw 'feed_core archive check failed'}
$hash=Get-FileHash $exes[0].FullName -Algorithm SHA256;$exes[0]|Select Name,Length;"SHA256: $($hash.Hash)"
