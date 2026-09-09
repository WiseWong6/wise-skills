#!/usr/bin/env bash
set -u

usage() {
  cat <<'USAGE'
Usage:
  capture_macos_snapshot.sh --label before|after --out <dir>

Collects a read-only macOS performance snapshot. It does not stop processes,
does not use sudo, does not call sfltool, and does not modify launch items or
configuration files.
USAGE
}

label=""
out_dir=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      shift
      label="${1:-}"
      ;;
    --out)
      shift
      out_dir="${1:-}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift || true
done

if [ -z "$label" ] || [ -z "$out_dir" ]; then
  usage >&2
  exit 2
fi

safe_label="$(printf '%s' "$label" | tr -c 'A-Za-z0-9_.-' '_')"
snapshot_dir="${out_dir%/}/${safe_label}"
raw_dir="$snapshot_dir/raw"
mkdir -p "$raw_dir"

timestamp_utc="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

have() {
  command -v "$1" >/dev/null 2>&1
}

capture_cmd() {
  name="$1"
  shift
  file="$raw_dir/$name.txt"
  {
    printf '$'
    printf ' %q' "$@"
    printf '\n\n'
    "$@"
  } >"$file" 2>&1
  status=$?
  if [ "$status" -ne 0 ]; then
    printf '\n[unavailable or failed: exit %s]\n' "$status" >>"$file"
  fi
}

capture_shell() {
  name="$1"
  command_text="$2"
  file="$raw_dir/$name.txt"
  {
    printf '$ %s\n\n' "$command_text"
    /bin/sh -c "$command_text"
  } >"$file" 2>&1
  status=$?
  if [ "$status" -ne 0 ]; then
    printf '\n[unavailable or failed: exit %s]\n' "$status" >>"$file"
  fi
}

capture_cmd date date
capture_cmd hostname hostname
capture_cmd uname uname -a
capture_cmd uptime uptime
capture_shell disk_space "df -kHl"

if have iostat; then
  capture_shell disk_iostat "iostat -d -w 1 -c 2"
fi

if have netstat; then
  capture_shell network_interfaces "netstat -ibn | head -120"
fi

if have sysctl; then
  capture_cmd hw_memsize sysctl -n hw.memsize
  capture_shell swapusage "sysctl vm.swapusage"
  capture_shell thermal "sysctl -n machdep.xcpm.cpu_thermal_level 2>/dev/null; sysctl -n machdep.xcpm.gpu_thermal_level 2>/dev/null; pmset -g therm 2>/dev/null; pmset -g ps 2>/dev/null"
fi

if have memory_pressure; then
  capture_cmd memory_pressure memory_pressure
fi

if have vm_stat; then
  capture_cmd vm_stat vm_stat
fi

if have top; then
  capture_shell top_header "top -l 1 -n 20 -stats pid,command,cpu,mem,rsize,vsize,state,time"
fi

if have ps; then
  capture_shell process_snapshot "ps -axo pid=,ppid=,user=,etime=,%cpu=,%mem=,rss=,vsz=,stat=,comm="
fi

if have lsof; then
  capture_shell tcp_listeners "lsof -nP -iTCP -sTCP:LISTEN"
  capture_shell udp_sockets "lsof -nP -iUDP | head -120"
fi

capture_shell launch_plists "find \"\$HOME/Library/LaunchAgents\" /Library/LaunchAgents /Library/LaunchDaemons -maxdepth 1 -name '*.plist' -print 2>/dev/null | sort"

if have launchctl; then
  capture_shell launchctl_list "launchctl list"
fi

if have brew; then
  capture_shell brew_services "brew services list"
fi

if have python3; then
  python3 - "$snapshot_dir" "$safe_label" "$timestamp_utc" <<'PY'
import json
import os
import re
import sys

snapshot_dir, label, timestamp_utc = sys.argv[1:4]
raw_dir = os.path.join(snapshot_dir, "raw")

