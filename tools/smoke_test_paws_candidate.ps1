[CmdletBinding()]
param([string]$CandidatePath = "dist/桌面宠物_双前肢位移2.5倍_释放与边界验证_20260910候选.exe")
$ErrorActionPreference = "Stop"
$candidate = (Resolve-Path -LiteralPath $CandidatePath).Path
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("paws-startup-" + [guid]::NewGuid().ToString("N"))
$candidateProcess = $null
$ownedIds = [Collections.Generic.HashSet[int]]::new()

# A PyInstaller onefile launcher owns a separate process containing the Tk UI.
# Enumerate visible windows belonging only to this launch's process tree.
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class PawsSmokeWindows {
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
    $start.Environment["USERNAME"] = "PawsCI-" + [guid]::NewGuid().ToString("N")
    $candidateProcess = [Diagnostics.Process]::Start($start)
    $ownedIds.Add($candidateProcess.Id) | Out-Null
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        Start-Sleep -Milliseconds 250
        Update-OwnedProcessTree
        $candidateProcess.Refresh()
        if ($candidateProcess.HasExited) { throw "Candidate exited during startup: $($candidateProcess.ExitCode)" }
    } while ($timer.Elapsed.TotalSeconds -lt 7)
    $windows = @([PawsSmokeWindows]::Visible([int[]]@($ownedIds)))
    if (@($windows | Where-Object { $_ -match '无法启动|Fatal error|Traceback' }).Count) {
        throw "Candidate displayed an error window: $($windows -join ', ')"
    }
    if (-not @($windows | Where-Object { $_ -match '^TkTopLevel\|桌面宠物 V2\.1-CORE \| 2\.1\.2-paws \| git:[0-9a-f]{8} \| foundation:4eda8964$' }).Count) {
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
