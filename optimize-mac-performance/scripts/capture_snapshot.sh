#!/usr/bin/env bash
set -u

usage() {
  cat <<'USAGE'
Usage:
  capture_snapshot.sh --label before|after --out <dir>

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
    {
      printf '\n[unavailable or failed: exit %s]\n' "$status"
    } >>"$file"
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
    {
      printf '\n[unavailable or failed: exit %s]\n' "$status"
    } >>"$file"
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
  capture_shell top_cpu "top -l 1 -n 20 -o cpu -stats pid,command,cpu,mem,rsize,vsize,state,time"
  capture_shell top_mem "top -l 1 -n 20 -o mem -stats pid,command,cpu,mem,rsize,vsize,state,time"
fi

if have ps; then
  capture_shell ps_cpu "ps -axo pid=,ppid=,user=,%cpu=,%mem=,rss=,vsz=,stat=,command= | sort -k4 -nr | head -40"
  capture_shell ps_mem "ps -axo pid=,ppid=,user=,%cpu=,%mem=,rss=,vsz=,stat=,command= | sort -k5 -nr | head -40"
  capture_shell key_processes "ps -axo pid=,ppid=,user=,%cpu=,%mem=,rss=,stat=,command= | egrep -i 'Codex|Claude|Chrome|Chromium|Electron|Docker|node|python|java|bun|deno|MCP|node_repl|playwright|browser|ToDesk|Clash|Surge|VPN|Dropbox|Google Drive|OneDrive|Cursor|Visual Studio Code|Code Helper|idea|WebStorm|Zoom|Teams|Feishu|Lark' || true"
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

def read_raw(name):
    path = os.path.join(raw_dir, f"{name}.txt")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""

def first_matching(text, prefix):
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.strip()
    return None

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

def parse_vm_stat(text):
    result = {"raw_available": bool(text)}
    page_size = 4096
    page_match = re.search(r"page size of (\d+) bytes", text)
    if page_match:
        page_size = int(page_match.group(1))
    result["page_size"] = page_size
    pages = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        number = parse_number(value)
        if number is not None:
            pages[key.strip()] = int(number)
    result["pages"] = pages
    def pages_to_mib(*keys):
        total = sum(pages.get(key, 0) for key in keys)
        return round(total * page_size / (1024 * 1024), 1)
    result["available_mib"] = pages_to_mib("Pages free", "Pages speculative")
    result["compressed_occupied_mib"] = pages_to_mib("Pages occupied by compressor")
    result["compressed_stored_mib"] = pages_to_mib("Pages stored in compressor")
    for key in ("Pageins", "Pageouts", "Swapins", "Swapouts", "Compressions", "Decompressions"):
        result[key.lower()] = pages.get(key)
    return result

def parse_memory_pressure(text):
    result = {"raw_available": bool(text)}
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", text)
    if match:
        result["free_percent"] = int(match.group(1))
    for line in text.splitlines():
        if "memory free percentage" in line:
            result["free_percent_line"] = line.strip()
            break
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
        result["cpu"] = {
            "user_percent": float(cpu.group(1)),
            "system_percent": float(cpu.group(2)),
            "idle_percent": float(cpu.group(3)),
        }
    phys = first_matching(text, "PhysMem:")
    if phys:
        result["physmem_line"] = phys
        unused = re.search(r",\s*([0-9.]+\s*[KMGT]?B?)\s+unused", phys, re.I)
        if unused:
            result["physmem_unused_mib"] = round(parse_mib_token(unused.group(1)) or 0, 1)
    vm = first_matching(text, "VM:")
    if vm:
        result["vm_line"] = vm
    return result

def parse_processes(text, limit=10):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("$") or line.startswith("["):
            continue
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        pid, ppid, user, cpu, mem, rss, vsz, stat, command = parts
        try:
            row = {
                "pid": int(pid),
                "ppid": int(ppid),
                "user": user,
                "cpu_percent": float(cpu),
                "mem_percent": float(mem),
                "rss_mib": round(int(rss) / 1024, 1),
                "vsz_mib": round(int(vsz) / 1024, 1),
                "stat": stat,
                "command": command,
            }
        except ValueError:
            continue
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows

def parse_listener_lines(text, limit=80):
    lines = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("$") or line.startswith("COMMAND") or line.startswith("["):
            continue
        lines.append(line.rstrip())
        if len(lines) >= limit:
            break
    return lines

def count_non_command_lines(text):
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("$") and not stripped.startswith("["):
            count += 1
    return count

def parse_disk_space(text):
    rows = []
    root = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("$") or stripped.startswith("Filesystem") or stripped.startswith("["):
            continue
        parts = stripped.split()
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
    return {
        "filesystem_count": len(rows),
        "root_available_mib": root.get("available_mib"),
        "root_capacity": root.get("capacity"),
        "sample": rows[:20],
    }

def parse_network_interfaces(text):
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("$") or stripped.startswith("Name") or stripped.startswith("["):
            continue
        parts = stripped.split()
        if len(parts) < 10:
            continue
        rows.append(stripped)
        if len(rows) >= 30:
            break
    return {
        "interface_row_count": len(rows),
        "sample": rows,
    }

total_mem_mib = None
hw_mem = read_raw("hw_memsize")
for line in hw_mem.splitlines():
    if line.startswith("$") or not line.strip():
        continue
    number = parse_number(line)
    if number:
        total_mem_mib = round(number / (1024 * 1024), 1)
        break

vm_stat = parse_vm_stat(read_raw("vm_stat"))
free_speculative_percent_pages = None
if total_mem_mib and vm_stat.get("available_mib") is not None:
    free_speculative_percent_pages = round(vm_stat["available_mib"] / total_mem_mib * 100, 1)

top = parse_top_header(read_raw("top_cpu"))
memory_pressure = parse_memory_pressure(read_raw("memory_pressure"))
pressure_available_mib = None
if total_mem_mib is not None and memory_pressure.get("free_percent") is not None:
    pressure_available_mib = round(total_mem_mib * memory_pressure["free_percent"] / 100, 1)

summary = {
    "schema_version": 1,
    "label": label,
    "timestamp_utc": timestamp_utc,
    "snapshot_dir": snapshot_dir,
    "raw_dir": raw_dir,
    "system": {
        "hostname": read_raw("hostname").splitlines()[-1].strip() if read_raw("hostname").strip() else None,
        "uname": read_raw("uname").splitlines()[-1].strip() if read_raw("uname").strip() else None,
        "uptime": next((line.strip() for line in read_raw("uptime").splitlines() if line and not line.startswith("$")), None),
    },
    "memory": {
        "total_mib": total_mem_mib,
        "pressure_available_mib": pressure_available_mib,
        "physmem_unused_mib": top.get("physmem_unused_mib"),
        "vm_free_speculative_mib": vm_stat.get("available_mib"),
        "vm_free_speculative_percent": free_speculative_percent_pages,
        "memory_pressure": memory_pressure,
        "compressed_occupied_mib": vm_stat.get("compressed_occupied_mib"),
        "compressed_stored_mib": vm_stat.get("compressed_stored_mib"),
        "pageins": vm_stat.get("pageins"),
        "pageouts": vm_stat.get("pageouts"),
        "swapins": vm_stat.get("swapins"),
        "swapouts": vm_stat.get("swapouts"),
        "swapusage": parse_swapusage(read_raw("swapusage")),
        "physmem_line": top.get("physmem_line"),
        "vm_line": top.get("vm_line"),
    },
    "cpu": {
        "load_average": top.get("load_average"),
        **top.get("cpu", {}),
        "thermal_raw": read_raw("thermal").strip(),
        "energy_inference": "low_permission_cpu_load_and_thermal_only",
    },
    "disk": {
        **parse_disk_space(read_raw("disk_space")),
        "iostat_available": bool(read_raw("disk_iostat").strip()),
        "iostat_raw": read_raw("disk_iostat").strip(),
        "scope": "low_permission_space_and_overall_io_only",
    },
    "network": {
        **parse_network_interfaces(read_raw("network_interfaces")),
        "scope": "low_permission_interface_overview_and_listeners_only",
    },
    "top_cpu": parse_processes(read_raw("ps_cpu"), 10),
    "top_memory": parse_processes(read_raw("ps_mem"), 10),
    "listeners": {
        "tcp_count": len(parse_listener_lines(read_raw("tcp_listeners"), 10000)),
        "tcp_sample": parse_listener_lines(read_raw("tcp_listeners"), 40),
        "udp_sample": parse_listener_lines(read_raw("udp_sockets"), 20),
    },
    "startup": {
        "launch_plist_count": count_non_command_lines(read_raw("launch_plists")),
        "launch_plist_sample": [line for line in read_raw("launch_plists").splitlines() if line and not line.startswith("$")][:80],
        "brew_services": [line for line in read_raw("brew_services").splitlines() if line and not line.startswith("$")][:80],
        "launchctl_count": count_non_command_lines(read_raw("launchctl_list")),
        "background_items_scope": "not_collected_by_default_low_permission",
    },
    "raw_files": sorted(
        os.path.join(raw_dir, name)
        for name in os.listdir(raw_dir)
        if name.endswith(".txt")
    ) if os.path.isdir(raw_dir) else [],
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
  "schema_version": 1,
  "label": "$safe_label",
  "timestamp_utc": "$timestamp_utc",
  "snapshot_dir": "$snapshot_dir",
  "error": "python3 unavailable; raw files were collected but summary parsing was skipped"
}
JSON
  printf '%s\n' "$snapshot_dir/summary.json"
fi
