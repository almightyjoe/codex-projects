[CmdletBinding()]
param(
    [string] $ProfilePath,
    [switch] $SkipWireGuardInstall
)

$ErrorActionPreference = 'Stop'
$AppName = 'JJOES PRIVATES NETWORK'
$InstallRoot = Join-Path $env:ProgramData $AppName
$ClientScript = Join-Path $InstallRoot 'JJPNClient.ps1'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal] $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    throw 'Run this installer from an elevated PowerShell prompt.'
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Force -Path (Join-Path $PSScriptRoot 'JJPNClient.ps1') -Destination $ClientScript

if (-not $SkipWireGuardInstall) {
    $wireGuardExe = Join-Path ${env:ProgramFiles} 'WireGuard\wireguard.exe'
    if (-not (Test-Path $wireGuardExe)) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            winget install --id WireGuard.WireGuard --exact --accept-package-agreements --accept-source-agreements
        }
        else {
            Write-Warning 'winget was not found. Install WireGuard for Windows from https://www.wireguard.com/install/ and rerun this installer.'
        }
    }
}

if ($ProfilePath) {
    if (-not (Test-Path $ProfilePath)) {
        throw "Profile not found: $ProfilePath"
    }

    $profilesDir = Join-Path $InstallRoot 'Profiles'
    New-Item -ItemType Directory -Force -Path $profilesDir | Out-Null
    Copy-Item -Force -Path $ProfilePath -Destination (Join-Path $profilesDir (Split-Path $ProfilePath -Leaf))
}

$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$ClientScript`""
$shortcut.WorkingDirectory = $InstallRoot
$shortcut.IconLocation = Join-Path ${env:ProgramFiles} 'WireGuard\wireguard.exe'
$shortcut.Save()

Write-Host "$AppName installed."
Write-Host "Open the Desktop shortcut to import or manage a VPN profile."

