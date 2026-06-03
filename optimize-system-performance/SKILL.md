---
name: optimize-system-performance
description: Diagnose Mac or Windows CPU, memory, heat or energy symptoms, disk and network load, local dev servers, background stability, and startup items with low-permission before/after evidence. Use when the user wants to understand why a computer is slow, hot, swapping, or cluttered with background processes, and wants safe reversible cleanup recommendations without sudo/admin rights, rebooting, deleting configs, disabling startup items, or stopping protected work services.
---

# Optimize System Performance

Use a diagnose-first workflow. The default mode is read-only: capture a baseline, explain the causes in plain Chinese, show a short low-risk cleanup choice, then wait for the user before any cleanup. Treat this as a diagnosis and decision skill, not an automatic cleaner.

## Safety Rules

- Default actions must be L0/L1 only: low-permission sampling, Chinese explanation, and cleanup recommendations.
- Do not use `sudo`, elevated PowerShell, reboot, log out, clear caches, delete configs, disable startup items, unload plists, edit registry, change services, change scheduled tasks, or force-kill processes by default.
- Do not stop browser main processes, remote control, VPN/proxy, sync drives, input methods, security software, enterprise management, meeting software, IDEs, Docker/VMs, Codex/Claude sessions, or local business services unless the user confirms that specific high-risk target after seeing the risk.
- Batch cleanup is allowed only for the report's explicit low-risk cleanup list after the user confirms a simple choice such as `清理低风险项`. Never include protected, ambiguous, startup, service, Docker/VM/browser/IDE, or business-service targets in that batch.
- When cleanup is confirmed, use only gentle user-process termination: macOS `kill -TERM <pid>`; Windows `Stop-Process -Id <pid>` without `-Force`. If it fails, report it and stop.
- Deep forensics are opt-in only. Before any high-risk tool, read the relevant reference and explain use, risk, permissions, duration, artifacts, and low-permission alternatives.
- For macOS deep forensics, run a command-path preflight first. Prefer system absolute paths such as `/usr/bin/sample` and `/usr/sbin/spindump`; never assume a bare command is the Apple tool because Python, Homebrew, or third-party installs may shadow it in `PATH`.
- Default snapshots store executable/process names rather than full process arguments. Full command-line capture can expose tokens, paths, URLs, and business context, so treat it as opt-in deep inspection.
- Redact sensitive text in user-facing reports. Keep snapshot paths visible so the user can decide whether to delete them.
- Make decision ownership explicit but simple: the agent explains evidence and tradeoffs; the user can choose `清理低风险项` or `只观察`. High-risk targets still need specific confirmation.

## Dangerous Action Gate

Treat these as dangerous actions: stopping any process, disabling or unloading startup/background items, changing services or scheduled tasks, editing registry/plists/configs, deleting files/caches, force-killing, Docker/VM/browser/IDE cleanup, and any deep forensic command that may require permissions or expose sensitive data.

Before any dangerous action:

1. Show the target group, action, likely benefit, risk, and recovery path in Chinese.
2. For L2 low-risk cleanup, accept a clear batch confirmation such as `清理低风险项` only after the report lists the exact PIDs in that group.
3. For high-risk, ambiguous, protected, startup/service, Docker/VM/browser/IDE, deep forensic, deletion, config, registry/plist, or force-kill actions, require a specific target confirmation such as `确认停止 PID 12345`.
4. A vague phrase such as `优化一下`, `继续`, or `你决定` is not enough. Ask one short follow-up instead of acting.
5. If the process, port, service, or startup item changed since the report, re-audit before acting.
6. Never escalate from a failed gentle stop to force kill or config changes without a new explicit confirmation.
7. If a deep forensic command fails, check for `PATH` shadowing before blaming the OS tool. Explain the collision plainly and retry only with the verified absolute system path after confirmation.

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
   - Privacy: default process evidence uses executable/process names, PID, PPID, age, ports, CPU, and memory; do not collect full arguments unless the user confirms.
4. Build the decision list:
   - keep/protected
   - observe only
   - low-risk cleanup choice
   - high-risk or ambiguous targets, specific confirmation only
   - deep forensic option, user-confirmed only
5. For the low-risk cleanup list, explain in plain language:
   - what is consuming CPU, memory, disk, network, or local ports
   - why it is suspicious
   - what the likely benefit would be if it is truly unused
   - what could break if it is stopped
   - how to recover or restart it
6. If the user confirms `清理低风险项`, recheck that each listed PID still matches the report and is still unprotected, then gently stop only those listed PIDs. If the user confirms a high-risk specific PID and action, act only on that target. Record a cleanup ledger:

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

- Correlate local listeners with PIDs and executable/process names. A port is not a cleanup target by itself; it is evidence.
- Use process age, PPID, command grouping, dev keywords, listener ownership, and protected keywords to score candidates.
- Prefer confirmation candidates over automatic cleanup. A higher score means "ask the user", not "kill now".
- Do not claim optimization unless a cleanup ledger or user action explains the before/after change.

## Bundled Resources

- `scripts/capture_macos_snapshot.sh`: read-only macOS snapshot collector; default process data is executable-only.
- `scripts/capture_windows_snapshot.ps1`: read-only Windows snapshot collector; default process data is executable-only.
- `scripts/normalize_snapshot.py`: schema sanity check and normalization helper.
- `scripts/compare_snapshots.py`: Chinese before-only and before/after report generator.
- `references/report-template.zh.md`: required report shape.
- `references/deep-forensics-macos.md`: macOS opt-in deep forensics menu.
- `references/deep-forensics-windows.md`: Windows opt-in deep forensics menu.
- `references/platform-mapping.md`: Mac/Windows signal mapping and safety levels.
