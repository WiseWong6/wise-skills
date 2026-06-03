---
name: optimize-mac-performance
description: Diagnose and safely optimize a Mac's memory pressure, CPU load, heat, responsiveness, background stability, local dev servers, and startup items. Use when the user asks to reduce RAM/swap/CPU use, cool down a Mac, audit launch agents or login/background items, clean leftover Codex/MCP/browser automation/node_repl/dev-server processes, or produce before/after performance evidence without sudo, rebooting, deleting configs, disabling startup items, or killing protected system/critical work processes.
---

# Optimize Mac Performance

Use a diagnose-first workflow: capture a before baseline, explain the likely causes in plain Chinese, ask the user to decide on risky cleanup, make only minimal reversible cleanup, then capture an after baseline and compare. Never start by killing processes.

## Safety Rules

- Do not use `sudo`, reboot, log out, disable launch items, unload plists, delete configs, run `purge`, clear system caches, or kill system core processes.
- Do not stop the current browser main process, remote control, VPN/proxy, sync drive, input method, security software, enterprise management software, meeting software, IDE, Docker/VM, or local business service unless the user explicitly confirms.
- Do not kill `mds`, `mds_stores`, `mdworker`, `syspolicyd`, `trustd`, `WindowServer`, or `kernel_task`. Explain short high-CPU bursts from indexing/security checks instead.
- Do not call `sfltool`, `launchctl print`, AppleScript automation, or GUI login-item scraping by default. These are optional deep-audit steps only after the user confirms.
- Do not call deep forensic tools by default. Before `powermetrics`, `fs_usage`, DTrace-style tools, deep `nettop`, `sample`, `spindump`, or background-item database probes, read `references/deep-forensics.md` and explain use, risk, permissions, expected duration, artifacts, and low-permission alternatives.
- Before starting any long-running helper, check whether an equivalent process already exists. Prefer one-shot commands and bundled scripts.
- Keep a cleanup ledger of every process you actually stop, including PID, process, command, reason, signal, result, and recovery/restart path.

## Workflow

1. Inspect protected context before cleanup:
   - Look for remote control, VPN/proxy, sync drive, meetings, downloads, Docker/VM, IDEs, browsers, Codex, Chrome, ToDesk, Clash/Surge, enterprise management, local business services, and active dev servers.
   - Mark risky candidates; do not stop them.
2. Capture the before baseline with the bundled script:
   - `scripts/capture_snapshot.sh --label before --out <work-dir>`
   - Resolve `scripts/` relative to this skill directory. If the agent exposes a skill base path variable, use it; otherwise inspect the installed skill path.
3. Diagnose from the baseline:
   - Distinguish true memory shortage, normal file cache, high compression, growing swap, single-process leak, duplicate helper services, sustained CPU, CPU spikes, browser renderer CPU, Electron/IDE/Docker load, dev-server load, and macOS indexing/security bursts.
   - Cover the Activity Monitor-style dimensions at low permission: CPU, memory, energy/heat inference, disk overview, network overview, and startup/background audit.
   - Check top CPU, top memory, local listeners, disk space, overall disk I/O snapshot, network interface overview, LaunchAgents/LaunchDaemons, and brew services. Do not use high-permission background-item probes by default.
   - Print a Chinese before report directly to the user with `scripts/compare_snapshots.py <before-summary.json>`. Start with: one-line conclusion, why the Mac may be slow/hot, top occupiers, whether cleanup is recommended, and how to decide.
4. Let the user decide before cleanup:
   - Split candidates into: recommended immediate cleanup, confirm before cleanup, observe only, and do not touch.
   - For each candidate, explain why it is suspicious, impact scope, stop risk, and recovery path.
5. Clean only low-risk, clearly stale user processes:
   - Prefer stale Codex MCP, browser automation helpers, node_repl helpers, duplicate temporary MCP services, orphaned node/python/java/bun/deno processes, and confirmed-unused dev servers.
   - Use `kill -TERM <pid>` only after confirming the process is not protected and is not part of the user's current work.
   - Escalation such as `kill -9`, Docker/IDE/browser cleanup, or startup-item disablement requires explicit user confirmation.
   - Write cleanup actions as JSON when possible, then pass it as `--cleanup-log <cleanup.json>`.
6. Capture the after baseline:
   - `scripts/capture_snapshot.sh --label after --out <same-work-dir>`
7. Compare and report:
   - `scripts/compare_snapshots.py <before-summary.json> <after-summary.json> [--cleanup-log <cleanup.json>]`
   - The report prints Chinese content to stdout by default. Use `--out <report.md>` only when the user wants a saved file.
   - If no cleanup ledger exists, explicitly say this was only a retest and the metric movement may be normal fluctuation, not proven optimization.
   - Include CPU, memory, energy/heat inference, disk overview, network overview, startup-item audit, actual cleanup performed, protected services preserved, remaining risks, manual validation steps, and temporary artifact paths.

## Risk Classification

- **Keep**: current browser, remote control, VPN/proxy, sync drive, input method, security/enterprise software, meeting app, IDE, Docker/VM, current project services, business services.
- **Risk only**: any process that may affect remote access, network routing, syncing, downloads, meetings, current code work, or production/business traffic.
- **Low-risk cleanup**: clearly stale user-owned helper processes with no active window/task, duplicate MCP/browser automation/node_repl helpers, confirmed-unused dev servers, zombie/orphan user processes.
- **Needs confirmation**: startup item changes, Docker/VM/browser/IDE cleanup, `kill -9`, system settings, cache deletion, plist unload/disable/delete, anything with unclear ownership.

## Cleanup Ledger

When cleanup happens, record a JSON list like:

```json
[
  {
    "pid": 12345,
    "process": "node",
    "command": "node server.js",
    "reason": "confirmed unused dev server",
    "signal": "TERM",
    "result": "exited",
    "recovery": "rerun npm run dev in the project directory"
  }
]
```

## Bundled Resources

- `scripts/capture_snapshot.sh`: one-shot low-permission read-only snapshot collector. It writes raw command outputs and `summary.json` under the chosen output directory. It does not call `sfltool` by default.
- `scripts/compare_snapshots.py`: prints a Chinese before-only diagnosis or before/after report to stdout. `--out` is optional.
- `references/report-template.md`: Chinese report structure to follow when writing the final user-facing summary.
- `references/deep-forensics.md`: opt-in deep forensic menu. Read before proposing or running any high-risk diagnostic.
- `references/windows-performance-notes.md`: Windows comparison notes. Do not run Windows commands from this Mac skill.
