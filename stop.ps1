$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$roots = @()
foreach ($port in @(9622, 8502, 8503, 8510)) {
  $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if (-not $processInfo -or $processInfo.CommandLine -notmatch [regex]::Escape($projectRoot)) {
      throw "Port $port is not owned by this project. Refusing to stop it."
    }
    $roots += [int]$processInfo.ProcessId
  }
}
# Descendants are resolved within this process snapshot; original port 9621 is never targeted.
$processSnapshot = Get-CimInstance Win32_Process
$targets = [System.Collections.Generic.HashSet[int]]::new()
foreach ($rootId in $roots) { $null = $targets.Add($rootId) }
do {
  $added = $false
  foreach ($processInfo in $processSnapshot) {
    if ($targets.Contains([int]$processInfo.ParentProcessId) -and $targets.Add([int]$processInfo.ProcessId)) { $added = $true }
  }
} while ($added)
foreach ($targetId in $targets) { Stop-Process -Id $targetId -ErrorAction SilentlyContinue }
Write-Output 'Project services stopped. Original LightRAG was not targeted.'
