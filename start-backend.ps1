$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot 'backend_mock'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
  Write-Error "Missing backend virtualenv: $pythonExe"
  exit 1
}

$existing = Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -eq 'python.exe' -and
    $_.CommandLine -like '*ontology-scenario*backend_mock*main.py*'
  } |
  Select-Object -ExpandProperty ProcessId -ErrorAction SilentlyContinue

if ($existing) {
  Write-Host 'backend_mock is already running.'
  exit 0
}

$command = "Set-Location `"$backendDir`"; & `"$pythonExe`" .\main.py"
Start-Process powershell.exe -ArgumentList '-NoExit', '-Command', $command -WindowStyle Normal

Write-Host 'Opened backend_mock window.'
