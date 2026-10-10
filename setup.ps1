$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { uv venv --python 3.13 .venv }
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
if (Test-Path -LiteralPath 'requirements.lock') {
  uv pip install --python .venv/Scripts/python.exe -r requirements.lock
} else {
  uv pip install --python .venv/Scripts/python.exe -e 'vendor/LightRAG[api]' -e '.[dev]'
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 or newer before building the Vue app.' }
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
try {
  npm ci --cache (Join-Path $PSScriptRoot '.npm-cache')
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Output 'Ready. Configure your DeepSeek key in the project .env, then run start.ps1.'
