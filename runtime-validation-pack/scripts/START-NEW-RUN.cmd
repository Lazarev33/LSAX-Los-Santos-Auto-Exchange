@echo off
rem LSAX PHASE 0 RUNTIME VALIDATION PACK - START-NEW-RUN. NOT LSAX PRODUCTION CODE.
rem Runs scripts\lib\New-Run.ps1 with Windows PowerShell 5.1. All arguments are passed through unchanged.
rem Usage: START-NEW-RUN.cmd -GtaRoot "[GTA folder]" -Label [name]
rem Do not end a quoted path with a backslash.
setlocal
set "LSAX_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%LSAX_PS%" set "LSAX_PS=powershell.exe"
"%LSAX_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\New-Run.ps1" %*
set "LSAX_RC=%ERRORLEVEL%"
echo.
echo [LSAX] START-NEW-RUN finished with exit code %LSAX_RC%
if not defined LSAX_NOPAUSE pause
exit /b %LSAX_RC%
