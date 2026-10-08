<# The one command the desktop shortcut runs: start the live Mirror Dungeon window.

It does the five things a fresh session needs and that a bare
`python tools/window_step.py` call does not:

  1. find the Maa native library (the driver needs its directory);
  2. run `adb connect <address>` -- the driver never connects the device
     itself, so after the emulator or the adb server restarts the MuMu
     instance is simply absent from `adb devices` and the window dies with
     `window_failed` on `dumpsys window` (live 2026-10-08 02:15);
  3. replay the nonce from build/map-probe-authorization.json, the gate every
     live tool demands before it may send input;
  4. ask GitHub once (cached, backed off) whether a newer release exists, and
     stage it into build/updates when one does -- `-NoUpdate` skips the check,
     `update = false` in the settings file disables it for good;
  5. tee the console to build/mirror-console-<stamp>.log, so a window that
     stopped at 03:00 can still be read at breakfast.

Settings come from config/user-launch.json when that file exists (it is
private and git-ignored); the defaults below are the standing settings the
user asked for, and any key of that file overrides the matching default.
#>
[CmdletBinding()]
param(
    [string]$Label,
    [switch]$DryRun,
    [switch]$NoUpdate
)

$ErrorActionPreference = 'Stop'
$TaskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

$TaskSettings = [ordered]@{
    binary         = ''
    adb            = ''
    address        = '127.0.0.1:16416'
    steps          = 400
    rounds         = 5
    interval       = 6
    unknown_rounds = 40
    map_tries      = 10
    claim_tries    = 6
    defeat_tries   = 2
    run_store      = 'config/user-run-ledger.json'
    graces         = '1,3,5,6,8'
    grace_budget   = 60
    gift_keyword   = 'charge'
    gift_plan      = 'assets/resource/base/gift-plan.json'
    gift_search    = 'refuse'
    flow           = 'to_mirror,enter_mirror'
    after_flow     = $true
    update         = $true
    update_stage   = $true
    update_timeout = 120
}
$TaskUser = Join-Path $TaskRoot 'config/user-launch.json'
if (Test-Path -LiteralPath $TaskUser) {
    $TaskJson = Get-Content -LiteralPath $TaskUser -Raw | ConvertFrom-Json
    foreach ($TaskName in @($TaskJson.PSObject.Properties.Name)) {
        if ($TaskSettings.Contains($TaskName)) { $TaskSettings[$TaskName] = $TaskJson.$TaskName }
    }
}

$TaskBinary = [string]$TaskSettings.binary
if (-not $TaskBinary) {
    $TaskBinary = Get-ChildItem -LiteralPath (Join-Path $TaskRoot 'build') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'maafw/MaaFramework.dll') } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if ($TaskBinary) { $TaskBinary = Join-Path $TaskBinary 'maafw' }
if (-not $TaskBinary -or -not (Test-Path -LiteralPath (Join-Path $TaskBinary 'MaaFramework.dll'))) {
    throw 'No Maa native library found: pass binary in config/user-launch.json'
}

$TaskAdb = [string]$TaskSettings.adb
if (-not $TaskAdb) {
    $TaskAdb = @("$env:ProgramFiles\Netease\MuMu\nx_main\adb.exe", 'D:\Program Files\Netease\MuMu\nx_main\adb.exe') |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $TaskAdb) { $TaskAdb = (Get-Command adb -ErrorAction SilentlyContinue).Source }
if (-not $TaskAdb) { throw 'No adb.exe found: pass adb in config/user-launch.json' }

$TaskState = (& $TaskAdb connect $TaskSettings.address 2>&1 | Out-String).Trim()
Write-Host "adb: $TaskState"
$TaskState = (& $TaskAdb -s $TaskSettings.address get-state 2>&1 | Out-String).Trim()
if ($TaskState -ne 'device') { throw "the adb device is not ready at $($TaskSettings.address): $TaskState" }

$TaskAuth = Join-Path $TaskRoot 'build/map-probe-authorization.json'
if (-not (Test-Path -LiteralPath $TaskAuth)) {
    throw 'build/map-probe-authorization.json is missing: live input is not authorized'
}
$TaskNonce = (Get-Content -LiteralPath $TaskAuth -Raw | ConvertFrom-Json).nonce
if (-not $TaskNonce) { throw 'the authorization file carries no nonce' }

$TaskStamp = [DateTime]::Now.ToString('yyyyMMdd-HHmmss')
if (-not $Label) { $Label = "run-$TaskStamp" }
$TaskLog = Join-Path $TaskRoot "build/mirror-console-$TaskStamp.log"
$TaskPython = (Get-Command python -ErrorAction Stop).Source
$TaskScript = Join-Path $TaskRoot 'tools/window_step.py'
$TaskGate = @(
    '--binary', $TaskBinary,
    '--adb', $TaskAdb,
    '--address', [string]$TaskSettings.address,
    '--authorize', $TaskNonce
)

