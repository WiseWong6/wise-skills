---
name: optimize-system-performance
description: Diagnose Mac or Windows CPU, memory, heat or energy symptoms, disk and network load, local dev servers, background stability, and startup items with low-permission before/after evidence. Use when the user wants to understand why a computer is slow, hot, swapping, or cluttered with background processes, and wants safe reversible cleanup recommendations without sudo/admin rights, rebooting, deleting configs, disabling startup items, or stopping protected work services.
---

# Optimize System Performance

Use a diagnose-first workflow. The default mode is read-only: capture a baseline, explain the causes in plain Chinese, produce a per-PID confirmation plan with risk, benefit, and recovery, then wait for the user before any cleanup. Treat this as a diagnosis and decision skill, not an automatic cleaner.

## Safety Rules

- Default actions must be L0/L1 only: low-permission sampling, Chinese explanation, and cleanup recommendations.
- Do not use `sudo`, elevated PowerShell, reboot, log out, clear caches, delete configs, disable startup items, unload plists, edit registry, change services, change scheduled tasks, or force-kill processes by default.
- Do not stop browser main processes, remote control, VPN/proxy, sync drives, input methods, security software, enterprise management, meeting software, IDEs, Docker/VMs, Codex/Claude sessions, or local business services unless the user confirms a specific PID after seeing the risk.
- Do not batch-clean from a broad instruction such as "clean it"; list the exact PID/service/port candidate first and ask for per-item confirmation.
- When cleanup is confirmed, use only gentle user-process termination: macOS `kill -TERM <pid>`; Windows `Stop-Process -Id <pid>` without `-Force`. If it fails, report it and stop.
- Deep forensics are opt-in only. Before any high-risk tool, read the relevant reference and explain use, risk, permissions, duration, artifacts, and low-permission alternatives.
- Redact sensitive command text in user-facing reports. Keep raw snapshot paths visible so the user can decide whether to delete them.
- Make decision ownership explicit: the agent explains evidence and tradeoffs; the user decides whether a specific PID should be stopped.

## Dangerous Action Gate

Treat these as dangerous actions: stopping any process, disabling or unloading startup/background items, changing services or scheduled tasks, editing registry/plists/configs, deleting files/caches, force-killing, Docker/VM/browser/IDE cleanup, and any deep forensic command that may require permissions or expose sensitive data.

Before any dangerous action:

1. Show the exact target, action, likely benefit, risk, and recovery path in Chinese.
2. Require explicit per-item confirmation. Accept only a message that names the action and concrete target, such as `确认停止 PID 12345`.
3. A broad phrase such as `清理吧`, `都处理`, `优化一下`, or `继续` is not enough. Ask again instead of acting.
4. If the process, port, service, or startup item changed since the report, re-audit before acting.
5. Never escalate from a failed gentle stop to force kill or config changes without a new explicit confirmation.

## Platform Selection

1. Detect the platform with `uname` on POSIX shells or `$PSVersionTable`/`$env:OS` on Windows.
2. On macOS, use `scripts/capture_macos_snapshot.sh --label before --out <work-dir>`.
3. On Windows, use PowerShell: `pwsh -NoProfile -File scripts/capture_windows_snapshot.ps1 -Label before -Out <work-dir>`.
4. Print the before report directly: `python3 scripts/compare_snapshots.py <before-summary.json>` on macOS/Linux shells, or `python scripts/compare_snapshots.py <before-summary.json>` where Python is available on Windows.
5. After any confirmed cleanup, capture `after` with the same platform script and compare before/after.

## Workflow

1. Inspect protected context first:
   - remote control, VPN/proxy, sync drives, meetings, downloads, Docker/VMs, IDEs, browsers, Codex/Claude, Chrome/Edge, ToDesk, Clash/Surge, enterprise agents, current local services.
   - Mark risky items; do not stop them.
2. Capture before.
3. Explain in Chinese before deciding:
   - CPU: who is computing and whether it can cause heat.
   - Memory: normal cache, compression, swap pressure, pageouts, or one large process.
   - Disk: space and aggregate I/O only by default.
   - Network: listeners and adapter overview only by default.
   - Startup/background: read-only summary only by default.
4. Build the decision list:
   - keep/protected
   - observe only
   - confirm before cleanup
   - deep forensic option, user-confirmed only
5. For every cleanup candidate, explain in plain language:
   - what is consuming CPU, memory, disk, network, or local ports
   - why it is suspicious
   - what the likely benefit would be if it is truly unused
   - what could break if it is stopped
   - how to recover or restart it
6. If the user explicitly confirms a specific PID and action, record a cleanup ledger:

```json
[
  {
    "pid": 12345,
    "process": "node",
    "command": "node server.js",
    "reason": "confirmed unused dev server on localhost:3000",
    "signal": "TERM",
    "result": "exited",
    "recovery": "rerun npm run dev in the project directory"
  }
]
```

7. Capture after and compare. If there was no cleanup ledger, explicitly say this was only a retest and any small movement may be natural fluctuation.
8. Confirm no temporary helper processes remain, then list snapshot/log artifacts and ask whether to delete them.

## Low-Permission Detection Upgrades

- Correlate local listeners with PIDs and commands. A port is not a cleanup target by itself; it is evidence.
- Use process age, PPID, command grouping, dev keywords, listener ownership, and protected keywords to score candidates.
- Prefer confirmation candidates over automatic cleanup. A higher score means "ask the user", not "kill now".
- Do not claim optimization unless a cleanup ledger or user action explains the before/after change.

## Bundled Resources

- `scripts/capture_macos_snapshot.sh`: read-only macOS snapshot collector.
- `scripts/capture_windows_snapshot.ps1`: read-only Windows snapshot collector.
- `scripts/normalize_snapshot.py`: schema sanity check and normalization helper.
- `scripts/compare_snapshots.py`: Chinese before-only and before/after report generator.
- `references/report-template.zh.md`: required report shape.
- `references/deep-forensics-macos.md`: macOS opt-in deep forensics menu.
- `references/deep-forensics-windows.md`: Windows opt-in deep forensics menu.
- `references/platform-mapping.md`: Mac/Windows signal mapping and safety levels.