DEV_KEYWORDS = re.compile(r"codex|claude|mcp|node_repl|playwright|browser automation|node|python|java|bun|deno|vite|next|webpack|http-server", re.I)
PROTECTED_KEYWORDS = re.compile(r"chrome|safari|firefox|todesk|clash|surge|vpn|dropbox|google drive|onedrive|docker|cursor|visual studio code|code helper|zoom|teams|feishu|lark|wechat|企业微信|doubaoime|input|security|sentinel|falcon|rapportd|sharingd|bluetoothd|mdnsresponder|configd|airportd|systemuiserver|controlcenter|loginwindow|trae|kimi|kimi-webbridge|ghostty|terminal|iterm|finder|spotlight|notificationcenter|corespotlightd|suggestd|duetexpertd|applespell|webkit", re.I)

def read_raw(name):
    path = os.path.join(raw_dir, f"{name}.txt")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""

def non_command_lines(text):
    return [line.rstrip() for line in text.splitlines() if line.strip() and not line.startswith("$") and not line.startswith("[")]

def parse_number(value):
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value or "")
    if not match:
        return None
    raw = match.group(0).replace(",", "")
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return None

def parse_mib_token(token):
    if not token:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)([KMGT]?B?|[kmgt]?b?)", token.strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit in ("", "B"):
        return value / (1024 * 1024)
    if unit in ("K", "KB"):
        return value / 1024
    if unit in ("M", "MB"):
        return value
    if unit in ("G", "GB"):
        return value * 1024
    if unit in ("T", "TB"):
        return value * 1024 * 1024
    return None

def parse_etime_seconds(value):
    if not value:
        return None
    days = 0
    rest = value.strip()
    if "-" in rest:
        day_part, rest = rest.split("-", 1)
        try:
            days = int(day_part)
        except ValueError:
            days = 0
    parts = rest.split(":")
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        hours, minutes, seconds = nums
    elif len(nums) == 2:
        hours, minutes, seconds = 0, nums[0], nums[1]
    else:
        return None
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def safe_process_name(command):
    text = (command or "").strip()
    if not text:
        return ""
    first = text.split()[0]
    if "/" in text:
        return os.path.basename(text)
    if first.lower() in ("npm", "npx", "pnpm", "yarn", "node", "python", "python3", "java", "bun", "deno", "uvx"):
        return first
    return text[:80]

def parse_vm_stat(text):
    result = {"raw_available": bool(text)}
    page_size = 4096
    page_match = re.search(r"page size of (\d+) bytes", text)
    if page_match:
        page_size = int(page_match.group(1))
    pages = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        number = parse_number(value)
        if number is not None:
            pages[key.strip()] = int(number)
    def pages_to_mib(*keys):
        return round(sum(pages.get(key, 0) for key in keys) * page_size / (1024 * 1024), 1)
    return {
        "raw_available": bool(text),
        "page_size": page_size,
        "available_mib": pages_to_mib("Pages free", "Pages speculative"),
        "compressed_occupied_mib": pages_to_mib("Pages occupied by compressor"),
        "compressed_stored_mib": pages_to_mib("Pages stored in compressor"),
        "pageins": pages.get("Pageins"),
        "pageouts": pages.get("Pageouts"),
        "swapins": pages.get("Swapins"),
        "swapouts": pages.get("Swapouts"),
        "compressions": pages.get("Compressions"),
        "decompressions": pages.get("Decompressions"),
    }

def parse_memory_pressure(text):
    result = {"raw_available": bool(text)}
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", text)
    if match:
        result["free_percent"] = int(match.group(1))
    return result

def parse_swapusage(text):
    result = {"raw_available": bool(text)}
    for key in ("total", "used", "free"):
        match = re.search(rf"{key}\s*=\s*([0-9.]+\s*[KMGT]?)", text, re.I)
        if match:
            result[f"{key}_mib"] = round(parse_mib_token(match.group(1)) or 0, 1)
    return result

def parse_top_header(text):
    result = {"raw_available": bool(text)}
    load = re.search(r"Load Avg:\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)", text)
    if load:
        result["load_average"] = [float(load.group(i)) for i in range(1, 4)]
    cpu = re.search(r"CPU usage:\s*([0-9.]+)% user,\s*([0-9.]+)% sys,\s*([0-9.]+)% idle", text)
    if cpu:
        result["user_percent"] = float(cpu.group(1))
        result["system_percent"] = float(cpu.group(2))
        result["idle_percent"] = float(cpu.group(3))
    phys = next((line.strip() for line in text.splitlines() if line.startswith("PhysMem:")), None)
    if phys:
        result["physmem_line"] = phys
        unused = re.search(r",\s*([0-9.]+\s*[KMGT]?B?)\s+unused", phys, re.I)
        if unused:
            result["physmem_unused_mib"] = round(parse_mib_token(unused.group(1)) or 0, 1)
    return result

