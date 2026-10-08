<# Put the Mirror Dungeon launcher on the Desktop as a double-clickable shortcut.

The shortcut points at tools/start-mirror.cmd, so the console stays open when
the window stops and the reason it stopped stays readable. Its icon is the
project's own Don Quixote asset, converted to .ico in build/ (the ICO is a
build artifact, not a source file). Re-running this script replaces the
shortcut; it never touches anything else on the Desktop.
#>
[CmdletBinding()]
param(
    [string]$Name = 'MaaLimbus 镜牢',
    [string]$Target = ''
)

$ErrorActionPreference = 'Stop'
$TaskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Target) { $Target = Join-Path $TaskRoot 'tools/start-mirror.cmd' }
if (-not (Test-Path -LiteralPath $Target)) { throw "the launcher is missing: $Target" }

$TaskDesktop = [Environment]::GetFolderPath('Desktop')
if (-not $TaskDesktop) { throw 'no Desktop folder for this user' }

$TaskIcon = Join-Path $TaskRoot 'build/MaaLimbus.ico'
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
$TaskLink.WorkingDirectory = $TaskRoot
$TaskLink.Description = 'Start the MaaLimbus Mirror Dungeon window (auto battle, five floors, claim, next run)'
if (Test-Path -LiteralPath $TaskIcon) { $TaskLink.IconLocation = $TaskIcon }
$TaskLink.Save()

Write-Host "shortcut: $TaskShortcut"
Write-Host "target:   $Target"
Write-Host "workdir:  $TaskRoot"
if (Test-Path -LiteralPath $TaskIcon) { Write-Host "icon:     $TaskIcon" }
