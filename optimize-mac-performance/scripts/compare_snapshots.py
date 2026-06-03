#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


PROTECTED_KEYWORDS = (
    "Chrome", "Google Chrome", "Codex.app", "Codex", "ToDesk", "Clash", "Surge",
    "WeChat", "企业微信", "Feishu", "Lark", "Dropbox", "OneDrive", "Google Drive",
    "Docker", "Cursor", "Visual Studio Code", "Code Helper", "Trae", "Kimi Code",
    "Zoom", "Teams", "Mail.app", "DoubaoIme",
)

SYSTEM_BURST_KEYWORDS = (
    "syspolicyd", "trustd", "mds", "mdworker", "mds_stores", "WindowServer",
    "kernel_task", "Metadata.framework",
)

DEV_KEYWORDS = (
    "node", "python", "java", "bun", "deno", "vite", "next", "webpack",
    "playwright", "mcp", "node_repl", "browser automation",
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def get(data, path, default=None):
    cur = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def fmt(value, suffix=""):
    if value is None:
        return "不可用"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        text = f"{value:.1f}"
    else:
        text = str(value)
    return f"{text}{suffix}"


def delta(after, before, suffix=""):
    if after is None or before is None:
        return "不可用"
    value = after - before
    sign = "+" if value > 0 else ""
    if isinstance(value, float):
        return f"{sign}{value:.1f}{suffix}"
    return f"{sign}{value}{suffix}"


def md_table(rows):
    if not rows:
        return "_无数据_"
    header = rows[0]
    out = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def truncate(text, width=86):
    text = " ".join(str(text or "").split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "..."


def command_text(proc):
    return proc.get("command", "") if isinstance(proc, dict) else ""


def top_process_name(proc):
    cmd = command_text(proc)
    if not cmd:
        return "未知进程"
    parts = cmd.split()
    return Path(parts[0]).name if parts else truncate(cmd, 24)


def is_system_burst(proc):
    cmd = command_text(proc)
    return any(key.lower() in cmd.lower() for key in SYSTEM_BURST_KEYWORDS)


def is_protected(proc):
    cmd = command_text(proc)
    return any(key.lower() in cmd.lower() for key in PROTECTED_KEYWORDS)


def is_dev_candidate(proc):
    cmd = command_text(proc)
    return any(key.lower() in cmd.lower() for key in DEV_KEYWORDS)


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


def proc_rows(items, limit=10):
    rows = [["PID", "CPU%", "内存%", "RSS", "说明"]]
    for item in (items or [])[:limit]:
        rows.append([
            item.get("pid", ""),
            fmt(item.get("cpu_percent")),
            fmt(item.get("mem_percent")),
            fmt(item.get("rss_mib"), " MiB"),
            truncate(item.get("command")),
        ])
    return rows


def metric_rows(before, after=None):
    if after is None:
        return [
            ["指标", "当前值", "怎么理解"],
            ["Memory pressure free", fmt(get(before, "memory.memory_pressure.free_percent"), "%"), "macOS 还能调度的内存余量，越低越容易卡"],
            ["可用内存估算", fmt(get(before, "memory.pressure_available_mib"), " MiB"), "按 memory_pressure 百分比估算，不等同于 Activity Monitor 的全部缓存口径"],
            ["PhysMem unused", fmt(get(before, "memory.physmem_unused_mib"), " MiB"), "完全空闲内存；macOS 通常会把内存拿去做缓存，所以低不一定坏"],
            ["压缩内存 occupied", fmt(get(before, "memory.compressed_occupied_mib"), " MiB"), "压缩越高，说明系统在努力挤内存；持续高才值得处理"],
            ["Swap used", fmt(get(before, "memory.swapusage.used_mib"), " MiB"), "已经写到磁盘的内存；是否继续增长比单点值更重要"],
            ["CPU idle", fmt(get(before, "cpu.idle_percent"), "%"), "空闲越高越轻松；低且持续才会发热"],
            ["Load avg 1m", fmt((get(before, "cpu.load_average") or [None])[0]), "短时系统负载，需结合核心数和 Top CPU 看"],
            ["能耗/发热", "低权限推断", "默认只用 CPU 持续占用和 thermal/pmset 信息，不跑 powermetrics"],
            ["根分区可用空间", fmt(get(before, "disk.root_available_mib"), " MiB"), "磁盘空间不足会拖慢缓存、swap 和构建任务"],
            ["磁盘 I/O 快照", "已采集" if get(before, "disk.iostat_available") else "不可用", "默认只看总体 I/O，不追踪进程级磁盘读写"],
            ["网络接口概览", fmt(get(before, "network.interface_row_count")), "默认只看接口概览和监听端口，不做进程级流量深挖"],
            ["TCP listeners", fmt(get(before, "listeners.tcp_count")), "本地服务数量；不减少不代表失败，只说明没停服务"],
            ["Launch plist count", fmt(get(before, "startup.launch_plist_count")), "启动项 plist 数；默认只审计不禁用"],
        ]

    load_b = get(before, "cpu.load_average") or []
    load_a = get(after, "cpu.load_average") or []
    def load_at(load, index):
        return load[index] if isinstance(load, list) and len(load) > index else None

    metrics = [
        ("Memory pressure free", "memory.memory_pressure.free_percent", "%"),
        ("可用内存估算", "memory.pressure_available_mib", " MiB"),
        ("PhysMem unused", "memory.physmem_unused_mib", " MiB"),
        ("VM free+speculative", "memory.vm_free_speculative_mib", " MiB"),
        ("压缩内存 occupied", "memory.compressed_occupied_mib", " MiB"),
        ("压缩内存 stored", "memory.compressed_stored_mib", " MiB"),
        ("Swap used", "memory.swapusage.used_mib", " MiB"),
        ("Pageins", "memory.pageins", ""),
        ("Pageouts", "memory.pageouts", ""),
        ("Swapins", "memory.swapins", ""),
        ("Swapouts", "memory.swapouts", ""),
        ("CPU idle", "cpu.idle_percent", "%"),
        ("CPU user", "cpu.user_percent", "%"),
        ("CPU system", "cpu.system_percent", "%"),
        ("根分区可用空间", "disk.root_available_mib", " MiB"),
    ]
    rows = [["指标", "Before", "After", "变化"]]
    for label, path, suffix in metrics:
        b_val = get(before, path)
        a_val = get(after, path)
        rows.append([label, fmt(b_val, suffix), fmt(a_val, suffix), delta(a_val, b_val, suffix)])
    rows.extend([
        ["Load avg 1m", fmt(load_at(load_b, 0)), fmt(load_at(load_a, 0)), delta(load_at(load_a, 0), load_at(load_b, 0))],
        ["Load avg 5m", fmt(load_at(load_b, 1)), fmt(load_at(load_a, 1)), delta(load_at(load_a, 1), load_at(load_b, 1))],
        ["Load avg 15m", fmt(load_at(load_b, 2)), fmt(load_at(load_a, 2)), delta(load_at(load_a, 2), load_at(load_b, 2))],
        ["TCP listeners", fmt(get(before, "listeners.tcp_count")), fmt(get(after, "listeners.tcp_count")), delta(get(after, "listeners.tcp_count"), get(before, "listeners.tcp_count"))],
        ["Launch plist count", fmt(get(before, "startup.launch_plist_count")), fmt(get(after, "startup.launch_plist_count")), delta(get(after, "startup.launch_plist_count"), get(before, "startup.launch_plist_count"))],
        ["磁盘 I/O 快照", "已采集" if get(before, "disk.iostat_available") else "不可用", "已采集" if get(after, "disk.iostat_available") else "不可用", "总体 I/O，非进程级"],
        ["网络接口概览", fmt(get(before, "network.interface_row_count")), fmt(get(after, "network.interface_row_count")), "低权限概览，非进程级流量"],
    ])
    return rows


def cleanup_rows(cleanup_log):
    rows = [["PID", "进程", "动作", "原因", "结果", "恢复方式"]]
    for item in cleanup_log:
        rows.append([
            item.get("pid", ""),
            truncate(item.get("process") or item.get("command") or ""),
            item.get("signal") or item.get("action") or "",
            truncate(item.get("reason", ""), 42),
            item.get("result", ""),
            truncate(item.get("restart") or item.get("recovery") or "未知", 42),
        ])
    return rows


def classify_current_state(snapshot):
    top_cpu = snapshot.get("top_cpu") or []
    top_mem = snapshot.get("top_memory") or []
    pressure = get(snapshot, "memory.memory_pressure.free_percent")
    compressed = get(snapshot, "memory.compressed_occupied_mib")
    swap_used = get(snapshot, "memory.swapusage.used_mib")
    cpu_idle = get(snapshot, "cpu.idle_percent")

    lines = []
    if cpu_idle is not None and cpu_idle < 50:
        lines.append("CPU 空闲偏低，如果这个状态持续，发热和卡顿主要会来自持续计算。")
    elif cpu_idle is not None:
        lines.append("CPU 当前还有余量；如果仍然发热，要看 Top CPU 是否有短时系统校验或某个应用持续占用。")

    if pressure is not None and pressure < 25:
        lines.append("内存压力偏紧，需要优先找浏览器/Electron/IDE/开发服务里的大户。")
    elif pressure is not None:
        lines.append("内存压力不是红线；macOS 文件缓存本身不是问题，压缩和 swap 是否持续增长更关键。")

    if compressed is not None and compressed > 4096:
        lines.append("压缩内存较高，说明系统在挤内存；如果伴随 swap/pageout 增长，才会明显拖慢。")

    if swap_used is not None and swap_used > 0:
        lines.append("swap 已经存在，但单点不代表正在恶化；要对比 after 是否继续增长。")
    root_avail = get(snapshot, "disk.root_available_mib")
    if root_avail is not None and root_avail < 10240:
        lines.append("根分区可用空间偏低，可能影响 swap、缓存、构建和应用响应。")
    elif root_avail is not None:
        lines.append("磁盘空间当前不是第一风险；默认只看总体空间和 I/O，不做进程级磁盘取证。")
    if get(snapshot, "network.interface_row_count") is not None:
        lines.append("网络默认只看接口概览和本地监听端口，避免暴露连接明细和进程级流量。")

    if top_cpu:
        first = top_cpu[0]
        kind = "系统短时任务" if is_system_burst(first) else "应用/开发进程"
        lines.append(f"当前 CPU 第一占用是 {top_process_name(first)}（{fmt(first.get('cpu_percent'), '%')}），类型判断：{kind}。")
    if top_mem:
        first = top_mem[0]
        lines.append(f"当前内存第一占用是 {top_process_name(first)}（RSS {fmt(first.get('rss_mib'), ' MiB')}）。")
    return lines


def decision_lists(snapshot):
    immediate = []
    confirm = []
    observe = []
    keep = []

    for proc in snapshot.get("top_cpu", []) + snapshot.get("top_memory", []):
        cmd = command_text(proc)
        if not cmd:
            continue
        item = {
            "pid": proc.get("pid"),
            "name": top_process_name(proc),
            "cpu": proc.get("cpu_percent"),
            "rss": proc.get("rss_mib"),
            "reason": "",
            "risk": "",
            "recovery": "通常重新运行对应命令或重开应用即可恢复；不确定时先问用户。",
            "command": truncate(cmd, 120),
        }
        if is_system_burst(proc):
            item["reason"] = "macOS 系统索引/安全校验/窗口服务类进程，可能短时高 CPU。"
            item["risk"] = "不要强杀，观察即可。"
            keep.append(item)
        elif is_protected(proc):
            item["reason"] = "属于浏览器、远控、代理、输入法、IDE、企业通讯或当前工作工具。"
            item["risk"] = "可能影响当前工作、网络、远程连接或输入。"
            keep.append(item)
        elif is_dev_candidate(proc):
            item["reason"] = "疑似开发辅助进程或本地服务。"
            item["risk"] = "可能是当前项目需要的服务；需确认是否无用。"
            confirm.append(item)
        elif proc.get("cpu_percent", 0) >= 20 or proc.get("rss_mib", 0) >= 1024:
            item["reason"] = "资源占用较高，但归属不够明确。"
            item["risk"] = "需确认是否正在执行任务。"
            confirm.append(item)

    listener_count = get(snapshot, "listeners.tcp_count")
    if listener_count:
        observe.append({
            "name": "本地监听端口",
            "reason": f"当前有 {listener_count} 个 TCP listener；端口不减少不代表失败。",
            "risk": "只有确认无用 dev server 后才建议停止。",
            "recovery": "重启对应 dev server 或服务。",
        })
    observe.append({
        "name": "启动项审计",
        "reason": "默认只列 plist 和 brew services；不读取可能弹权限的登录项数据库。",
        "risk": "禁用启动项可能影响代理、同步盘、远控和企业管理。",
        "recovery": "系统设置 > 通用 > 登录项，或重新 load 对应服务。",
    })
    return immediate, confirm, observe, keep


def candidate_table(items):
    rows = [["对象", "为什么关注", "风险", "恢复方式"]]
    for item in items:
        rows.append([
            f"{item.get('name', '')} {('(PID ' + str(item.get('pid')) + ')') if item.get('pid') else ''}".strip(),
            truncate(item.get("reason", ""), 52),
            truncate(item.get("risk", ""), 44),
            truncate(item.get("recovery", ""), 44),
        ])
    return rows


def interpret_after(before, after, cleanup_log):
    notes = []
    if not cleanup_log:
        notes.append("本轮没有清理账本记录，只能算复测；指标变化可能来自自然波动，不能宣称明显优化。")
    else:
        notes.append(f"本轮记录了 {len(cleanup_log)} 个清理动作，下面的 before/after 才能用于判断这些动作的效果。")

    pressure_delta = (get(after, "memory.memory_pressure.free_percent") or 0) - (get(before, "memory.memory_pressure.free_percent") or 0)
    cpu_delta = (get(after, "cpu.idle_percent") or 0) - (get(before, "cpu.idle_percent") or 0)
    swap_delta = (get(after, "memory.swapusage.used_mib") or 0) - (get(before, "memory.swapusage.used_mib") or 0)
    compressed_delta = (get(after, "memory.compressed_occupied_mib") or 0) - (get(before, "memory.compressed_occupied_mib") or 0)

    if abs(pressure_delta) <= 2 and abs(cpu_delta) <= 3 and abs(swap_delta) < 64:
        notes.append("关键指标变化很小，更像正常波动；真正有效的优化通常应看到持续高占用进程消失或 swap/pageout 增长停止。")
    if compressed_delta < -256:
        notes.append("压缩内存下降较明显，这是好信号，但仍需看后续工作负载下是否保持。")
    if swap_delta == 0:
        notes.append("swap 没继续增长，说明这段复测窗口内没有新的明显磁盘换页压力。")
    elif swap_delta > 0:
        notes.append("swap 继续增长，说明内存压力仍在恶化，应继续找大内存进程。")

    return notes


def render_report(before, after=None, cleanup_log=None):
    cleanup_log = cleanup_log or []
    lines = []
    if after is None:
        lines.append("# Mac 性能诊断报告（before）")
        lines.append("")
        lines.append("一句话结论：先让用户理解占用来源，再决定要不要清理；当前报告只诊断，不代表已经优化。")
        lines.append("")
        lines.append("## 为什么可能卡、发热")
        for item in classify_current_state(before):
            lines.append(f"- {item}")
        lines.append("")
        immediate, confirm, observe, keep = decision_lists(before)
        lines.append("## 建议处理清单")
        lines.append("")
        lines.append("### 建议立即清理")
        lines.append(md_table(candidate_table(immediate)) if immediate else "暂无。")
        lines.append("")
        lines.append("### 建议确认后清理")
        lines.append(md_table(candidate_table(confirm)) if confirm else "暂无。")
        lines.append("")
        lines.append("### 只观察")
        lines.append(md_table(candidate_table(observe)) if observe else "暂无。")
        lines.append("")
        lines.append("### 不处理 / 保留")
        lines.append(md_table(candidate_table(keep[:10])) if keep else "暂无。")
        lines.append("")
        lines.append("## 关键指标")
        lines.append(md_table(metric_rows(before)))
        lines.append("")
        lines.append("## Top CPU")
        lines.append(md_table(proc_rows(before.get("top_cpu"))))
        lines.append("")
        lines.append("## Top 内存")
        lines.append(md_table(proc_rows(before.get("top_memory"))))
        lines.append("")
        lines.append("## 启动项审计口径")
        lines.append("- 默认只看 LaunchAgents、LaunchDaemons、brew services 和监听端口。")
        lines.append("- 不默认调用 `sfltool`，不读取可能触发权限弹窗的后台项数据库。")
        lines.append("- 启动项只给建议，不 unload/disable/delete。")
        lines.append("")
        lines.append("## 深度取证状态")
        lines.append("- 未做深度取证；本结论基于低权限快照。")
        lines.append("- 如需 powermetrics、fs_usage/DTrace、深度 nettop、sample/spindump 或后台项数据库，必须先说明用途、风险、权限、耗时、临时产物和低权限替代方案，再等用户确认。")
        return "\n".join(lines) + "\n"

    lines.append("# Mac 性能复测报告（before/after）")
    lines.append("")
    after_notes = interpret_after(before, after, cleanup_log)
    lines.append(f"一句话结论：{after_notes[0]}")
    lines.append("")
    lines.append("## 这次有没有效果")
    for item in after_notes:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 为什么卡、热、占用高")
    for item in classify_current_state(after):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 已执行清理")
    lines.append(md_table(cleanup_rows(cleanup_log)) if cleanup_log else "无清理账本记录。")
    lines.append("")
    lines.append("## 关键指标对比")
    lines.append(md_table(metric_rows(before, after)))
    lines.append("")
    lines.append("## Top CPU Before")
    lines.append(md_table(proc_rows(before.get("top_cpu"))))
    lines.append("")
    lines.append("## Top CPU After")
    lines.append(md_table(proc_rows(after.get("top_cpu"))))
    lines.append("")
    lines.append("## Top 内存 Before")
    lines.append(md_table(proc_rows(before.get("top_memory"))))
    lines.append("")
    lines.append("## Top 内存 After")
    lines.append(md_table(proc_rows(after.get("top_memory"))))
    lines.append("")
    lines.append("## 端口和启动项")
    lines.append(md_table([
        ["项目", "Before", "After", "说明"],
        ["TCP listeners", fmt(get(before, "listeners.tcp_count")), fmt(get(after, "listeners.tcp_count")), "不减少不一定失败，只有确认无用服务被停掉才应减少"],
        ["磁盘 I/O", "已采集" if get(before, "disk.iostat_available") else "不可用", "已采集" if get(after, "disk.iostat_available") else "不可用", "默认只做总体 I/O 快照，不做进程级追踪"],
        ["网络接口", fmt(get(before, "network.interface_row_count")), fmt(get(after, "network.interface_row_count")), "低权限概览，非进程级流量"],
        ["Launch plist count", fmt(get(before, "startup.launch_plist_count")), fmt(get(after, "startup.launch_plist_count")), "只审计，不禁用"],
        ["brew services rows", fmt(len(get(before, "startup.brew_services", []))), fmt(len(get(after, "startup.brew_services", []))), "只审计，不 stop"],
        ["后台登录项数据库", "默认不采集", "默认不采集", "避免 sfltool/权限弹窗；需要时走人工确认"],
    ]))
    lines.append("")
    lines.append("## 深度取证状态")
    lines.append("- 未做深度取证；本报告基于低权限快照。")
    lines.append("- 深度工具只能在用户确认后使用，并且必须先说明用途、风险、权限、预计耗时、临时产物和低权限替代方案。")
    lines.append("")
    lines.append("## 下一步建议")
    immediate, confirm, observe, keep = decision_lists(after)
    lines.append("- 先处理“确认后清理”里的可疑开发服务或残留辅助进程；不要动远控、代理、同步盘、输入法、浏览器主进程。")
    lines.append("- 如果 swap/pageout 继续增长，优先减少浏览器 Renderer、Electron、IDE 和本地 dev server。")
    lines.append("- 如果高 CPU 来自 syspolicyd/trustd/mdworker，先观察，不强杀系统进程。")
    if confirm:
        lines.append("")
        lines.append("### 建议确认后清理")
        lines.append(md_table(candidate_table(confirm)))
    lines.append("")
    lines.append("## 临时产物")
    lines.append(f"- Before snapshot: `{before.get('snapshot_dir', '不可用')}`")
    lines.append(f"- After snapshot: `{after.get('snapshot_dir', '不可用')}`")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Print a Chinese Mac performance diagnosis/report.")
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
