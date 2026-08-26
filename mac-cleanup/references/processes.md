# 进程/端口 Playbook

触发：kill 端口、杀进程、残留服务、「有什么垃圾进程隐藏在后台」。

## 盘点命令

```bash
# 只看当前用户的 TCP 监听（过滤系统进程和 UDP 噪音，不触发 sudo）
lsof -iTCP -sTCP:LISTEN -nP 2>/dev/null | awk -v user="$(id -un)" 'NR==1 || $3==user' | grep -v '^rapportd\|^ControlCe'
# 逐个查进程身份：启动了多久、完整命令、父进程是谁
ps -o pid,ppid,etime,command -p <PID>
```

AirPlay(5000/7000)、ControlCenter、mDNSResponder 等系统监听直接跳过不报。

## 孤儿判据（核心）

- **PPID=1** = 父进程已退出，典型残留（hyperframes preview、npm run dev 都这么判的）。
- 挂在**存活的 zcode/claude/codex 会话**下的 dev server / MCP 服务 = 可能正在用，列为"需确认"并说明挂在谁下面，不直接杀。
- 查启动时长（etime）：挂了一天以上的 preview 服务基本是残留。
- 重复监听同一端口的多个实例 = 之前端口占用导致重复启动，都可清。

## 执行规则

1. 先报清单（端口、进程、命令、跑了多久、孤儿/在用判定），等用户拍板。
2. 用户说 kill：先 `kill -TERM <PID>`；几秒后 `ps -p <PID>` 确认；忽略 TERM 的才升级 `kill -9`。
3. **只杀目标进程本身**，不追杀父会话；kill 一个 npm run dev 时连着它的 npm 父进程一起结束（同一个服务的进程组），但不动其上的 CLI 会话。
4. brew 服务优先 `brew services stop <name>` 优雅停（有时会因内部 bug 失败，失败再回退 kill）。

## 整套移除数据库/服务（用户点名删时）

例：PostgreSQL——先确认没有活动连接（`lsof -i :5432` / psql 查）、哪些项目配置指向它（grep 项目 .env）、然后问一句"要不要备份导出"（用户默认不要），再按顺序：停服务 → `brew uninstall` → 卸 launchd → 删 plist → 删数据目录。完成后明确告知"数据已不可恢复"。

## 高 CPU 进程

配合 perf-diagnosis.md：先报告是谁、为什么吃、杀了会坏什么。浏览器主进程、VPN、远控、输入法、IDE、活跃会话子进程一律只报告不代杀，用户点名才动。
