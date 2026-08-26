# 性能诊断 Playbook（吸收自 optimize-system-performance）

触发：机器慢、发热、卡、风扇狂转、负载高、「优化系统性能」。定位是"为什么慢"，不是"删什么"——诊断产出建议清单，清理动作转到其他领域执行。

## 原则

- **只诊断不动手**：本领域默认不关任何应用、不删任何东西。产出的是"谁在吃资源 + 要不要处理"的报告。
- **有证据再下结论**：用快照 before/after 对比说话，没有清理台账就不声称"优化了"。
- 性能问题的答案经常是磁盘满或残留进程——磁盘占用 90%+ 本身就是性能问题，诊断完转 disk.md / processes.md。

## 排查命令

```bash
# 负载与 CPU
uptime                                        # 1/5/15 分钟负载（>核数算高）
top -l 2 -o cpu -n 15 -stats pid,command,cpu,mem,state    # 第二个采样才准
ps aux | sort -nrk 3 | head -15               # CPU 前 15

# 内存
vm_stat                                       # 换入换出、压缩
sysctl vm.swapusage                           # swap used 高 = 内存真不够
memory_pressure                               # 一眼看出压力等级

# 磁盘与 I/O
df -h /
iotop                                         # 需 sudo，走交接

# 发热/降频
pmset -g thermlog                             # 若无输出 = 没有温度限速
powermetrics --samplers cpu -i 3000 -n 1      # 需 sudo，走交接

# 开机时长（长时间未重启本身是问题）
sysctl -n kern.boottime
```

## 快照对比（scripts/ 下的工具）

`<skill>` 是本技能根目录，用绝对路径执行：

```bash
<skill>/scripts/capture_macos_snapshot.sh --label before --out /tmp/perf-check
python3 <skill>/scripts/compare_snapshots.py /tmp/perf-check/before-summary.json
# 用户确认清理、执行完毕后：
<skill>/scripts/capture_macos_snapshot.sh --label after --out /tmp/perf-check
python3 <skill>/scripts/compare_snapshots.py /tmp/perf-check/before-summary.json /tmp/perf-check/after-summary.json
```

- 快照默认只记录进程名/PID/PPID/年龄/端口/CPU/内存，**不抓完整命令行**（可能暴露 token 和路径）。
- 没有清理动作就出 after 对比时，明确说明"波动可能是自然抖动"。

## PATH 遮蔽预检

跑 `sample`、`spindump` 等系统工具前先确认路径——Python/Homebrew 装的同名工具可能遮蔽 Apple 原版。优先用绝对路径 `/usr/bin/sample`、`/usr/sbin/spindump`。深度取证工具（spindump/fs_usage/sc_usage）都是 sudo 级，走交接且先说明用途、时长、产物。

## 保护进程（不纳入清理建议）

浏览器主进程、VPN/代理（Clash 系）、远控（ToDesk）、输入法、IDE、Docker/VM、进行中的 zcode/claude/codex 会话及其子进程、系统进程（WindowServer、coreaudiod 等只报告不处理）。

发现这些吃资源时：报告事实 + 解释为什么，处理方式留给用户（"要不要退出 Cursor 由你定"），不代做。

## 产出格式

按资源分节（CPU/内存/磁盘/开机时长），每项：谁、吃了多少、为什么可疑/正常、动了有什么收益、会弄坏什么、怎么恢复。最后给一句总判断（瓶颈在哪）。
