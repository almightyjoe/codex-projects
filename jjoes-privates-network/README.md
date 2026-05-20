# JJOES PRIVATES NETWORK

JJOES PRIVATES NETWORK is a small, self-hosted VPN project built around WireGuard.
It provides:

- a one-command Raspberry Pi server installer
- generated client profiles for Windows and iPhone
- a branded Windows client launcher for importing, connecting, disconnecting, and checking status

WireGuard is used for the actual encrypted tunnel. This project adds a repeatable
setup, naming, profile generation, and a simple Windows experience around it.

## Repository Layout

```text
server/raspi/install-server.sh      Raspberry Pi VPN server installer
client/windows/install-client.ps1   Windows client installer
client/windows/JJPNClient.ps1       Branded Windows VPN launcher
docs/architecture.md                System design notes
docs/mobile-clients.md              iPhone and future client notes
```

## Raspberry Pi Server Install

On a Raspberry Pi running Raspberry Pi OS or Debian:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USER/YOUR_REPO/main/server/raspi/install-server.sh -o install-server.sh
chmod +x install-server.sh
sudo ./install-server.sh --endpoint vpn.example.com --client-name joes-windows
```

The installer:

- installs WireGuard and QR tooling
- creates `/etc/wireguard/jjpn0.conf`
- enables IP forwarding
- adds NAT/firewall rules
- starts `wg-quick@jjpn0`
- creates the first client profile at `/etc/wireguard/jjpn-clients/<client>.conf`
- prints a QR code for phone setup

Use the generated `.conf` file with the Windows installer, or scan the QR code
with the official WireGuard iPhone app.

## Windows Client Install

From an elevated PowerShell prompt:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\client\windows\install-client.ps1 -ProfilePath .\joes-windows.conf
```

The installer copies the branded client to:

```text
C:\ProgramData\JJOES PRIVATES NETWORK
```

It also installs WireGuard with `winget` when available and creates a Desktop
shortcut named `JJOES PRIVATES NETWORK`.

## Client Profile Flow

1. Run the Raspberry Pi installer.
2. Copy the generated client profile from the Pi:

   ```bash
   sudo cat /etc/wireguard/jjpn-clients/joes-windows.conf
   ```

3. Save that content on Windows as `joes-windows.conf`.
4. Run the Windows installer with `-ProfilePath`.
5. Open `JJOES PRIVATES NETWORK` and connect.

## Security Notes

- Keep generated client `.conf` files private. They contain VPN private keys.
- Create a separate client profile per device.
- Revoke lost devices by removing their `[Peer]` block from `/etc/wireguard/jjpn0.conf`
  and restarting the tunnel with `sudo systemctl restart wg-quick@jjpn0`.
- Prefer a dynamic DNS name for home internet connections where the public IP changes.

