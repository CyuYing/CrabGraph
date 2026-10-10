$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workbenchScript = Join-Path $projectRoot 'scripts\run_workbench.py'
$listeners = Get-NetTCPConnection -LocalPort 8503 -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    $jobs = Invoke-RestMethod 'http://127.0.0.1:8503/api/jobs' -TimeoutSec 5
    if ($jobs | Where-Object { $_.status -in @('running', 'queued') }) {
        throw 'Wait for active tasks to finish before restarting.'
    }
    foreach ($listener in $listeners) {
        $serviceOwner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($serviceOwner.CommandLine -notmatch [regex]::Escape($workbenchScript)) {
            throw 'Port 8503 does not belong to this workbench.'
        }
        Stop-Process -Id $listener.OwningProcess -ErrorAction Stop
    }
}
$service = Start-Process -FilePath (Join-Path $projectRoot '.venv\Scripts\python.exe') -ArgumentList @('"' + $workbenchScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'runtime\logs\workbench.stdout.log') -RedirectStandardError (Join-Path $projectRoot 'runtime\logs\workbench.stderr.log')
$service.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'runtime\workbench.pid')
for ($attempt = 0; $attempt -lt 25; $attempt++) {
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:8503/api/health' -TimeoutSec 2
        Write-Output 'Workbench ready: http://127.0.0.1:8503/'
        exit 0
    } catch { Start-Sleep -Seconds 1 }
}
throw 'Workbench did not become ready. Check runtime/logs.'
