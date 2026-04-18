$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $repoRoot 'frontend'

& (Join-Path $repoRoot 'start-backend.ps1')

$existingFrontend = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*ontology-scenario*frontend*vite*' } |
  Select-Object -ExpandProperty ProcessId -ErrorAction SilentlyContinue

if ($existingFrontend) {
  Write-Host 'frontend dev server is already running.'
  exit 0
}

$command = "Set-Location `"$frontendDir`"; npm run dev"
Start-Process powershell.exe -ArgumentList '-NoExit', '-Command', $command -WindowStyle Normal

Write-Host 'Opened frontend dev window.'