def parse_processes(text):
    rows = []
    for line in non_command_lines(text):
        parts = line.strip().split(None, 9)
        if len(parts) < 10:
            continue
        pid, ppid, user, etime, cpu, mem, rss, vsz, stat, command = parts
        process_name = safe_process_name(command)
        try:
            rows.append({
                "pid": int(pid),
                "ppid": int(ppid),
                "user": user,
                "etime": etime,
                "etime_seconds": parse_etime_seconds(etime),
                "cpu_percent": float(cpu),
                "mem_percent": float(mem),
                "rss_mib": round(int(rss) / 1024, 1),
                "vsz_mib": round(int(vsz) / 1024, 1),
                "stat": stat,
                "name": process_name,
                "command": process_name,
                "command_scope": "process_name_only_default",
                "is_dev_like": bool(DEV_KEYWORDS.search(command)),
                "is_protected_like": bool(PROTECTED_KEYWORDS.search(command)),
            })
        except ValueError:
            continue
    return rows

def parse_listeners(text):
    rows = []
    for line in non_command_lines(text):
        if line.startswith("COMMAND"):
            continue
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        command, pid, user, fd, kind, device, sizeoff, node, name = parts
        port = None
        match = re.search(r":(\d+)\s+\(LISTEN\)", name)
        if match:
            port = int(match.group(1))
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        rows.append({
            "process": command,
            "pid": pid_int,
            "user": user,
            "protocol": "TCP",
            "local": name,
            "port": port,
        })
    return rows

def parse_disk_space(text):
    rows = []
    root = {}
    data = {}
    for line in non_command_lines(text):
        if line.startswith("Filesystem"):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        fs, size, used, avail, capacity = parts[:5]
        mount = " ".join(parts[8:])
        row = {
            "filesystem": fs,
            "size_mib": round(parse_mib_token(size) or 0, 1),
            "used_mib": round(parse_mib_token(used) or 0, 1),
            "available_mib": round(parse_mib_token(avail) or 0, 1),
            "capacity": capacity,
            "mounted_on": mount,
        }
        rows.append(row)
        if mount == "/":
            root = row
        if mount == "/System/Volumes/Data":
            data = row
    return {"filesystem_count": len(rows), "root": root, "data": data, "sample": rows[:20]}

def parse_network_interfaces(text):
    rows = []
    for line in non_command_lines(text):
        if line.startswith("Name"):
            continue
        parts = line.split()
        if len(parts) >= 10:
            rows.append(line.strip())
        if len(rows) >= 30:
            break
    return {"interface_row_count": len(rows), "sample": rows}

total_mem_mib = None
for line in non_command_lines(read_raw("hw_memsize")):
    number = parse_number(line)
    if number:
        total_mem_mib = round(number / (1024 * 1024), 1)
        break

top_header = parse_top_header(read_raw("top_header"))
vm = parse_vm_stat(read_raw("vm_stat"))
pressure = parse_memory_pressure(read_raw("memory_pressure"))
pressure_available_mib = None
if total_mem_mib is not None and pressure.get("free_percent") is not None:
    pressure_available_mib = round(total_mem_mib * pressure["free_percent"] / 100, 1)

processes = parse_processes(read_raw("process_snapshot"))
listeners = parse_listeners(read_raw("tcp_listeners"))
try:
    os.remove(os.path.join(raw_dir, "process_snapshot.txt"))
except OSError:
    pass
listener_pids = {item["pid"] for item in listeners}
process_by_pid = {item["pid"]: item for item in processes}
for item in listeners:
    proc = process_by_pid.get(item["pid"])
    if proc:
        item["command"] = proc.get("command")
        item["etime"] = proc.get("etime")
        item["etime_seconds"] = proc.get("etime_seconds")

key_processes = [
    proc for proc in processes
    if proc.get("is_dev_like") or proc.get("is_protected_like") or proc.get("pid") in listener_pids
]

