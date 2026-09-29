@echo off
rem LSAX PHASE 0 RUNTIME VALIDATION PACK - SET-PROBE-CONFIG. NOT LSAX PRODUCTION CODE.
rem Runs scripts\lib\Set-ProbeConfig.ps1 with Windows PowerShell 5.1. All arguments are passed through unchanged.
rem Usage: SET-PROBE-CONFIG.cmd -GtaRoot "[GTA folder]" -ProbeProfile PSL01/PDB01-STEP1/PDB01/PDB01-LEAK/PID01
rem Do not end a quoted path with a backslash.
setlocal
set "LSAX_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%LSAX_PS%" set "LSAX_PS=powershell.exe"
"%LSAX_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\Set-ProbeConfig.ps1" %*
set "LSAX_RC=%ERRORLEVEL%"
echo.
echo [LSAX] SET-PROBE-CONFIG finished with exit code %LSAX_RC%
if not defined LSAX_NOPAUSE pause
exit /b %LSAX_RC%
