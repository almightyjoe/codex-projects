# Connection Observer

Connection Observer is an original Windows network-visibility tool inspired by the workflow we studied in Stardock Connection Explorer. The project is intentionally clean-room: it does not patch, redistribute, decompile, or reuse Stardock binaries, assets, names, license data, or proprietary services.

## Current Status

- .NET 8 solution scaffolded.
- WPF desktop shell created.
- Core connection, DNS note, alert rule, and settings models started.
- Windows snapshot service captures active TCP connections and UDP listeners with process ownership where available.
- SQLite storage saves connection history, DNS notes, alert rules, and alert events.
- Desktop tabs for live connections, stored history, DNS notes, alerts, and rules.
- Optional automatic refresh loop.
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

1. Add a tray/background monitor.
2. Add DNS event capture instead of manual DNS note storage only.
3. Add firewall block/unblock commands through a privileged boundary.
4. Add geo-IP provider abstraction and map visualization.
5. Add richer filtering/export controls for process, history, alerts, and settings views.
