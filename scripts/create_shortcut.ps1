$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$packaged = Join-Path $projectRoot 'dist\Klicky\Klicky.exe'
$pythonw = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$shellObject = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Klicky.lnk'
$shortcut = $shellObject.CreateShortcut($shortcutPath)
if (Test-Path -LiteralPath $packaged) {
    $shortcut.TargetPath = $packaged
} elseif (Test-Path -LiteralPath $pythonw) {
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + (Join-Path $projectRoot 'launch.pyw') + '"'
} else {
    throw 'Run setup.bat or build.bat first.'
}
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Klicky accessible browser assistant'
$shortcut.Save()
Write-Host 'Klicky shortcut created on your desktop.'
