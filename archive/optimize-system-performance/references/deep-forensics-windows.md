# Windows 深度取证菜单

默认不执行这里的任何项目。Windows 默认模式不得要求管理员 PowerShell。

| 工具/区域 | 用途 | 风险 | 权限/打扰 | 低权限替代 |
|---|---|---|---|---|
| WPR/WPA 或 ETW | CPU、磁盘、网络、UI 延迟追踪 | trace 大且敏感，分析成本高 | 中高/常需管理员 | `Get-Process`、聚合计数器、监听端口 |
| ProcDump / 进程 dump | 崩溃或卡死分析 | dump 含内存内容，极敏感且很大 | 高 | Top CPU/RSS 趋势、用户确认后单进程采样 |
| 事件日志深查 | 服务失败、崩溃、睡眠唤醒问题 | 含路径、账号、URL、设备标识 | 中 | 只读服务摘要和进程摘要 |
| 注册表启动项深查 | 隐藏启动项和策略项 | 注册表敏感；误改危险 | 中高 | 低敏启动项摘要、系统设置人工检查 |
| 服务/计划任务变更 | 停止后台服务或任务 | 可能破坏 VPN、同步、安全、企业管理 | 高 | 只读摘要，给建议不修改 |
| 完整进程命令行 | 区分同名 dev server、MCP 或脚本任务 | 可能暴露 token、账号、路径、URL、业务参数 | 中 | 默认只看进程名、PID、PPID、运行时长和端口 |

禁止默认执行：管理员 PowerShell、`taskkill /F`、`Stop-Service`、`Set-Service`、`sc config`、注册表写入、`schtasks /Change/Delete`、清事件日志、WPR/ETW、ProcDump、Defender/安全软件配置修改。
