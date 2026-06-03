# macOS 深度取证菜单

默认不执行这里的任何项目。只有用户明确确认后才能运行，并且要先说明用途、风险、权限、耗时、临时产物和低权限替代方案。

| 工具/区域 | 用途 | 风险 | 权限/打扰 | 低权限替代 |
|---|---|---|---|---|
| `powermetrics` | 能耗和热源精查 | 常需 `sudo`，暴露硬件和功耗细节 | 高 | CPU 持续占用、thermal sysctl、`pmset` |
| `fs_usage` / DTrace | 进程级磁盘 I/O | 输出大，路径敏感，可能影响性能 | 高 | `df`、`iostat`、swap/pageout 趋势 |
| 深度 `nettop` | 进程级网络流量 | 可能暴露域名、端点、流量模式 | 中 | 监听端口、接口概览 |
| `sample` / `spindump` | 卡顿栈分析 | 调用栈、路径、符号敏感，可能需权限 | 中高 | Top CPU 趋势、用户手动 Activity Monitor 采样 |
| `sfltool` / 后台项数据库 | 登录/后台项深查 | 可能触发认证，暴露后台项清单 | 中高 | LaunchAgents、LaunchDaemons、brew services、人工设置页 |

禁止默认执行：`sudo`、`purge`、`kill -9`、`pkill`、`killall`、`launchctl unload/bootout/disable`、`mdutil -i off`、`brew services stop`、`docker stop/prune`。
