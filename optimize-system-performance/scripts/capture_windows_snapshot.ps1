param(
  [Parameter(Mandatory = $true)][ValidateSet("before", "after")][string]$Label,
  [Parameter(Mandatory = $true)][string]$Out
)

$ErrorActionPreference = "SilentlyContinue"

$safeLabel = ($Label -replace '[^A-Za-z0-9_.-]', '_')
$snapshotDir = Join-Path $Out $safeLabel
$rawDir = Join-Path $snapshotDir "raw"
New-Item -ItemType Directory -Path $rawDir -Force | Out-Null
$timestampUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

function Convert-ToMiB {
  param([Nullable[double]]$Bytes)
  if ($null -eq $Bytes) { return $null }
  return [Math]::Round(($Bytes / 1MB), 1)
}

function Save-LowRiskText {
  param([string]$Name, [object]$Value)
  $path = Join-Path $rawDir "$Name.txt"
  $Value | Out-String -Width 240 | Set-Content -Path $path -Encoding UTF8
}

function Safe-Run {
  param([scriptblock]$Block)
  try { & $Block } catch { $null }
}

$os = Safe-Run { Get-CimInstance Win32_OperatingSystem }
$computer = Safe-Run { Get-CimInstance Win32_ComputerSystem }
$logicalDisks = @(Safe-Run { Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" })
$procCim = @(Safe-Run { Get-CimInstance Win32_Process })
$procBasic = @(Safe-Run { Get-Process })
$tcpListen = @(Safe-Run { Get-NetTCPConnection -State Listen })
$services = @(Safe-Run { Get-Service })
$startup = @(Safe-Run { Get-CimInstance Win32_StartupCommand | Select-Object Name, Location, User })
$cpuCounter = Safe-Run { (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue }

Save-LowRiskText "system" ([pscustomobject]@{
  ComputerName = $env:COMPUTERNAME
  UserDomain = $env:USERDOMAIN
  OS = $os.Caption
  Version = $os.Version
})
Save-LowRiskText "disk" $logicalDisks
Save-LowRiskText "services_summary" ($services | Select-Object -First 300 Name, DisplayName, Status, StartType)
Save-LowRiskText "startup_summary" $startup
Save-LowRiskText "tcp_listeners" ($tcpListen | Select-Object -First 300 LocalAddress, LocalPort, OwningProcess, State)

$basicById = @{}
foreach ($p in $procBasic) { $basicById[[int]$p.Id] = $p }

$processes = @()
foreach ($p in $procCim) {
  $id = [int]$p.ProcessId
  $basic = $basicById[$id]
  $created = $null
  $ageSeconds = $null
  if ($p.CreationDate) {
    $created = [Management.ManagementDateTimeConverter]::ToDateTime($p.CreationDate)
    $ageSeconds = [int]((Get-Date) - $created).TotalSeconds
  }
  $cmd = $p.Name
  $processes += [pscustomobject]@{
    pid = $id
    ppid = [int]$p.ParentProcessId
    user = $null
    etime = $null
    etime_seconds = $ageSeconds
    cpu_percent = $null
    mem_percent = $null
    rss_mib = Convert-ToMiB $p.WorkingSetSize
    vsz_mib = Convert-ToMiB $p.VirtualSize
    stat = $null
    name = $p.Name
    command = $cmd
    command_scope = "process_name_only_default"
    cpu_time_seconds = if ($basic) { [Math]::Round($basic.CPU, 1) } else { $null }
    is_dev_like = [bool]($cmd -match '(?i)codex|claude|mcp|node_repl|playwright|browser automation|node|python|java|bun|deno|vite|next|webpack|http-server')
    is_protected_like = [bool]($cmd -match '(?i)chrome|edge|firefox|remote|vpn|clash|surge|dropbox|onedrive|google drive|docker|cursor|visual studio code|code helper|trae|kimi|terminal|powershell|cmd|zoom|teams|lark|feishu|wechat|input|security|defender|sentinel|falcon')
  }
}

$listenerRows = @()
foreach ($l in $tcpListen) {
  $pid = [int]$l.OwningProcess
  $proc = $processes | Where-Object { $_.pid -eq $pid } | Select-Object -First 1
  $listenerRows += [pscustomobject]@{
    process = if ($proc) { $proc.name } else { $null }
    pid = $pid
    user = $null
    protocol = "TCP"
    local = "$($l.LocalAddress):$($l.LocalPort)"
    port = [int]$l.LocalPort
    command = if ($proc) { $proc.command } else { $null }
    etime = $null
    etime_seconds = if ($proc) { $proc.etime_seconds } else { $null }
  }
}

$totalMemMiB = if ($os.TotalVisibleMemorySize) { Convert-ToMiB ([double]$os.TotalVisibleMemorySize * 1KB) } else { $null }
$freeMemMiB = if ($os.FreePhysicalMemory) { Convert-ToMiB ([double]$os.FreePhysicalMemory * 1KB) } else { $null }
$swapUsedMiB = $null
if ($os.TotalVirtualMemorySize -and $os.FreeVirtualMemory) {
  $swapUsedMiB = [Math]::Round((($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1024), 1)
}

$diskRows = @()
foreach ($d in $logicalDisks) {
  $diskRows += [pscustomobject]@{
    filesystem = $d.DeviceID
    size_mib = Convert-ToMiB $d.Size
    used_mib = if ($d.Size -and $d.FreeSpace) { Convert-ToMiB ($d.Size - $d.FreeSpace) } else { $null }
    available_mib = Convert-ToMiB $d.FreeSpace
    capacity = if ($d.Size) { "$([Math]::Round((($d.Size - $d.FreeSpace) / $d.Size) * 100, 1))%" } else { $null }
    mounted_on = $d.DeviceID
  }
}

$summary = [ordered]@{
  schema_version = 2
  platform = "windows"
  label = $Label
  timestamp_utc = $timestampUtc
  snapshot_dir = $snapshotDir
  raw_dir = $rawDir
  privacy = [ordered]@{
    command_scope = "process_name_only_default"
    full_command_line_collected = $false
    note = "Default snapshots avoid full process arguments to reduce token, path, and secret exposure."
  }
  system = [ordered]@{
    hostname = $env:COMPUTERNAME
    uname = "$($os.Caption) $($os.Version)"
    uptime = if ($os.LastBootUpTime) { "Last boot: $($os.LastBootUpTime)" } else { $null }
  }
  cpu = [ordered]@{
    load_average = @()
    idle_percent = if ($null -ne $cpuCounter) { [Math]::Round((100 - [double]$cpuCounter), 1) } else { $null }
    user_percent = $null
    system_percent = $null
    thermal_raw_available = $false
    energy_inference = "low_permission_process_cpu_time_only"
  }
  memory = [ordered]@{
    total_mib = $totalMemMiB
    pressure_available_mib = $freeMemMiB
    physmem_unused_mib = $freeMemMiB
    vm_free_speculative_mib = $freeMemMiB
    memory_pressure = [ordered]@{
      raw_available = $true
      free_percent = if ($totalMemMiB) { [Math]::Round(($freeMemMiB / $totalMemMiB) * 100, 1) } else { $null }
    }
    compressed_occupied_mib = $null
    compressed_stored_mib = $null
    pageins = $null
    pageouts = $null
    swapins = $null
    swapouts = $null
    swapusage = [ordered]@{
      raw_available = $true
      used_mib = $swapUsedMiB
    }
  }
  disk = [ordered]@{
    filesystem_count = $diskRows.Count
    root = if ($diskRows.Count -gt 0) { $diskRows[0] } else { $null }
    data = $null
    sample = @($diskRows)
    iostat_available = $false
    scope = "low_permission_space_only"
  }
  network = [ordered]@{
    interface_row_count = $null
    sample = @()
    scope = "low_permission_listeners_only"
  }
  processes = [ordered]@{
    count = $processes.Count
    top_cpu = @($processes | Sort-Object -Property cpu_time_seconds -Descending | Select-Object -First 15)
    top_memory = @($processes | Sort-Object -Property rss_mib -Descending | Select-Object -First 15)
    key_processes = @($processes | Where-Object { $_.is_dev_like -or $_.is_protected_like } | Sort-Object -Property rss_mib -Descending | Select-Object -First 120)
    all_sample = @($processes | Sort-Object -Property rss_mib -Descending | Select-Object -First 250)
  }
  listeners = [ordered]@{
    tcp_count = $listenerRows.Count
    tcp = @($listenerRows | Select-Object -First 120)
    udp_sample = @()
  }
  startup = [ordered]@{
    launch_plist_count = $startup.Count
    launch_plist_sample = @($startup | Select-Object -First 100)
    brew_services = @()
    launchctl_count = $services.Count
    service_sample = @($services | Select-Object -First 120 Name, DisplayName, Status, StartType)
    background_items_scope = "low_sensitive_startup_and_service_summary_only"
  }
  raw_files = @((Get-ChildItem -Path $rawDir -File | ForEach-Object { $_.FullName }))
}

$summaryPath = Join-Path $snapshotDir "summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Output $summaryPath
