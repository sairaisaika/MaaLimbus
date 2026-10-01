<# Standard UAC launcher, following MaaEnd/LALC. Does not bypass consent. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Binary,
    [ValidateSet('en','jp')][string]$Locale = 'en',
    [ValidateRange(1,3600)][int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
$TaskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$TaskBinary = (Resolve-Path -LiteralPath $Binary).Path
if (-not (Test-Path -LiteralPath (Join-Path $TaskBinary 'MaaFramework.dll'))) { throw 'Maa binary directory is invalid' }
$TaskRunning = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'MaaLimbusAgent.exe' -or $_.Name -eq 'MaaLimbus.exe' -or
    ($_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like "*$TaskRoot*run_native.py*")
}
if ($TaskRunning) { throw 'MaaLimbus already has a running controller; inspect its session first' }
New-Item -ItemType Directory -Path (Join-Path $TaskRoot 'build') -Force | Out-Null
function Quote-NativeArgument([string]$Value) {
    if ($Value.Contains('"')) { throw 'Invalid quote in launcher path' }
    return '"' + $Value + '"'
}
$TaskScript = Join-Path $PSScriptRoot 'native_session.ps1'
$TaskArguments = '-NoProfile -File ' + (Quote-NativeArgument $TaskScript) +
    ' -Binary ' + (Quote-NativeArgument $TaskBinary) + ' -Locale ' + $Locale + ' -Seconds ' + $Seconds
# UAC remains interactive. A cancelled request starts no controller.
$TaskPowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$TaskRequest = @{ launcher_pid=$PID; status='uac_requested'; started=[DateTime]::UtcNow.ToString('o');
                  seconds=$Seconds; input_sent=$false }
$TaskRequestPath = Join-Path $TaskRoot 'build/native-launch-request.json'
$TaskRequest | ConvertTo-Json | Set-Content -LiteralPath $TaskRequestPath -Encoding utf8
try {
    $TaskProcess = Start-Process -FilePath $TaskPowerShell -ArgumentList $TaskArguments `
        -WorkingDirectory $TaskRoot -Verb RunAs -WindowStyle Hidden -PassThru
}
catch {
    $TaskRequest.status='launch_failed_or_cancelled'
    $TaskRequest.error=$_.Exception.Message
    $TaskRequest.finished=[DateTime]::UtcNow.ToString('o')
    $TaskRequest | ConvertTo-Json | Set-Content -LiteralPath $TaskRequestPath -Encoding utf8
    throw
}
$TaskRequest.status='wrapper_started'
$TaskRequest.wrapper_pid=$TaskProcess.Id
$TaskRequest | ConvertTo-Json | Set-Content -LiteralPath $TaskRequestPath -Encoding utf8
@{ wrapper_pid=$TaskProcess.Id; started=[DateTime]::UtcNow.ToString('o'); seconds=$Seconds;
   stdout=(Join-Path $TaskRoot 'build/native-live.stdout.log'); stderr=(Join-Path $TaskRoot 'build/native-live.stderr.log') } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $TaskRoot 'build/native-launch.json') -Encoding utf8
Write-Output "Standard UAC launcher process: $($TaskProcess.Id)"
