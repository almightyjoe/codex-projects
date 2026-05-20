# Mobile Clients

## iPhone

The first supported iPhone path is the official WireGuard app:

1. Install WireGuard from the App Store.
2. Run the Raspberry Pi installer or add a new client:

   ```bash
   sudo JJPN_ENDPOINT=vpn.example.com jjpn-add-client joes-iphone
   ```

3. Scan the printed QR code in the WireGuard app.
4. Toggle the tunnel on.

This is the fastest reliable way to use the VPN from iPhone because Apple VPN
apps require special Network Extension support and signing.

## Windows

Windows is the first branded client target in this project. The PowerShell
installer installs WireGuard, copies `JJPNClient.ps1`, and creates a shortcut.

The Windows client can:

- import a generated `.conf` profile
- connect the selected tunnel
- disconnect the selected tunnel
- display WireGuard service status

## Android and macOS

The generated `.conf` profiles are standard WireGuard profiles. Android and
macOS can use the official WireGuard apps until project-specific branded clients
are added.

