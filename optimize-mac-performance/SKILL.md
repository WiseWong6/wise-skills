---
name: optimize-mac-performance
description: Compatibility entry for Mac performance diagnosis. Use when the user asks to diagnose or safely optimize a Mac's memory pressure, CPU load, heat, responsiveness, background stability, local dev servers, or startup items. Prefer the cross-platform optimize-system-performance workflow when available; never use sudo, reboot, delete configs, disable startup items, or stop protected work processes by default.
---

# Optimize Mac Performance

This is a compatibility entry. Prefer `optimize-system-performance` when it is installed; it has the newer low-permission correlation logic for process age, PPID, local listeners, dev-server detection, protected-process handling, and Chinese before/after reporting.

## Default Path

Use the cross-platform Skill resources from the adjacent folder:

- Before: `../optimize-system-performance/scripts/capture_macos_snapshot.sh --label before --out <work-dir>`
- Report: `python3 ../optimize-system-performance/scripts/compare_snapshots.py <before-summary.json>`
- After: `../optimize-system-performance/scripts/capture_macos_snapshot.sh --label after --out <same-work-dir>`
- Compare: `python3 ../optimize-system-performance/scripts/compare_snapshots.py <before-summary.json> <after-summary.json> [--cleanup-log <cleanup.json>]`

If the cross-platform folder is missing, stop and ask the user to install or restore `optimize-system-performance`. Do not fall back to legacy scripts, because older snapshots may capture more command-line detail than the current safety policy allows.

## Safety Rules

- Default mode is read-only diagnosis and user decision support.
- Do not use `sudo`, reboot, log out, run `purge`, clear system caches, delete configs, disable startup items, unload plists, call `sfltool`, or run deep forensics by default.
- Do not stop browser main processes, remote control, VPN/proxy, sync drives, input methods, security software, enterprise management, meeting software, IDEs, Docker/VMs, Codex/Claude sessions, or local business services unless the user confirms that specific high-risk target.
- Do not kill `mds`, `mds_stores`, `mdworker`, `syspolicyd`, `trustd`, `WindowServer`, or `kernel_task`.
- A listening port is evidence, not proof that a service is unused. Only propose cleanup after correlating PID, command, PPID, age, protected keywords, and user context.
- When cleanup is confirmed, use only `kill -TERM <pid>`. Do not escalate to `kill -9` without explicit confirmation.
- Treat startup changes, cache deletion, deep forensics, Docker/browser/IDE cleanup, and any config change as dangerous actions that require specific confirmation. Low-risk user-process cleanup can be batch-confirmed only after the report lists exact PIDs, with a simple phrase such as `清理低风险项`.
- Do not use legacy raw command-line capture by default. Full command-line inspection can expose secrets and requires a separate user confirmation.

## Report Contract

Always print the Chinese diagnosis directly:

- one-line conclusion
- why the Mac may be slow/hot
- top CPU and memory owners
- memory pressure, compression, swap, pageins/pageouts
- local listener-to-PID evidence
- startup/background audit summary
- protected items preserved
- low-risk cleanup choice, plus specific confirmation for high-risk targets
- after comparison and cleanup ledger when cleanup happened
- temporary snapshot artifacts and whether the user wants them deleted
