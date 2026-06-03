# Deep Forensics Menu

Default snapshots must stay low-permission. Do not run any item here unless the user explicitly confirms after you explain the use, risk, permissions, duration, artifacts, and low-permission alternative.

| Tool / Area | Use | Risk | Permission / Friction | Low-permission alternative |
|---|---|---|---|---|
| `powermetrics` | Energy and thermal source investigation | Usually needs `sudo`; can expose hardware/power details; may run for several seconds | High | CPU sustained load, `pmset`, thermal sysctl if available |
| `fs_usage` / DTrace-style tracing | Per-process disk I/O investigation | High-volume output, privacy-sensitive paths, may affect performance, often restricted | High | `df`, `iostat`, swap/pageout trends |
| Deep `nettop` sampling | Per-process network flow investigation | Output can expose domains, endpoints, and traffic patterns; parsing can be noisy | Medium | `netstat -ibn`, local listeners, aggregate interface counters |
| `sample` / `spindump` | Stuck app or UI hang stack analysis | Captures call stacks, paths, code symbols, and potentially sensitive context; may need permission | Medium to high | Top CPU trend, Activity Monitor manual sample after user consent |
| `sfltool` / background item database | Login/background item deep audit | May trigger authentication; can expose sensitive background item inventory | Medium to high | LaunchAgents, LaunchDaemons, brew services, manual System Settings review |
| AppleScript / GUI login-item scraping | GUI login item list | May trigger Automation/TCC prompts and disturb the user | Medium | Ask user to inspect System Settings > General > Login Items manually |

When presenting a deep forensic option, use this wording shape:

```text
用途：
风险：
是否需要权限/密码：
预计耗时：
会产生哪些临时文件：
低权限替代方案：
等待用户确认后才执行。
```
