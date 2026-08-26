#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path


PROTECTED_KEYWORDS = (
    "chrome", "safari", "firefox", "edge", "browser", "codex.app", "codex",
    "claude", "todesk", "clash", "surge", "vpn", "dropbox", "onedrive",
    "google drive", "docker", "cursor", "visual studio code", "code helper",
    "webstorm", "idea", "zoom", "teams", "feishu", "lark", "wechat",
    "企业微信", "input", "ime", "security", "defender", "sentinel", "falcon",
    "rapportd", "sharingd", "bluetoothd", "mdnsresponder", "configd",
    "airportd", "systemuiserver", "controlcenter", "loginwindow",
    "trae", "kimi", "kimi-webbridge", "ghostty", "terminal", "iterm",
    "finder", "spotlight", "notificationcenter", "corespotlightd",
    "suggestd", "duetexpertd", "applespell", "webkit",
)

SYSTEM_BURST_KEYWORDS = (
    "syspolicyd", "trustd", "mds", "mdworker", "mds_stores", "windowserver",
    "kernel_task", "metadata.framework", "system idle process", "system",
    "registry", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "launchd", "notifyd", "distnoted",
)

DEV_KEYWORDS = (
    "node", "python", "java", "bun", "deno", "vite", "next", "webpack",
    "playwright", "mcp", "node_repl", "http-server", "localhost",
)

COMMON_DEV_PORTS = {
    3000, 3001, 3002, 3003, 4000, 4173, 4321, 5000, 5173, 5174, 6006,
    7000, 8000, 8080, 8787, 9000,
}


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def get(data, path, default=None):
    cur = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def first_value(data, paths, default=None):
    for path in paths:
        value = get(data, path)
        if value is not None:
            return value
    return default


def fmt(value, suffix=""):
    if value is None:
        return "不可用"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def delta(after, before, suffix=""):
    if after is None or before is None:
        return "不可用"
    try:
        value = after - before
    except TypeError:
        return "不可用"
    sign = "+" if value > 0 else ""
    if isinstance(value, float):
        return f"{sign}{value:.1f}{suffix}"
    return f"{sign}{value}{suffix}"


