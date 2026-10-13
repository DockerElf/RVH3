@echo off
setlocal
cd /d "%~dp0"
set "ROGGLE_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $root=$env:ROGGLE_ROOT; $c=Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw | ConvertFrom-Json; $p=[string]$c.paths.python_executable; $base=$root; if ([string]::IsNullOrWhiteSpace($p)) { $project=[Environment]::ExpandEnvironmentVariables([string]$c.paths.viggle_auto); if (-not [IO.Path]::IsPathRooted($project)) { $project=Join-Path $root $project }; $linked=Get-Content -LiteralPath (Join-Path $project 'config.json') -Raw | ConvertFrom-Json; $p=[string]$linked.paths.python_executable; $base=$project }; $p=[Environment]::ExpandEnvironmentVariables($p); if ([string]::IsNullOrWhiteSpace($p)) { throw 'No configured Python executable' }; if (-not [IO.Path]::IsPathRooted($p)) { $p=Join-Path $base $p }; if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw ('Python not found: ' + $p) }; & $p (Join-Path $root 'app\server.py'); exit $LASTEXITCODE } catch { Write-Host ('ERROR: ' + $_.Exception.Message); exit 1 }"
set "RESULT=%ERRORLEVEL%"
echo Exit code: %RESULT%
pause
exit /b %RESULT%