summary = {
    "schema_version": 2,
    "platform": "macos",
    "label": label,
    "timestamp_utc": timestamp_utc,
    "snapshot_dir": snapshot_dir,
    "raw_dir": raw_dir,
    "privacy": {
        "command_scope": "process_name_only_default",
        "full_command_line_collected": False,
        "note": "Default snapshots avoid full process arguments and remove the raw process list after parsing to reduce token, path, and secret exposure.",
    },
    "system": {
        "hostname": non_command_lines(read_raw("hostname"))[-1] if non_command_lines(read_raw("hostname")) else None,
        "uname": non_command_lines(read_raw("uname"))[-1] if non_command_lines(read_raw("uname")) else None,
        "uptime": non_command_lines(read_raw("uptime"))[0] if non_command_lines(read_raw("uptime")) else None,
    },
    "cpu": {
        "load_average": top_header.get("load_average"),
        "idle_percent": top_header.get("idle_percent"),
        "user_percent": top_header.get("user_percent"),
        "system_percent": top_header.get("system_percent"),
        "thermal_raw_available": bool(read_raw("thermal").strip()),
        "energy_inference": "low_permission_cpu_load_and_thermal_only",
    },
    "memory": {
        "total_mib": total_mem_mib,
        "pressure_available_mib": pressure_available_mib,
        "physmem_unused_mib": top_header.get("physmem_unused_mib"),
        "vm_free_speculative_mib": vm.get("available_mib"),
        "memory_pressure": pressure,
        "compressed_occupied_mib": vm.get("compressed_occupied_mib"),
        "compressed_stored_mib": vm.get("compressed_stored_mib"),
        "pageins": vm.get("pageins"),
        "pageouts": vm.get("pageouts"),
        "swapins": vm.get("swapins"),
        "swapouts": vm.get("swapouts"),
        "swapusage": parse_swapusage(read_raw("swapusage")),
    },
    "disk": {
        **parse_disk_space(read_raw("disk_space")),
        "iostat_available": bool(read_raw("disk_iostat").strip()),
        "scope": "low_permission_space_and_overall_io_only",
    },
    "network": {
        **parse_network_interfaces(read_raw("network_interfaces")),
        "scope": "low_permission_interface_overview_and_listeners_only",
    },
    "processes": {
        "count": len(processes),
        "top_cpu": sorted(processes, key=lambda row: row.get("cpu_percent", 0), reverse=True)[:15],
        "top_memory": sorted(processes, key=lambda row: row.get("rss_mib", 0), reverse=True)[:15],
        "key_processes": sorted(key_processes, key=lambda row: (row.get("is_protected_like", False), row.get("rss_mib", 0)), reverse=True)[:120],
        "all_sample": sorted(processes, key=lambda row: row.get("rss_mib", 0), reverse=True)[:250],
    },
    "listeners": {
        "tcp_count": len(listeners),
        "tcp": listeners[:120],
        "udp_sample": non_command_lines(read_raw("udp_sockets"))[:20],
    },
    "startup": {
        "launch_plist_count": len(non_command_lines(read_raw("launch_plists"))),
        "launch_plist_sample": non_command_lines(read_raw("launch_plists"))[:100],
        "brew_services": non_command_lines(read_raw("brew_services"))[:100],
        "launchctl_count": len(non_command_lines(read_raw("launchctl_list"))),
        "background_items_scope": "not_collected_by_default_low_permission",
    },
    "raw_files": sorted(os.path.join(raw_dir, name) for name in os.listdir(raw_dir) if name.endswith(".txt")) if os.path.isdir(raw_dir) else [],
}

summary_path = os.path.join(snapshot_dir, "summary.json")
with open(summary_path, "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, sort_keys=True)
    fh.write("\n")
print(summary_path)
PY
else
  cat >"$snapshot_dir/summary.json" <<JSON
{
  "schema_version": 2,
  "platform": "macos",
  "label": "$safe_label",
  "timestamp_utc": "$timestamp_utc",
  "snapshot_dir": "$snapshot_dir",
  "error": "python3 unavailable; raw files were collected but summary parsing was skipped"
}
JSON
  printf '%s\n' "$snapshot_dir/summary.json"
fi
