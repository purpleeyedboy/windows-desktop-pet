param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference = 'Stop'
$executablePath = [IO.Path]::GetFullPath($Executable)
$smokeRoot = Join-Path ([IO.Path]::GetTempPath()) ('desktop-pet-feed-startup-' + [Guid]::NewGuid().ToString('N'))
$previousLocal = $env:LOCALAPPDATA
$previousRoaming = $env:APPDATA
$previousSmoke = $env:DESKTOP_PET_SMOKE_CHECK
$previousDiagnostics = $env:DESKTOP_PET_STARTUP_DIAGNOSTICS
$started = $null
try {
    New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
    $env:LOCALAPPDATA = $smokeRoot
    $env:APPDATA = $smokeRoot
    $env:DESKTOP_PET_SMOKE_CHECK = '1'
    $env:DESKTOP_PET_STARTUP_DIAGNOSTICS = Join-Path $smokeRoot 'startup-error.txt'
    $started = Start-Process -FilePath $executablePath -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(8)
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 200
        $started.Refresh()
        if ($started.HasExited) { throw "FEED EXE exited before readiness: code $($started.ExitCode)" }
    }
    $marker = Join-Path $smokeRoot 'DesktopPet\smoke-ready.json'
    if (Test-Path $env:DESKTOP_PET_STARTUP_DIAGNOSTICS) { throw 'FEED startup recorded an exception' }
    if (-not (Test-Path $marker)) { throw 'FEED EXE never reached its Tk event loop and real runtime setup' }
    $ready = Get-Content $marker -Raw | ConvertFrom-Json
    if (-not $ready.ready -or -not $ready.same_runtime -or $ready.feed_frames -ne 6) {
        throw 'FEED runtime readiness marker is incomplete'
    }
    $statePath = Join-Path $smokeRoot 'DesktopPet\state.json'
    $state = Get-Content $statePath -Raw | ConvertFrom-Json
    if ($null -ne $state.data.pending_transaction -or $state.data.recent_operation_ids.Count -ne 0) {
        throw 'Startup smoke unexpectedly created a file transaction or reward'
    }
    Write-Output "FEED_EXE_STARTUP_OK: process survived 8 seconds; event loop, shared runtime and six frames ready; no file transaction"
    Write-Output 'This checks launch/readiness only. Native file recycling, DPI interaction and visual acceptance remain separate.'
}
catch {
    $diagnosticRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'build-feed-core-diagnostics'
    New-Item -ItemType Directory -Path $diagnosticRoot -Force | Out-Null
    $diagnostic = Join-Path $smokeRoot 'startup-error.txt'
    if (Test-Path $diagnostic) {
        Copy-Item -LiteralPath $diagnostic -Destination (Join-Path $diagnosticRoot 'startup-error.txt') -Force
        Get-Content -LiteralPath $diagnostic | Write-Output
    }
    $logFolder = Join-Path $smokeRoot 'DesktopPet\logs'
    if (Test-Path $logFolder) {
        Copy-Item -LiteralPath $logFolder -Destination $diagnosticRoot -Recurse -Force
        Get-ChildItem -LiteralPath $logFolder -Filter '*.log' | ForEach-Object { Get-Content $_.FullName -Tail 120 | Write-Output }
    }
    throw
}
finally {
    if ($null -ne $started) {
        $started.Refresh()
        if (-not $started.HasExited) {
            [void]$started.CloseMainWindow()
            if (-not $started.WaitForExit(3000)) { $started.Kill($true); $started.WaitForExit() }
        }
        $started.Dispose()
    }
    $env:LOCALAPPDATA = $previousLocal
    $env:APPDATA = $previousRoaming
    $env:DESKTOP_PET_SMOKE_CHECK = $previousSmoke
    $env:DESKTOP_PET_STARTUP_DIAGNOSTICS = $previousDiagnostics
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
}
