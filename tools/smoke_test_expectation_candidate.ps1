[CmdletBinding()]
param([string]$CandidatePath = "dist-drag-expectation-candidate/桌面宠物_期待逐帧与公共基础接入.exe")
$ErrorActionPreference = "Stop"
$candidate = (Resolve-Path -LiteralPath $CandidatePath).Path
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("expectation-startup-" + [guid]::NewGuid().ToString("N"))
$candidateProcess = $null
$ownedIds = [Collections.Generic.HashSet[int]]::new()

# A PyInstaller onefile launcher owns a separate process containing the Tk UI.
# Enumerate visible windows belonging only to this launch's process tree.
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class ExpectationSmokeWindows {
    private delegate bool Callback(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] private static extern bool EnumWindows(Callback callback, IntPtr data);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr window, StringBuilder text, int count);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr window, StringBuilder text, int count);
    public static string[] Visible(int[] processIds) {
        var owned = new HashSet<int>(processIds);
        var result = new List<string>();
        EnumWindows((window, data) => {
            uint process;
            GetWindowThreadProcessId(window, out process);
            if (owned.Contains((int)process) && IsWindowVisible(window)) {
                var title = new StringBuilder(512);
                var kind = new StringBuilder(128);
                GetWindowText(window, title, title.Capacity);
                GetClassName(window, kind, kind.Capacity);
                result.Add(kind.ToString() + "|" + title.ToString());
            }
            return true;
        }, IntPtr.Zero);
        return result.ToArray();
    }
}
'@

function Update-OwnedProcessTree {
    $snapshot = @(Get-CimInstance Win32_Process)
    do {
        $added = $false
        foreach ($item in $snapshot) {
            if ($ownedIds.Contains([int]$item.ParentProcessId)) {
                if ($ownedIds.Add([int]$item.ProcessId)) { $added = $true }
            }
        }
    } while ($added)
}

try {
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    $start = [Diagnostics.ProcessStartInfo]::new($candidate)
    $start.UseShellExecute = $false
    $start.WorkingDirectory = $testRoot
    foreach ($entry in (@{ APPDATA = "Roaming"; LOCALAPPDATA = "Local"; TEMP = "Temp"; TMP = "Temp" }).GetEnumerator()) {
        $path = Join-Path $testRoot $entry.Value
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        $start.Environment[$entry.Key] = $path
    }
    # Isolate the application's per-user mutex as well as its filesystem state.
    $start.Environment["USERNAME"] = "ExpectationCI-" + [guid]::NewGuid().ToString("N")
    $start.Environment["DESKTOP_PET_SMOKE_CHECK"] = "1"
    $diagnostic = Join-Path $testRoot "startup-error.txt"
    $start.Environment["DESKTOP_PET_STARTUP_DIAGNOSTICS"] = $diagnostic
    $candidateProcess = [Diagnostics.Process]::Start($start)
    $ownedIds.Add($candidateProcess.Id) | Out-Null
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        Start-Sleep -Milliseconds 250
        Update-OwnedProcessTree
        $candidateProcess.Refresh()
        if ($candidateProcess.HasExited) { throw "Candidate exited during startup: $($candidateProcess.ExitCode)" }
    } while ($timer.Elapsed.TotalSeconds -lt 7)
    if (Test-Path -LiteralPath $diagnostic) { Get-Content -LiteralPath $diagnostic | Write-Output; throw "Candidate recorded a startup/callback exception" }
    $marker = Join-Path $testRoot "Local\DesktopPet\smoke-ready.json"
    if (-not (Test-Path -LiteralPath $marker)) { throw "Candidate never reached its Tk event loop" }
    $ready = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if (-not $ready.ready -or -not $ready.same_runtime -or $ready.expectation_frames -ne 5) { throw "Incomplete runtime/frame readiness" }
    $state = Get-Content -LiteralPath (Join-Path $testRoot "Local\DesktopPet\state.json") -Raw | ConvertFrom-Json
    if ($null -ne $state.data.pending_transaction -or $state.data.recent_operation_ids.Count -ne 0) { throw "Startup unexpectedly created a file transaction or reward" }
    $windows = @([ExpectationSmokeWindows]::Visible([int[]]@($ownedIds)))
    if (@($windows | Where-Object { $_ -match '无法启动|Fatal error|Traceback' }).Count) {
        throw "Candidate displayed an error window: $($windows -join ', ')"
    }
    if (-not @($windows | Where-Object { $_ -like 'TkTopLevel|桌面宠物 V2.1-EXPECT |*' }).Count) {
        throw "No identified visible Tk candidate window in the launched process tree: $($windows -join ', ')"
    }
    "Isolated candidate process tree displayed its identified Tk window after seven seconds; pending user visual acceptance." |
        Tee-Object -FilePath $env:GITHUB_STEP_SUMMARY -Append
} finally {
    if ($null -ne $candidateProcess) {
        Update-OwnedProcessTree
        # These IDs came only from this Process.Start call and its descendants.
        foreach ($childId in @($ownedIds | Where-Object { $_ -ne $candidateProcess.Id })) {
            Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
        }
        $candidateProcess.Refresh()
        if (-not $candidateProcess.HasExited) {
            Stop-Process -Id $candidateProcess.Id -Force -ErrorAction SilentlyContinue
            $candidateProcess.WaitForExit(5000) | Out-Null
        }
    }
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}
