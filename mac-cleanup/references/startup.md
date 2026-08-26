# 启动项/后台服务 Playbook

触发：启动项、开机自启、后台服务残留、launchd、登录项、「有什么是不应该存在的」。

## 排查范围（全查一遍才算完整）

```bash
# 用户级 + 系统级 LaunchAgent/Daemon
ls ~/Library/LaunchAgents/ /Library/LaunchAgents/ /Library/LaunchDaemons/
# 逐个读 plist，看指向什么程序
for f in ~/Library/LaunchAgents/*.plist; do echo "== $f"; /usr/libexec/PlistBuddy -c 'Print :ProgramArguments' "$f" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Print :Program' "$f" 2>/dev/null; done

# 特权助手（常见卸载残留）
ls -la /Library/PrivilegedHelperTools/

# 登录项（BTM 后台任务管理，UUID 需展开看）
sfltool dumpbtm                                                    # 需 sudo，走交接；或用 osascript 查用户级
osascript -e 'tell application "System Events" to get the name of every login item'

# 定时任务
crontab -l
ls ~/Library/LaunchAgents/ | grep -v apple                        # cron 伪装成 agent 的也要看

# 内核扩展与音频驱动（删前预告副作用）
kmutil show                                                        # 或 kextstat
ls /Library/Audio/Plug-Ins/HAL/ /Library/Extensions/

# 浏览器/应用扩展注册与孤儿
ls ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/ 2>/dev/null
# App Support 孤儿：目录在但对应应用已卸载
```

## 残留判据（核心）

**启动项指向的程序文件是否还存在**。plist 里 Program/ProgramArguments 指向的二进制没了，只能说明它是残留候选；还要交叉验证对应应用是否仍在、最后使用时间、父应用是否卸载，以及外部个人档案里的历史决定，再请求用户确认。

## 执行顺序

1. 用户级（~/Library/LaunchAgents）：先 `launchctl bootout gui/$(id -u)/<label>` 卸载再删 plist；bootout 报错（如退出码 78）不阻塞，删文件后确认不再加载即可。
2. App Support 孤儿目录、偏好残留（`~/Library/Preferences/<bundleid>*`）：确认应用已卸载后直接删。
3. 系统级（/Library、PrivilegedHelperTools、kext、HAL、cron root）：全部汇总进 sudo 交接脚本。

## sudo 交接脚本模板

```bash
cat > ~/cleanup-sudo.sh <<'EOF'
#!/bin/bash
set -x
# 每条命令前用注释写明"这是什么、为什么删"
launchctl bootout system/<label> 2>/dev/null
rm -f /Library/LaunchDaemons/<xxx>.plist
rm -rf "/Library/PrivilegedHelperTools/<xxx>"
EOF
```

告诉用户：`sudo bash ~/cleanup-sudo.sh` 跑完把输出尾部贴回来。**用户可能裸跑**（不带 sudo 会卡在 override 提示），预先在交付说明里写清楚。

## 副作用预告（删前必须说）

- 删 HAL 音频驱动 → coreaudiod 自动重启，**声音会闪断一下**。
- 删银行 U 盾/网银控件 → 下次网银要用得去官网重装。
- 删 kext → 涉及对应硬件/文件系统（NTFS/RAID）功能失效。
- 删输入法 → 退出后输入法切换列表里消失。

## 已确认保留（对照个人档案）

个人档案中已确认保留的启动项不重复提议删除；若二进制、签名、父应用或使用状态已经变化，先报告变化，再由用户重新判断。

## 收尾

`launchctl list | grep <label>` 确认卸载；建议重启一次清掉 defunct 僵尸和旧注册项；把新发现的保留/删除写回档案。
