# Research Notes

## Reference Product Scope

Public documentation and local observation show the reference product covers:

- live network map with recent connection dots
- active TCP/UDP connection listing
- process-centric network activity
- DNS history and per-entry notes
- alert rules and alert history
- ping/traceroute utilities
- bandwidth timelines
- firewall blocking for applications and IPs
- system tray monitoring
- data retention settings

## Local Installation Observations

Observed installation path:

```text
C:\Program Files\Stardock\ConnectionExplorer
```

Observed user data path:

```text
C:\Users\joeln\AppData\Local\Stardock\ConnectionExplorer
```

Observed implementation traits:

- self-contained .NET 8 Windows desktop app
- WPF UI
- separate tray executable
- SQLite local database
- scheduled task for tray startup
- geo-IP seed data
- localized string files

These notes are for feature understanding only. The custom implementation should use original code, original schemas where practical, and independently selected data sources.
