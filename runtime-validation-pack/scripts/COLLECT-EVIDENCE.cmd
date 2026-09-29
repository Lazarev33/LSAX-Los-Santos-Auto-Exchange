@echo off
rem LSAX PHASE 0 RUNTIME VALIDATION PACK - COLLECT-EVIDENCE. NOT LSAX PRODUCTION CODE.
rem Runs scripts\lib\Collect-Evidence.ps1 with Windows PowerShell 5.1. All arguments are passed through unchanged.
rem Usage: COLLECT-EVIDENCE.cmd -GtaRoot "[GTA folder]" -Config FULL-MODPACK/MINIMAL -Phase SMOKE/FULL/PDB01/PID01/PSL02/OTHER [-IncludeShvdnLogExcerpt]
rem Do not end a quoted path with a backslash.
setlocal
set "LSAX_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%LSAX_PS%" set "LSAX_PS=powershell.exe"
"%LSAX_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\Collect-Evidence.ps1" %*
set "LSAX_RC=%ERRORLEVEL%"
echo.
echo [LSAX] COLLECT-EVIDENCE finished with exit code %LSAX_RC%
if not defined LSAX_NOPAUSE pause
exit /b %LSAX_RC%
