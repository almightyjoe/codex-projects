# Architecture

## Layers

`ConnectionObserver.App`

WPF desktop shell, view models, and user workflows.

`ConnectionObserver.Core`

Domain models and service contracts. This layer should stay free of Windows API details.

`ConnectionObserver.Infrastructure`

Windows network collection, SQLite persistence, geo-IP providers, firewall integration, and background monitoring infrastructure.

## First Implementation Choices

- UI: WPF on .NET 8 because this is a Windows-first tool.
- Persistence: SQLite, to keep the app local-first and portable.
- Background work: tray app or hosted worker process.
- Privileged operations: separate explicit elevation path for firewall changes.

## Design Bias

The app should prioritize dense, scannable operational views over marketing-style screens. The first screen should show useful network activity immediately.
