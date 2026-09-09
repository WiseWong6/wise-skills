# macOS 深度取证菜单

默认不执行这里的任何项目。只有用户明确确认后才能运行，并且要先说明用途、风险、权限、耗时、临时产物和低权限替代方案。

运行深度取证前必须先做命令路径预检。不要使用裸命令名；Python、Homebrew 或第三方工具可能在 `PATH` 里覆盖 macOS 原生工具。先用 `type -a <tool>` 或 `command -v <tool>` 解释是否存在阴影，再使用下表的系统绝对路径。

| 工具/区域 | 用途 | 风险 | 权限/打扰 | 低权限替代 |
|---|---|---|---|---|
| `/usr/bin/powermetrics` | 能耗和热源精查 | 常需 `sudo`，暴露硬件和功耗细节 | 高 | CPU 持续占用、thermal sysctl、`pmset` |
| `/usr/bin/fs_usage` / DTrace | 进程级磁盘 I/O | 输出大，路径敏感，可能影响性能 | 高 | `df`、`iostat`、swap/pageout 趋势 |
| 深度 `/usr/bin/nettop` | 进程级网络流量 | 可能暴露域名、端点、流量模式 | 中 | 监听端口、接口概览 |
| `/usr/bin/sample` / `/usr/sbin/spindump` | 卡顿栈分析 | 调用栈、路径、符号敏感，可能需权限 | 中高 | Top CPU 趋势、用户手动 Activity Monitor 采样 |
| `/usr/bin/sfltool` / 后台项数据库 | 登录/后台项深查 | 可能触发认证，暴露后台项清单 | 中高 | LaunchAgents、LaunchDaemons、brew services、人工设置页 |
| 完整进程命令行 | 区分同名 dev server、MCP 或脚本任务 | 可能暴露 token、账号、路径、URL、业务参数 | 中 | 默认只看进程名、PID、PPID、运行时长和端口 |

禁止默认执行：`sudo`、`purge`、`kill -9`、`pkill`、`killall`、`launchctl unload/bootout/disable`、`mdutil -i off`、`brew services stop`、`docker stop/prune`。

如果 `sample` 失败并出现 Python `ModuleNotFoundError` 之类报错，优先判断为 `PATH` 阴影，例如 Python 的 `sample` 抢在 `/usr/bin/sample` 前面。不要说 macOS 原生 `sample` 坏了；改为说明冲突，并在用户确认后使用 `/usr/bin/sample`。
