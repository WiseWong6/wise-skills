# Windows Performance Notes

This Mac skill must not run Windows commands. Use these notes only to explain how a future Windows-specific skill should map the same workflow.

## Low-permission defaults

- CPU and memory: PowerShell `Get-Process`, performance counters, Task Manager-style process lists.
- Disk: drive free space, aggregate disk performance counters, process I/O counters where available.
- Network: aggregate adapter counters and connection tables; avoid deep per-process traffic by default.
- Startup and background: Startup folders, Run keys read-only, Scheduled Tasks read-only, Services read-only.
- Reporting: explain in Chinese first, then ask before cleanup. Do not stop services or edit registry by default.

## Deep options that need confirmation

| Area | Use | Risk |
|---|---|---|
| Registry startup deep audit | Find hidden or policy-managed startup entries | Registry data is sensitive; editing can break startup behavior |
| Event logs | Diagnose crashes, service failures, sleep/wake issues | Logs may contain paths, account names, URLs, and identifiers |
| WPR/WPA or ETW traces | CPU, disk, network, UI latency forensic tracing | Large trace files, sensitive event data, non-trivial overhead |
| Process dumps | Debug crashes/hangs | Very sensitive memory contents; large files |
| Service changes | Disable background services | Can break VPN, sync, security, enterprise management, or business apps |

Future implementation should be a separate `optimize-windows-performance` skill or an explicit platform branch, not mixed into this Mac shell script.
