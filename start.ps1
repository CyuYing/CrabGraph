$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup.ps1 first.' }
$runtimePath = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Path (Join-Path $runtimePath 'logs') -Force | Out-Null
$ragUrl = 'http://127.0.0.1:9622'
try {
  $health = Invoke-RestMethod "$ragUrl/health" -TimeoutSec 3
  $expected = [IO.Path]::GetFullPath((Join-Path $runtimePath 'lightrag\rag_storage'))
  if ([IO.Path]::GetFullPath($health.working_directory) -ne $expected) { throw 'Port 9622 is used by another LightRAG.' }
} catch {
  if (Get-NetTCPConnection -LocalPort 9622 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 9622 is occupied; refusing to attach to another service.' }
  $ragScript = Join-Path $projectRoot 'scripts\run_lightrag.py'
  $ragProcess = Start-Process -FilePath $pythonPath -ArgumentList @('"' + $ragScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'logs\lightrag.stdout.log') -RedirectStandardError (Join-Path $runtimePath 'logs\lightrag.stderr.log')
  $ragProcess.Id | Set-Content -LiteralPath (Join-Path $runtimePath 'lightrag.pid')
  $ready = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if ($ragProcess.HasExited) { throw 'LightRAG failed to start. Check runtime/logs/lightrag.stderr.log.' }
    try { $null = Invoke-RestMethod "$ragUrl/health" -TimeoutSec 2; $ready = $true; break } catch {}
  }
  if (-not $ready) { throw 'LightRAG startup timeout. Check logs.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Run setup.ps1 to build the Vue frontend.' }
foreach ($port in @(8510, 8503)) {
  $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($listeners) {
    foreach ($listener in $listeners) {
      $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
      if ($owner.CommandLine -notmatch [regex]::Escape($projectRoot)) { throw "Port $port is owned by another service." }
    }
    continue
  }
  if ($port -eq 8510) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'pgvector-seed.json'))) {
      & $pythonPath (Join-Path $projectRoot 'scripts\seed_pgvector.py')
      if ($LASTEXITCODE -ne 0) { throw 'Vector copy failed.' }
    }
    $executable = (Get-Command node -ErrorAction Stop).Source
    $serviceScript = Join-Path $projectRoot 'frontend\vector-server.mjs'
    $logName = 'pgvector'
  } else {
    $executable = $pythonPath
    $serviceScript = Join-Path $projectRoot 'scripts\run_workbench.py'
    $logName = 'workbench'
  }
  $service = Start-Process -FilePath $executable -ArgumentList @('"' + $serviceScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath "logs\$logName.stdout.log") -RedirectStandardError (Join-Path $runtimePath "logs\$logName.stderr.log")
  $service.Id | Set-Content -LiteralPath (Join-Path $runtimePath "$logName.pid")
  $ready = $false
  $healthPath = if ($port -eq 8503) { '/api/health' } else { '/health' }
  for ($i=0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 1
    if ($service.HasExited) { throw "$logName failed to start. Check runtime/logs." }
    try { $null = Invoke-RestMethod "http://127.0.0.1:$port$healthPath" -TimeoutSec 2; $ready = $true; break } catch {}
  }
  if (-not $ready) { throw "$logName startup timed out." }
}
Write-Output 'CrabGraph Vue workbench: http://127.0.0.1:8503'
Write-Output 'Migrated LightRAG: http://127.0.0.1:9622/webui/'
Write-Output 'PostgreSQL + pgvector: http://127.0.0.1:8510/health'
