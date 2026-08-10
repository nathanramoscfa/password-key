@echo off
REM New Password.bat — double-click launcher for password-key.
REM
REM Runs the interactive menu. Works three ways, in order of preference:
REM   1. The installed console command (pip/pipx install password-key)
REM   2. This repo checkout, via  py -m password_key
REM   3. The standalone PowerShell fallback (no Python needed)

setlocal

where password-key >nul 2>nul
if %errorlevel%==0 (
    password-key --interactive
    goto end
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHONPATH=%~dp0src"
    py -m password_key --interactive
    goto end
)

echo Python not found - using the standalone PowerShell generator.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0contrib\new-password.ps1"
pause

:end
endlocal
