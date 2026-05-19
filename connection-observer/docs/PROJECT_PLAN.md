# Project Plan

## Phase 1: Foundation

- Establish solution structure.
- Capture active TCP and UDP listeners.
- Introduce domain models for connections, DNS records, alerts, bandwidth samples, and firewall actions.
- Add unit tests for core models and filtering behavior.

## Phase 2: Windows Network Collection

- Resolve owning process IDs and executable paths.
- Track first-seen and last-seen timestamps across snapshots.
- Add DNS event capture or cache ingestion.
- Normalize local, loopback, LAN, and internet destinations.

## Phase 3: Persistence

- Add SQLite storage.
- Store connection snapshots, DNS history, app bandwidth buckets, alert events, notes, and user settings.
- Add retention cleanup.

## Phase 4: Desktop Experience

- Build views for dashboard, connections, processes, DNS, history, alerts, and settings.
- Add search/filter/export.
- Add bandwidth charts.
- Add geo-IP map.

## Phase 5: Control and Protection

- Add alert rule evaluation.
- Add firewall block/unblock operations.
- Add admin elevation flow for privileged actions.
- Add tray monitor and notifications.

## Phase 6: Packaging

- Add app icon and original visual identity.
- Add installer or portable package.
- Add GitHub Actions build/test workflow.
- Publish signed release artifacts when ready.
