# Connection Observer

Connection Observer is an original Windows network-visibility tool inspired by the workflow we studied in Stardock Connection Explorer. The project is intentionally clean-room: it does not patch, redistribute, decompile, or reuse Stardock binaries, assets, names, license data, or proprietary services.

## Current Status

- .NET 8 solution scaffolded.
- WPF desktop shell created.
- Core network connection domain model started.
- First system snapshot service captures active TCP connections and UDP listeners.
- Unit test project added.

## Project Layout

```text
connection-observer/
  docs/                         Project notes, research, legal boundaries, roadmap
  src/
    ConnectionObserver.App/      WPF desktop application
    ConnectionObserver.Core/     Domain models and service contracts
    ConnectionObserver.Infrastructure/ Windows/network implementation details
  tests/
    ConnectionObserver.Tests/    Unit tests
  tools/                         Future helper scripts
```

## Build

```powershell
dotnet build
dotnet test
```

## Near-Term Goals

1. Add Windows-specific process ownership for TCP/UDP connections.
2. Add SQLite persistence for connection snapshots, DNS records, notes, and alert events.
3. Add a tray/background monitor.
4. Add firewall block/unblock commands through a privileged boundary.
5. Add geo-IP provider abstraction and map visualization.
