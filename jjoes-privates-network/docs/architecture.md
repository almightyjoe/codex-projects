# Architecture

JJOES PRIVATES NETWORK uses WireGuard as the VPN engine and adds project-owned
installation and client management around it.

## Components

- Raspberry Pi server: Debian/Raspberry Pi OS host running `wg-quick@jjpn0`.
- Client profiles: WireGuard `.conf` files generated one per device.
- Windows client: PowerShell/WinForms launcher that wraps WireGuard for Windows.
- iPhone client: official WireGuard app using the generated QR code or profile.

## Network Defaults

- VPN subnet: `10.44.0.0/24`
- Server address: `10.44.0.1`
- Server interface: `jjpn0`
- UDP port: `51820`
- Default client route: all traffic through the VPN

The Raspberry Pi installer accepts `--split-tunnel` when only `10.44.0.0/24`
should be routed through the VPN.

## Why WireGuard

VPN software should not invent cryptography. WireGuard gives this project:

- modern, audited tunnel primitives
- native Windows and iPhone support
- small Raspberry Pi footprint
- simple text profiles that are easy to generate and revoke

## Future iPhone App Path

Apple does not allow normal apps to create arbitrary VPN tunnels without using
Network Extension entitlements. A custom iPhone app is possible later, but the
practical first version is generated WireGuard profiles plus QR onboarding.

## Revocation

Each device has its own public key and `[Peer]` block in `/etc/wireguard/jjpn0.conf`.
To revoke a device:

1. remove that peer block
2. delete the matching file in `/etc/wireguard/jjpn-clients`
3. run `sudo systemctl restart wg-quick@jjpn0`

