@echo off
REM New Password.bat - double-click launcher for password-key.
REM
REM Opens the interactive menu. Works three ways, in order of preference:
REM   1. The installed console command (pipx/pip install password-key)
REM   2. This repo checkout, run in place via  py -m password_key
REM   3. The standalone PowerShell generator (no Python required)

setlocal EnableExtensions EnableDelayedExpansion

REM When launched by double-click, cmd closes the window the instant this
REM script ends - which would wipe the result off the screen before it
REM can be read. %cmdcmdline% contains this script's name only in that
REM case, never when it is run from an already-open console, so it tells
REM the two apart and only the double-click path pauses.
set "PAUSE_ON_EXIT="
set "SCRIPT_NAME=%~nx0"
echo !cmdcmdline! | find /i "!SCRIPT_NAME!" >nul && set "PAUSE_ON_EXIT=1"

where password-key >nul 2>nul
if not errorlevel 1 (
    password-key --interactive
    goto done
)

if exist "%~dp0src\password_key\__init__.py" (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHONPATH=%~dp0src"
        py -m password_key --interactive
        goto done
    )
)

echo.
echo   password-key is not installed and Python was not found.
echo   Falling back to the standalone PowerShell generator.
echo.
echo   To get the full version ^(passphrases, auto-clear^), install
echo   Python and then run:  pip install password-key
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0contrib\new-password.ps1"

:done
if defined PAUSE_ON_EXIT pause
endlocal
