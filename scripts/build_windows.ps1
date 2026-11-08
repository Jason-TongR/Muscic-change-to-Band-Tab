param([switch]$SkipSetup)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "2"
$env:OPENBLAS_NUM_THREADS = "2"
$env:NUMBA_NUM_THREADS = "2"
$env:QT_QPA_PLATFORM = "offscreen"
$python = Join-Path (Get-Location) ".venv-desktop\Scripts\python.exe"
if (-not $SkipSetup) {
    & py -3.11 scripts/setup_desktop.py
    if ($LASTEXITCODE -ne 0) { throw "Desktop environment setup failed." }
}
if (-not (Test-Path $python)) { throw "Python environment missing. Run without -SkipSetup." }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
& $python scripts/build_desktop.py --archive --require-installer
if ($LASTEXITCODE -ne 0) { throw "Build failed." }
& $python scripts/check_windows_release.py
if ($LASTEXITCODE -ne 0) { throw "Packaged Windows validation failed. See data/windows-validation." }
Copy-Item data/windows-validation/windows-validation.json release/Windows-validation.json
Write-Host "Windows installer, portable ZIP, sample project and checksums are ready in release/."
