$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($PSScriptRoot); Set-Location $root
$python=if(Test-Path '.venv\Scripts\python.exe'){'.venv\Scripts\python.exe'}else{(Get-Command python -ErrorAction Stop).Source}
& $python tools\build_feed_frames.py
if($LASTEXITCODE -ne 0){throw 'Deterministic FEED frame generation failed'}
foreach($foundationFile in @('src\desktop_pet\foundation\services.py','src\desktop_pet\foundation\runtime.py')){if(-not(Test-Path $foundationFile)){throw "Missing codex-od26j1 f617765 foundation file: $foundationFile"}}
& $python tools\check_feed_foundation_gate.py
if($LASTEXITCODE -ne 0){throw 'Shared FEED runtime wiring and transaction failure gate failed'}
& $python -m compileall -q src run_desktop_pet.py tools\build_feed_frames.py tools\verify_feed_core_archive.py
if($LASTEXITCODE -ne 0){throw 'Python compile check failed'}
foreach($required in @('assets\keyframes','assets\generated\work\feed\v1','assets\feed\v1\manifest.json','assets\feed\v1\source\feed-face-patches.base64.txt','assets\bubble','assets\fonts','assets\dialogue','assets\rig\v1\source\eye-neutral-v1','THIRD_PARTY_NOTICES.txt')){if(-not(Test-Path $required)){throw "Missing resource: $required"}}
$meta=Join-Path $root 'build-feed-core-metadata';New-Item -ItemType Directory -Path $meta -Force|Out-Null
$info=Get-Content BUILD_INFO_FEED_CORE.json -Raw|ConvertFrom-Json;$sourceHead=if($env:SOURCE_HEAD_SHA){$env:SOURCE_HEAD_SHA}else{(& git rev-parse HEAD).Trim()};if($sourceHead -notmatch '^[0-9a-fA-F]{40}$'){throw 'Invalid source head SHA'};$info.source_head_sha=$sourceHead;$info.git_short_hash=$sourceHead.Substring(0,7);$generated=Join-Path $meta 'BUILD_INFO_FEED_CORE.json';$info|ConvertTo-Json -Depth 5|Set-Content $generated -Encoding utf8;$env:DESKTOP_PET_FEED_BUILD_INFO=$generated
Remove-Item build-feed-core,dist-feed-core -Recurse -Force -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --workpath build-feed-core --distpath dist-feed-core desktop_pet_feed_core.spec
if($LASTEXITCODE -ne 0){throw 'PyInstaller build failed'}
$exes=@(Get-ChildItem dist-feed-core -Filter *.exe -File);if($exes.Count -ne 1){throw "Expected exactly one EXE; found $($exes.Count)"};if($exes[0].Name -ne '桌面宠物_文件进食动画恢复候选.exe'){throw 'Unexpected EXE'}
& $python tools\verify_eye_follow_candidate_archive.py $exes[0].FullName;if($LASTEXITCODE -ne 0){throw 'Resource archive check failed'}
& $python tools\verify_feed_core_archive.py $exes[0].FullName;if($LASTEXITCODE -ne 0){throw 'feed_core archive check failed'}
& (Join-Path $root 'tools\check_feed_exe_startup.ps1') -Executable $exes[0].FullName
$hash=Get-FileHash $exes[0].FullName -Algorithm SHA256;$exes[0]|Select Name,Length;"SHA256: $($hash.Hash)"
