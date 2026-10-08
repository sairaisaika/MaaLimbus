<# Put the MaaLimbus entry on the Desktop as a double-clickable shortcut.

By default this points at the assembled app (dist/MaaLimbus/MaaLimbus.exe), which
is the MXU ProjectInterface V2 window: the Maa-style way to start the project, the
same shape as other Maa projects' installers. When that app has not been assembled
yet it falls back to tools/start-mirror.cmd, the console launcher, so the shortcut
still does something. Its icon is the project's own Don Quixote asset, converted to
.ico beside the target (the ICO is a build artifact, not a source file). Re-running
this script replaces the shortcut; it never touches anything else on the Desktop.
#>
[CmdletBinding()]
param(
    [string]$Name = '',
    [string]$Target = '',
    [string]$WorkDir = ''
)

$ErrorActionPreference = 'Stop'
$TaskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

$TaskApp = Join-Path $TaskRoot 'dist/MaaLimbus/MaaLimbus.exe'
$TaskLauncher = Join-Path $TaskRoot 'dist/MaaLimbus/launcher/MaaLimbusLauncher.exe'
if (-not $Target) {
    if (Test-Path -LiteralPath $TaskApp) {
        if (Test-Path -LiteralPath $TaskLauncher) { $Target = $TaskLauncher } else { $Target = $TaskApp }
        $WorkDir = Join-Path $TaskRoot 'dist/MaaLimbus'
        if (-not $Name) { $Name = 'MaaLimbus' }
    } else {
        $Target = Join-Path $TaskRoot 'tools/start-mirror.cmd'
        $WorkDir = $TaskRoot
        if (-not $Name) { $Name = 'MaaLimbus 镜牢' }
    }
}
if (-not (Test-Path -LiteralPath $Target)) { throw "the launcher is missing: $Target" }
if (-not $WorkDir) { $WorkDir = Split-Path -Parent $Target }

$TaskDesktop = [Environment]::GetFolderPath('Desktop')
if (-not $TaskDesktop) { throw 'no Desktop folder for this user' }

$TaskIcon = Join-Path $WorkDir 'MaaLimbus.ico'
$TaskPng = Join-Path $TaskRoot 'assets/misc/Don-Quixote.png'
if (Test-Path -LiteralPath $TaskPng) {
    $TaskPython = (Get-Command python -ErrorAction Stop).Source
    $TaskCode = "from PIL import Image; Image.open(r'$TaskPng').save(r'$TaskIcon', sizes=[(256,256)])"
    & $TaskPython -c $TaskCode
    if ($LASTEXITCODE -ne 0) { Write-Warning 'the ICO could not be built; the shortcut keeps the default icon' }
}

$TaskShortcut = Join-Path $TaskDesktop "$Name.lnk"
$TaskShell = New-Object -ComObject WScript.Shell
$TaskLink = $TaskShell.CreateShortcut($TaskShortcut)
$TaskLink.TargetPath = $Target
$TaskLink.WorkingDirectory = $WorkDir
$TaskLink.Description = 'Start MaaLimbus (Mirror Dungeon: auto battle, five floors, claim, next run)'
if (Test-Path -LiteralPath $TaskIcon) { $TaskLink.IconLocation = $TaskIcon }
$TaskLink.Save()

Write-Host "shortcut: $TaskShortcut"
Write-Host "target:   $Target"
Write-Host "workdir:  $WorkDir"
if (Test-Path -LiteralPath $TaskIcon) { Write-Host "icon:     $TaskIcon" }
