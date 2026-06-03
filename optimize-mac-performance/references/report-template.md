# Mac Performance Chinese Report Template

Start by explaining the problem to the user in plain Chinese. Do not make the user open a report file just to understand the result.

## Required Sections

- **一句话结论**：有没有实质清理，指标是否明显改善，是否只是自然波动。
- **为什么卡/热**：用 CPU、内存、压缩、swap、pageout、Top 进程解释原因。
- **活动监视器维度**：覆盖 CPU、内存、能耗/发热推断、磁盘总览、网络总览、启动项审计。
- **是否建议解决**：分为立即清理、确认后清理、只观察、不处理。
- **怎么解决**：说明每个候选的影响范围、停止风险和恢复方式。
- **Before/After 证据**：memory pressure、可用内存估算、压缩内存、swap、pageins/pageouts、CPU idle/user/system、load average、Top CPU、Top 内存、监听端口。
- **深度取证状态**：默认未做深度取证；如建议深度取证，说明用途、风险、权限、耗时、临时产物、低权限替代方案。
- **已执行清理**：只列实际动作。包含 PID、process、signal、reason、result、recovery。
- **保留关键服务**：浏览器、远控、VPN/代理、同步盘、会议、Docker/VM、IDE、Codex、Chrome、ToDesk、Clash/Surge、企业管理、本地业务服务。
- **启动项审计**：默认只看 LaunchAgents、LaunchDaemons、brew services、监听端口；不默认调用 sfltool。只给建议，不 disable/unload/delete。
- **人工验证**：Activity Monitor、响应速度、发热、启动项 UI、恢复步骤。
- **临时产物**：snapshot 路径；仅用户要求时保存 Markdown 报告。
