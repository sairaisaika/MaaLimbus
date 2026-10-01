<# Runs inside the ordinary Windows UAC-approved process; no input outside Maa. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Binary,
    [ValidateSet('en','jp')][string]$Locale = 'en',
    [ValidateRange(1,3600)][int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
$TaskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $TaskRoot
$TaskOutput = Join-Path $TaskRoot 'build/native-live.stdout.log'
$TaskErrors = Join-Path $TaskRoot 'build/native-live.stderr.log'
$TaskPython = (Get-Command python -ErrorAction Stop).Source
function Quote-NativeArgument([string]$Value) {
    if ($Value.Contains('"')) { throw 'Invalid quote in launcher path' }
    return '"' + $Value + '"'
}
$TaskArguments = '-u ' + (Quote-NativeArgument (Join-Path $PSScriptRoot 'run_native.py')) +
    ' --binary ' + (Quote-NativeArgument $Binary) + ' --locale ' + $Locale + ' --seconds ' + $Seconds + ' --live'
$TaskRunner = Start-Process -FilePath $TaskPython -ArgumentList $TaskArguments -WorkingDirectory $TaskRoot `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput $TaskOutput -RedirectStandardError $TaskErrors
$TaskTimeout = -not $TaskRunner.WaitForExit(($Seconds+45)*1000)
if ($TaskTimeout) {
    # This is only the exact child created above. Its own native stop budget has expired.
    $TaskRunner.Kill()
    $TaskRunner.WaitForExit()
}
$TaskCode = if ($TaskTimeout) { 124 } else { $TaskRunner.ExitCode }
@{ exit_code=$TaskCode; timed_out=$TaskTimeout; runner_pid=$TaskRunner.Id;
   finished_at=[DateTime]::UtcNow.ToString('o'); wrapper_pid=$PID } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $TaskRoot 'build/native-launch-result.json') -Encoding utf8
exit $TaskCode
