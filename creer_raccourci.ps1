# VideoLoader - Creation du raccourci Bureau

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "VideoLoader.lnk"
$iconPath = Join-Path $scriptDir "videoloader.ico"
$launchScript = Join-Path $scriptDir "launch.vbs"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$launchScript`""
$shortcut.WorkingDirectory = $scriptDir
$shortcut.IconLocation = "$iconPath, 0"
$shortcut.Description = "VideoLoader"
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "Raccourci VideoLoader cree sur le Bureau !" -ForegroundColor Green
Write-Host "Double-clique sur l'icone pour lancer." -ForegroundColor Cyan
Read-Host "Appuie sur Entree pour fermer"