def md_table(rows):
    if not rows or len(rows) == 1:
        return "暂无。"
    header = rows[0]
    out = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def redact(text):
    text = " ".join(str(text or "").split())
    text = re.sub(r"/Users/[^/\s]+", "~", text)
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", r"%USERPROFILE%", text)
    text = re.sub(r"(?i)(token|access_token|api[_-]?key|secret|password|passwd|pwd)=([^\s&]+)", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(--?(?:token|api-key|password|secret)\s+)(\S+)", r"\1<redacted>", text)
    text = re.sub(r"(https?://[^?\s]+)\?([^\s]+)", r"\1?<redacted>", text)
    return text


def truncate(text, width=96):
    text = redact(text)
    if len(text) <= width:
        return text
    return text[: width - 1] + "..."


def command_text(proc):
    return str(proc.get("command") or proc.get("CommandLine") or proc.get("name") or "")


def proc_name(proc):
    name = proc.get("name") or proc.get("process")
    if name:
        return str(name)
    cmd = command_text(proc)
    parts = cmd.split()
    return Path(parts[0]).name if parts else "未知进程"


def text_has(text, keywords):
    low = str(text or "").lower()
    return any(key in low for key in keywords)


def is_protected(proc):
    cmd = command_text(proc)
    return bool(proc.get("is_protected_like")) or text_has(cmd, PROTECTED_KEYWORDS)


def is_system_burst(proc):
    return text_has(command_text(proc) or proc_name(proc), SYSTEM_BURST_KEYWORDS)


def is_dev_like(proc):
    cmd = command_text(proc)
    return bool(proc.get("is_dev_like")) or text_has(cmd, DEV_KEYWORDS)


def processes(snapshot, key):
    return get(snapshot, f"processes.{key}") or snapshot.get(key) or []


def all_candidate_processes(snapshot):
    seen = {}
    for group in ("top_cpu", "top_memory", "key_processes", "all_sample"):
        for proc in processes(snapshot, group):
            if isinstance(proc, dict) and proc.get("pid") is not None:
                seen[int(proc["pid"])] = proc
    return list(seen.values())


def listeners(snapshot):
    return get(snapshot, "listeners.tcp") or get(snapshot, "listeners.tcp_sample") or []


def listeners_by_pid(snapshot):
    by_pid = {}
    for item in listeners(snapshot):
        if not isinstance(item, dict):
            continue
        pid = item.get("pid")
        if pid is None:
            continue
        by_pid.setdefault(int(pid), []).append(item)
    return by_pid


def command_key(proc):
    return redact(command_text(proc))[:140]


def cleanup_candidates(snapshot):
    listener_map = listeners_by_pid(snapshot)
    procs = all_candidate_processes(snapshot)
    protected_parent_pids = {
        int(proc["pid"]) for proc in procs
        if proc.get("pid") is not None and (is_protected(proc) or is_system_burst(proc))
    }
    command_counts = Counter(command_key(proc) for proc in procs if command_key(proc))
    keep = []
    observe = []
    confirm = []

    for proc in sorted(procs, key=lambda p: (p.get("rss_mib") or 0, p.get("cpu_percent") or 0), reverse=True):
        pid = proc.get("pid")
        ports = sorted({item.get("port") for item in listener_map.get(int(pid), []) if item.get("port")})
        score = 0
        reasons = []
        risk = "低风险候选也可能打断临时任务；确认前请看端口和名称。恢复方式：重开应用或重新运行对应命令。回复“清理低风险项”才会尝试温和停止。"

        if is_system_burst(proc):
            keep.append((proc, "系统/安全/索引类进程；高占用通常应观察，不强杀。", "收益很小，风险高；不要处理。", ports))
            continue
        if is_protected(proc):
            keep.append((proc, "保护类进程或当前工作工具；可能影响连接、输入、同步或开发。", "保留它的收益是保护当前工作稳定；默认不处理。", ports))
            continue
        if proc.get("ppid") in protected_parent_pids:
            keep.append((proc, "保护类工具的子进程；通常属于当前浏览器、IDE、Codex/Claude、远控或同步工作链路。", "保留可避免打断当前工作；默认不处理。", ports))
            continue

        if is_dev_like(proc):
            score += 2
            reasons.append("开发/AI 辅助关键词")
        if ports:
            score += 2
            if any(port in COMMON_DEV_PORTS for port in ports):
                score += 1
                reasons.append(f"监听常见 dev 端口 {','.join(str(p) for p in ports[:6])}")
            else:
                reasons.append(f"监听本地端口 {','.join(str(p) for p in ports[:6])}")
        etime_seconds = proc.get("etime_seconds")
        age_is_relevant = is_dev_like(proc) or bool(ports) or (proc.get("rss_mib") or 0) >= 1024 or (proc.get("cpu_percent") or 0) >= 20
        if age_is_relevant and isinstance(etime_seconds, (int, float)) and etime_seconds >= 24 * 3600:
            score += 2
            reasons.append("运行超过 24 小时")
        elif age_is_relevant and isinstance(etime_seconds, (int, float)) and etime_seconds >= 4 * 3600:
            score += 1
            reasons.append("运行超过 4 小时")
        if proc.get("ppid") in (0, 1) and is_dev_like(proc):
            score += 1
            reasons.append("疑似孤儿用户态开发进程")
        if proc.get("command_scope") not in ("executable_only_default", "process_name_only_default") and command_counts.get(command_key(proc), 0) > 1 and is_dev_like(proc):
            score += 1
            reasons.append("命令重复")
        if (proc.get("rss_mib") or 0) >= 1024 or (proc.get("cpu_percent") or 0) >= 20:
            score += 1
            reasons.append("资源占用偏高")

        if score >= 3:
            confirm.append((proc, "、".join(reasons) or "归属需确认", risk, ports))
        elif reasons:
            observe.append((proc, "、".join(reasons), "先观察；证据不足以建议停止。", ports))

    return keep[:15], observe[:15], confirm[:20]


def proc_rows(items, limit=10):
    rows = [["PID", "CPU/时间", "内存", "运行时长", "说明"]]
    for proc in (items or [])[:limit]:
        cpu = proc.get("cpu_percent")
        if cpu is None:
            cpu = proc.get("cpu_time_seconds")
            cpu_text = fmt(cpu, "s")
        else:
            cpu_text = fmt(cpu, "%")
        rows.append([
            proc.get("pid", ""),
            cpu_text,
            fmt(proc.get("rss_mib"), " MiB"),
            proc.get("etime") or seconds_to_text(proc.get("etime_seconds")),
            truncate(command_text(proc)),
        ])
    return rows


def seconds_to_text(value):
    if not isinstance(value, (int, float)):
        return "不可用"
    value = int(value)
    days, rem = divmod(value, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def candidate_rows(items):
    rows = [["PID", "对象", "端口/时长/父进程", "为什么关注", "可能收益", "风险和恢复"]]
    for proc, reason, risk, ports in items:
        rows.append([
            proc.get("pid", ""),
            truncate(proc_name(proc), 32),
            candidate_context(proc, ports),
            truncate(reason, 54),
            truncate(benefit_text(proc, ports, reason), 54),
            truncate(risk, 70),
        ])
    return rows


def candidate_context(proc, ports):
    parts = []
    if ports:
        parts.append("端口 " + ",".join(str(port) for port in ports[:8]))
    age = proc.get("etime") or seconds_to_text(proc.get("etime_seconds"))
    if age and age != "不可用":
        parts.append(f"已运行 {age}")
    if proc.get("ppid") is not None:
        parts.append(f"父进程 {proc.get('ppid')}")
    return "；".join(parts)


def benefit_text(proc, ports, reason):
    if is_system_burst(proc):
        return "保留可避免干扰系统索引、安全校验或核心服务"
    if is_protected(proc):
        return "保留可避免打断当前工作、网络、同步、输入或开发"
    benefits = []
    rss = proc.get("rss_mib")
    cpu = proc.get("cpu_percent")
    if isinstance(rss, (int, float)) and rss >= 256:
        benefits.append(f"可能释放约 {rss:.0f} MiB 内存")
    if isinstance(cpu, (int, float)) and cpu >= 5:
        benefits.append("可能降低持续 CPU 和发热")
    if ports:
        benefits.append("可能关闭无用本地端口")
    if "命令重复" in reason:
        benefits.append("可能减少重复后台开发工具")
    if "运行超过" in reason:
        benefits.append("可能清掉长时间残留任务")
    if not benefits:
        benefits.append("收益不确定，建议先确认用途")
    return "；".join(benefits)


def metric_rows(before, after=None):
    metrics = [
        ("平台", "platform", ""),
        ("Memory free %", "memory.memory_pressure.free_percent", "%"),
        ("可用内存估算", "memory.pressure_available_mib", " MiB"),
        ("PhysMem/free", "memory.physmem_unused_mib", " MiB"),
        ("VM free/speculative", "memory.vm_free_speculative_mib", " MiB"),
        ("压缩内存 occupied", "memory.compressed_occupied_mib", " MiB"),
        ("Swap used", "memory.swapusage.used_mib", " MiB"),
        ("Pageins", "memory.pageins", ""),
        ("Pageouts", "memory.pageouts", ""),
        ("Swapins", "memory.swapins", ""),
        ("Swapouts", "memory.swapouts", ""),
        ("CPU idle", "cpu.idle_percent", "%"),
        ("CPU user", "cpu.user_percent", "%"),
        ("CPU system", "cpu.system_percent", "%"),
        ("根/系统盘可用", "disk.root.available_mib", " MiB"),
        ("数据盘可用", "disk.data.available_mib", " MiB"),
        ("TCP listeners", "listeners.tcp_count", ""),
        ("启动/后台摘要数", "startup.launch_plist_count", ""),
    ]
    if after is None:
        rows = [["指标", "当前值", "怎么理解"]]
        for label, path, suffix in metrics:
            value = first_value(before, [path, path.replace("disk.root.", "disk.")])
            rows.append([label, fmt(value, suffix), metric_hint(label)])
        return rows

    rows = [["指标", "Before", "After", "变化"]]
    for label, path, suffix in metrics:
        before_value = first_value(before, [path, path.replace("disk.root.", "disk.")])
        after_value = first_value(after, [path, path.replace("disk.root.", "disk.")])
        rows.append([label, fmt(before_value, suffix), fmt(after_value, suffix), delta(after_value, before_value, suffix)])
    return rows


def metric_hint(label):
    hints = {
        "Memory free %": "越低越紧；需结合压缩、swap 和 pageout。",
        "可用内存估算": "不同平台口径不同，只做趋势参考。",
        "压缩内存 occupied": "macOS 压缩偏高说明系统在挤内存；Windows 可能不可用。",
        "Swap used": "是否继续增长比单点值更重要。",
        "CPU idle": "低且持续会带来发热和响应变慢。",
        "根/系统盘可用": "空间不足会拖慢缓存、swap 和构建。",
        "TCP listeners": "端口不等于可清理，需看 PID 和用途。",
        "启动/后台摘要数": "只审计，不禁用。",
    }
    return hints.get(label, "低权限快照指标，需结合上下文。")


def explain_state(snapshot):
    lines = []
    platform = snapshot.get("platform", "unknown")
    lines.append(f"当前平台：{platform}；默认未做深度取证，结论基于低权限快照。")
    cpu_idle = get(snapshot, "cpu.idle_percent")
    if cpu_idle is not None and cpu_idle < 50:
        lines.append("CPU 空闲偏低；如果持续这样，卡顿和发热主要来自持续计算。")
    elif cpu_idle is not None:
        lines.append("CPU 当前还有余量；若仍发热，要看是否有短时高峰或后台校验。")
    free_percent = get(snapshot, "memory.memory_pressure.free_percent")
    if free_percent is not None and free_percent < 25:
        lines.append("内存余量偏紧，需要优先看浏览器/Electron/IDE/开发服务里的大户。")
    elif free_percent is not None:
        lines.append("内存余量暂未到红线；缓存本身不是问题，swap/pageout 是否增长更关键。")
    compressed = get(snapshot, "memory.compressed_occupied_mib")
    if compressed is not None and compressed > 4096:
        lines.append("压缩内存较高，说明系统正在挤内存；如果伴随 swap/pageout 增长才会明显拖慢。")
    swap_used = get(snapshot, "memory.swapusage.used_mib")
    if swap_used is not None and swap_used > 0:
        lines.append("swap 已存在；单点不等于恶化，before/after 是否继续增长更重要。")
    root_avail = get(snapshot, "disk.root.available_mib")
    if root_avail is not None and root_avail < 10240:
        lines.append("系统盘可用空间偏低，可能影响缓存、swap 和构建任务。")
    listener_count = get(snapshot, "listeners.tcp_count")
    if listener_count:
        lines.append(f"当前有 {listener_count} 个 TCP listener；这只是服务存在证据，不代表都能停。")
    top_cpu = processes(snapshot, "top_cpu")
    top_mem = processes(snapshot, "top_memory")
    if top_cpu:
        first = top_cpu[0]
        lines.append(f"CPU/CPU 时间第一占用：{proc_name(first)}，{truncate(command_text(first), 64)}。")
    if top_mem:
        first = top_mem[0]
        lines.append(f"内存第一占用：{proc_name(first)}，RSS {fmt(first.get('rss_mib'), ' MiB')}。")
    return lines


def cleanup_rows(cleanup_log):
    rows = [["PID", "进程", "动作", "原因", "结果", "恢复方式"]]
    for item in cleanup_log:
        rows.append([
            item.get("pid", ""),
            truncate(item.get("process") or item.get("command") or "", 36),
            item.get("signal") or item.get("action") or "",
            truncate(item.get("reason", ""), 42),
            item.get("result", ""),
            truncate(item.get("restart") or item.get("recovery") or "未知", 42),
        ])
    return rows


def load_cleanup_log(path):
    if not path:
        return []
    data = load_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "cleanup", "actions", "entries"):
            if isinstance(data.get(key), list):
                return data[key]
    raise SystemExit("cleanup log must be a JSON list or an object with items/cleanup/actions/entries")


def pid_set(snapshot):
    return {int(proc["pid"]) for proc in all_candidate_processes(snapshot) if proc.get("pid") is not None}


def port_set(snapshot):
    return {int(item["port"]) for item in listeners(snapshot) if isinstance(item, dict) and item.get("port") is not None}


def after_notes(before, after, cleanup_log):
    notes = []
    if cleanup_log:
        notes.append(f"本轮记录了 {len(cleanup_log)} 个清理动作，before/after 可以用来判断这些动作影响。")
    else:
        notes.append("本轮没有清理账本记录，只能算复测；指标变化可能来自自然波动，不能宣称明显优化。")
    pressure_delta = (get(after, "memory.memory_pressure.free_percent") or 0) - (get(before, "memory.memory_pressure.free_percent") or 0)
    cpu_delta = (get(after, "cpu.idle_percent") or 0) - (get(before, "cpu.idle_percent") or 0)
    swap_delta = (get(after, "memory.swapusage.used_mib") or 0) - (get(before, "memory.swapusage.used_mib") or 0)
    if abs(pressure_delta) <= 2 and abs(cpu_delta) <= 3 and abs(swap_delta) < 64:
        notes.append("关键指标变化较小，更像正常波动；真正有效的优化通常应看到明确进程/端口消失或 swap/pageout 增长停止。")
    if swap_delta == 0:
        notes.append("swap 在复测窗口内没有继续增长。")
    elif swap_delta > 0:
        notes.append("swap 继续增长，内存压力仍可能恶化。")
    disappeared_ports = sorted(port_set(before) - port_set(after))
    if disappeared_ports:
        notes.append(f"消失的监听端口：{','.join(str(p) for p in disappeared_ports[:12])}。")
    return notes


def render_report(before, after=None, cleanup_log=None):
    cleanup_log = cleanup_log or []
    lines = []
    if after is None:
        keep, observe, confirm = cleanup_candidates(before)
        lines.append("# 系统性能诊断报告（before）")
        lines.append("")
        lines.append("一句话结论：当前只做低权限诊断和决策建议；未清理任何进程，不能宣称已经优化。")
        lines.append("怎么决定：最简单是回复“清理低风险项”或“只观察”。高风险项不会混进低风险批量清理。")
        lines.append("安全门槛：低风险项可批量确认；启动项、深度取证、删除、强杀、Docker/浏览器/IDE/业务服务等仍需单独确认。")
        lines.append("隐私边界：默认不采集完整进程参数，只用进程名/PID/父进程/运行时长/端口/CPU/内存判断；完整命令行需要单独确认。")
        lines.append("")
        lines.append("## 为什么可能卡、热、占用高")
        for item in explain_state(before):
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## 建议清理（低风险，确认后批量处理）")
        lines.append(md_table(candidate_rows(confirm)))
        lines.append("")
        lines.append("可选动作：回复 `清理低风险项`，只会温和停止上表列出的低风险 PID；回复 `只观察`，则不做任何清理。")
        lines.append("")
        lines.append("## 只观察（更安全）")
        lines.append(md_table(candidate_rows(observe)))
        lines.append("")
        lines.append("## 不处理 / 保留（保护当前工作）")
        lines.append(md_table(candidate_rows(keep)))
        lines.append("")
        lines.append("## 关键指标")
        lines.append(md_table(metric_rows(before)))
        lines.append("")
        lines.append("## Top CPU / CPU 时间")
        lines.append(md_table(proc_rows(processes(before, "top_cpu"))))
        lines.append("")
        lines.append("## Top 内存")
        lines.append(md_table(proc_rows(processes(before, "top_memory"))))
        lines.append("")
        lines.append("## 安全边界")
        lines.append("- 默认未停止、未禁用、未删除、未修改配置。")
        lines.append("- 默认未采集完整进程参数，避免暴露 token、路径、URL 或业务参数。")
        lines.append("- 端口和开发关键词只是证据，不等于可以直接清理。")
        lines.append("- 收益只在候选确实无用时成立；不确定用途时宁可先保留。")
        lines.append("- 低风险用户态临时进程可以批量确认；禁用启动项、改服务/注册表/plist/config、删缓存、深度取证、强杀和高风险进程必须单独确认。")
        lines.append("- 深度取证未执行；如需执行，必须先说明用途、风险、权限、耗时、临时产物和替代方案。")
        lines.append("- macOS 调用栈取证要使用 `/usr/bin/sample` 和 `/usr/sbin/spindump`；裸 `sample` 可能被 Python/Homebrew 命令覆盖，报错时先解释 PATH 冲突。")
        lines.append("")
        lines.append("## 临时产物")
        lines.append(f"- Snapshot: `{before.get('snapshot_dir', '不可用')}`")
        return "\n".join(lines) + "\n"

    notes = after_notes(before, after, cleanup_log)
    keep, observe, confirm = cleanup_candidates(after)
    lines.append("# 系统性能复测报告（before/after）")
    lines.append("")
    lines.append(f"一句话结论：{notes[0]}")
    lines.append("怎么决定：复测结果只说明指标变化；后续可以回复“清理低风险项”或“只观察”。")
    lines.append("安全门槛：高风险、深度取证、启动项、服务、删除和强杀仍需单独确认。")
    lines.append("隐私边界：默认不采集完整进程参数；如果需要完整命令行排查同名服务，必须单独确认。")
    lines.append("macOS 取证提示：`sample/spindump` 属于深度取证；必须先做路径预检并使用系统绝对路径。")
    lines.append("")
    lines.append("## 这次有没有效果")
    for item in notes:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 已执行清理")
    lines.append(md_table(cleanup_rows(cleanup_log)) if cleanup_log else "无清理账本记录。")
    lines.append("")
    lines.append("## 关键指标对比")
    lines.append(md_table(metric_rows(before, after)))
    lines.append("")
    lines.append("## Top CPU Before")
    lines.append(md_table(proc_rows(processes(before, "top_cpu"))))
    lines.append("")
    lines.append("## Top CPU After")
    lines.append(md_table(proc_rows(processes(after, "top_cpu"))))
    lines.append("")
    lines.append("## Top 内存 Before")
    lines.append(md_table(proc_rows(processes(before, "top_memory"))))
    lines.append("")
    lines.append("## Top 内存 After")
    lines.append(md_table(proc_rows(processes(after, "top_memory"))))
    lines.append("")
    lines.append("## 复测后建议清理（低风险，确认后批量处理）")
    lines.append(md_table(candidate_rows(confirm)))
    lines.append("")
    lines.append("## 仍需保留/只观察")
    lines.append(md_table(candidate_rows(keep + observe)))
    lines.append("")
    lines.append("## 临时产物")
    lines.append(f"- Before snapshot: `{before.get('snapshot_dir', '不可用')}`")
    lines.append(f"- After snapshot: `{after.get('snapshot_dir', '不可用')}`")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Print a Chinese low-permission performance diagnosis/report.")
    parser.add_argument("before_summary", help="before summary.json")
    parser.add_argument("after_summary", nargs="?", help="optional after summary.json")
    parser.add_argument("--cleanup-log", help="optional cleanup ledger JSON")
    parser.add_argument("--out", help="optional Markdown report path; stdout is always printed")
    args = parser.parse_args()

    before = load_json(args.before_summary)
    after = load_json(args.after_summary) if args.after_summary else None
    cleanup_log = load_cleanup_log(args.cleanup_log)
    report = render_report(before, after, cleanup_log)
    print(report, end="")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\n[已写入报告] {out_path}")


if __name__ == "__main__":
    main()
