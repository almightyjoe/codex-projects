Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$AppName = 'JJOES PRIVATES NETWORK'
$InstallRoot = Join-Path $env:ProgramData $AppName
$ProfilesDir = Join-Path $InstallRoot 'Profiles'
$WireGuardExe = Join-Path ${env:ProgramFiles} 'WireGuard\wireguard.exe'

New-Item -ItemType Directory -Force -Path $ProfilesDir | Out-Null

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal] $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ProfileFiles {
    Get-ChildItem -Path $ProfilesDir -Filter '*.conf' -ErrorAction SilentlyContinue | Sort-Object Name
}

function Get-SelectedProfile {
    if (-not $script:ProfileList.SelectedItem) {
        throw 'Choose a VPN profile first.'
    }

    return [string] $script:ProfileList.SelectedItem
}

function Get-TunnelNameFromProfile([string] $profilePath) {
    return [IO.Path]::GetFileNameWithoutExtension($profilePath)
}

function Refresh-Profiles {
    $script:ProfileList.Items.Clear()
    foreach ($profile in Get-ProfileFiles) {
        [void] $script:ProfileList.Items.Add($profile.FullName)
    }
    if ($script:ProfileList.Items.Count -gt 0) {
        $script:ProfileList.SelectedIndex = 0
    }
}

function Set-Status([string] $message) {
    $script:StatusLabel.Text = $message
}

function Ensure-Ready {
    if (-not (Test-IsAdministrator)) {
        throw 'Restart this client as Administrator to manage VPN tunnels.'
    }
    if (-not (Test-Path $WireGuardExe)) {
        throw 'WireGuard for Windows is not installed.'
    }
}

function Import-Profile {
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = 'WireGuard profiles (*.conf)|*.conf|All files (*.*)|*.*'
    $dialog.Title = 'Import JJOES PRIVATES NETWORK profile'
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        Copy-Item -Force -Path $dialog.FileName -Destination (Join-Path $ProfilesDir (Split-Path $dialog.FileName -Leaf))
        Refresh-Profiles
        Set-Status 'Profile imported.'
    }
}

function Connect-Profile {
    Ensure-Ready
    $profile = Get-SelectedProfile
    & $WireGuardExe /installtunnelservice $profile | Out-Null
    Set-Status "Connected: $(Get-TunnelNameFromProfile $profile)"
}

function Disconnect-Profile {
    Ensure-Ready
    $profile = Get-SelectedProfile
    $tunnelName = Get-TunnelNameFromProfile $profile
    & $WireGuardExe /uninstalltunnelservice $tunnelName | Out-Null
    Set-Status "Disconnected: $tunnelName"
}

function Show-Status {
    Ensure-Ready
    $services = Get-Service -Name 'WireGuardTunnel$*' -ErrorAction SilentlyContinue
    if (-not $services) {
        Set-Status 'No active WireGuard tunnels.'
        return
    }

    $summary = ($services | ForEach-Object { "$($_.DisplayName): $($_.Status)" }) -join '    '
    Set-Status $summary
}

$form = New-Object System.Windows.Forms.Form
$form.Text = $AppName
$form.Size = New-Object System.Drawing.Size(620, 330)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::FromArgb(250, 250, 248)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = $AppName
$title.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 18)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(24, 22)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = 'WireGuard profile manager'
$subtitle.AutoSize = $true
$subtitle.Location = New-Object System.Drawing.Point(27, 62)
$form.Controls.Add($subtitle)

$script:ProfileList = New-Object System.Windows.Forms.ComboBox
$script:ProfileList.DropDownStyle = 'DropDownList'
$script:ProfileList.Location = New-Object System.Drawing.Point(30, 105)
$script:ProfileList.Size = New-Object System.Drawing.Size(540, 30)
$form.Controls.Add($script:ProfileList)

$importButton = New-Object System.Windows.Forms.Button
$importButton.Text = 'Import Profile'
$importButton.Location = New-Object System.Drawing.Point(30, 155)
$importButton.Size = New-Object System.Drawing.Size(125, 38)
$importButton.Add_Click({ try { Import-Profile } catch { Set-Status $_.Exception.Message } })
$form.Controls.Add($importButton)

$connectButton = New-Object System.Windows.Forms.Button
$connectButton.Text = 'Connect'
$connectButton.Location = New-Object System.Drawing.Point(170, 155)
$connectButton.Size = New-Object System.Drawing.Size(110, 38)
$connectButton.Add_Click({ try { Connect-Profile } catch { Set-Status $_.Exception.Message } })
$form.Controls.Add($connectButton)

$disconnectButton = New-Object System.Windows.Forms.Button
$disconnectButton.Text = 'Disconnect'
$disconnectButton.Location = New-Object System.Drawing.Point(295, 155)
$disconnectButton.Size = New-Object System.Drawing.Size(110, 38)
$disconnectButton.Add_Click({ try { Disconnect-Profile } catch { Set-Status $_.Exception.Message } })
$form.Controls.Add($disconnectButton)

$statusButton = New-Object System.Windows.Forms.Button
$statusButton.Text = 'Status'
$statusButton.Location = New-Object System.Drawing.Point(420, 155)
$statusButton.Size = New-Object System.Drawing.Size(110, 38)
$statusButton.Add_Click({ try { Show-Status } catch { Set-Status $_.Exception.Message } })
$form.Controls.Add($statusButton)

$script:StatusLabel = New-Object System.Windows.Forms.Label
$script:StatusLabel.Text = 'Ready.'
$script:StatusLabel.Location = New-Object System.Drawing.Point(30, 220)
$script:StatusLabel.Size = New-Object System.Drawing.Size(540, 40)
$script:StatusLabel.AutoEllipsis = $true
$form.Controls.Add($script:StatusLabel)

Refresh-Profiles

if (-not (Test-Path $WireGuardExe)) {
    Set-Status 'WireGuard is not installed. Run install-client.ps1 or install WireGuard manually.'
}
elseif (-not (Test-IsAdministrator)) {
    Set-Status 'Open as Administrator to connect or disconnect VPN profiles.'
}

[void] $form.ShowDialog()