if ($TaskSettings.update -and -not $NoUpdate) {
    # The player asked the software to keep itself current from GitHub. One bounded,
    # cached check runs before the window: `config/user-update-state.json` remembers the
    # answer and backs off for an hour (longer on a rate limit), so starting the script
    # many times is not a request loop. A release is staged -- downloaded, checksummed
    # and unpacked into build/updates -- and installing it stays deliberate, because the
    # files of a window that is about to drive the game must not be swapped underneath.
    $TaskUpdate = Join-Path $TaskRoot 'tools/check_update.py'
    if (Test-Path -LiteralPath $TaskUpdate) {
        try {
            $TaskUpdateArgs = @($TaskUpdate, '--timeout', [string]$TaskSettings.update_timeout)
            if ($TaskSettings.update_stage -and -not $DryRun) { $TaskUpdateArgs += '--stage' }
            $TaskUpdateJson = (& $TaskPython $TaskUpdateArgs 2>&1 | Out-String) | ConvertFrom-Json
            $TaskUpdateLine = "update: $($TaskUpdateJson.status)"
            if ($TaskUpdateJson.version) { $TaskUpdateLine += " $($TaskUpdateJson.version)" }
            if (@($TaskUpdateJson.PSObject.Properties.Name) -contains 'stage') {
                $TaskUpdateLine += " (stage: $($TaskUpdateJson.stage.status)"
                if ($TaskUpdateJson.stage.reason) { $TaskUpdateLine += " $($TaskUpdateJson.stage.reason)" }
                $TaskUpdateLine += ')'
                if ($TaskUpdateJson.stage.package) { $TaskUpdateLine += " -> $($TaskUpdateJson.stage.package)" }
            }
            Write-Host $TaskUpdateLine
        } catch {
            Write-Host "update: check failed ($($_.Exception.Message))"
        }
    }
}

$TaskFlow = [string]$TaskSettings.flow
if ($TaskFlow) {
    # A window starts either from the lobby or from inside a run a previous window
    # left standing. One read-only observation (no input at all) decides which:
    # the menu walk is only needed when the client is not already in the dungeon.
    $TaskProbe = (& $TaskPython $TaskScript @TaskGate --observe-page 2>&1 | Out-String)
    $TaskScene = [regex]::Match($TaskProbe, '"scene"\s*:\s*"([A-Z_]+)"').Groups[1].Value
    Write-Host "the client is showing: $(if ($TaskScene) { $TaskScene } else { '(unreadable)' })"
    if ($TaskScene -and $TaskScene -notin @('HOME', 'UNKNOWN')) {
        Write-Host 'already inside the dungeon: the menu walk is skipped'
        $TaskFlow = ''
    }
}

$TaskArgs = @($TaskScript) + $TaskGate + @(
    '--steps', [string]$TaskSettings.steps,
    '--rounds', [string]$TaskSettings.rounds,
    '--interval', [string]$TaskSettings.interval,
    '--unknown-rounds', [string]$TaskSettings.unknown_rounds,
    '--map-tries', [string]$TaskSettings.map_tries,
    '--claim-tries', [string]$TaskSettings.claim_tries,
    '--defeat-tries', [string]$TaskSettings.defeat_tries,
    '--run-store', (Join-Path $TaskRoot $TaskSettings.run_store),
    '--graces', [string]$TaskSettings.graces,
    '--grace-budget', [string]$TaskSettings.grace_budget,
    '--gift-keyword', [string]$TaskSettings.gift_keyword,
    '--gift-plan', (Join-Path $TaskRoot $TaskSettings.gift_plan),
    '--gift-search', [string]$TaskSettings.gift_search,
    '--label', $Label
)
if ($TaskFlow) {
    $TaskArgs += @('--flow', $TaskFlow)
    if ($TaskSettings.after_flow) { $TaskArgs += '--after-flow' }
}

Write-Host "MaaLimbus mirror window: label $Label"
Write-Host "binary $TaskBinary"
Write-Host "console log $TaskLog"
if ($DryRun) {
    Write-Host ($TaskArgs -join ' ')
    return
}

# `Tee-Object -FilePath` created no file under a background invocation (2026-10-08
# 02:26, the log path was printed and never appeared), so the console is copied the
# long way: every line is shown and appended before the pipeline moves on.
& $TaskPython @TaskArgs 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -LiteralPath $TaskLog -Value $_ -Encoding utf8
}
$TaskCode = $LASTEXITCODE
Write-Host "the window stopped with exit code $TaskCode"
Write-Host "console log: $TaskLog"
