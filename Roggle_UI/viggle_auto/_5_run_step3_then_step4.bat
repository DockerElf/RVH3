@echo off
setlocal
cd /d "%~dp0"
set "VIGGLE_ROOT=%~dp0"
set "VIGGLE_MODE=both"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $root=$env:VIGGLE_ROOT; $c=Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw | ConvertFrom-Json; $p=[Environment]::ExpandEnvironmentVariables([string]$c.paths.python_executable); if (-not [IO.Path]::IsPathRooted($p)) { $p=Join-Path $root $p }; if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw ('Python not found: ' + $p) }; & $p (Join-Path $root 'launcher.py') $env:VIGGLE_MODE; exit $LASTEXITCODE } catch { Write-Host ('ERROR: ' + $_.Exception.Message); exit 1 }"
set "RESULT=%ERRORLEVEL%"
echo Exit code: %RESULT%
pause
exit /b %RESULT%
