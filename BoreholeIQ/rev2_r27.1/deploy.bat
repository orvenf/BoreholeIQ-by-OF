@echo off
setlocal enabledelayedexpansion
title BoreholeIQ v2 - Build R27 (Modular Deploy)
color 0A

echo.
echo  ===================================================
echo    BoreholeIQ v2 - Build R27 (Modular Deploy)
echo    Prototype by Orven Fajardo of Bentley Systems
echo  ===================================================
echo.

:: ── Admin check ──────────────────────────────────────
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell"
"%PS%" -ExecutionPolicy Bypass -NoProfile -Command "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 1 }"
if %errorlevel% neq 0 (
    echo  [!!] Admin required. Elevating...
    "%PS%" -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c ""%~f0"" %*' -Verb RunAs"
    exit /b
)
echo  [OK] Running as Administrator

:: ── Paths ────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "DEPLOY_DIR=%SCRIPT_DIR%deploy\"
set "LOGFILE=%TEMP%\BoreholeIQ-deploy.log"
set "STATE_DIR=%LOCALAPPDATA%\BoreholeIQ\state"
if not exist "%STATE_DIR%" mkdir "%STATE_DIR%"
echo  [..] Logging to %LOGFILE%
echo  [..] Scripts: %SCRIPT_DIR%

:: ── Verify deploy folder ─────────────────────────────
if not exist "%DEPLOY_DIR%utils.py" (
    echo  [FATAL] deploy\utils.py not found.
    pause & exit /b 1
)

:: ══════════════════════════════════════════════════════
::  FIND OR INSTALL PYTHON (bulletproof — never uses bare 'python')
:: ══════════════════════════════════════════════════════
:: The Windows Store installs a fake python.exe stub in WindowsApps
:: that redirects to the Microsoft Store. It returns exit code 9009.
:: We NEVER trust bare 'python' — we always resolve to a full .exe path.

set "PY="

:: ── Phase 1: Disable Windows Store Python stubs ──────
:: Delete the fake python.exe stubs from WindowsApps (they cause exit 9009)
del "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" >nul 2>&1
del "%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe" >nul 2>&1

:: ── Phase 2: Check known install locations ───────────
:: These are the ONLY locations where real Python lives.
:: We check every common version, newest first.
for %%P in (
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set "PY=%%~P"
        goto :py_found
    )
)

:: ── Phase 3: Try 'where' to find python.exe (skip WindowsApps) ──
for /f "tokens=*" %%i in ('where python.exe 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        :: Not in WindowsApps — verify it's real
        "%%i" -c "import sys" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY=%%i"
            goto :py_found
        )
    )
)

:: ── Phase 4: Try py launcher ─────────────────────────
where py.exe >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%i" (
            set "PY=%%i"
            goto :py_found
        )
    )
)

:: ── Phase 5: Python not found — install it ───────────
echo  [] Python not found. Installing...

:: Try winget
winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
:: After winget, refresh PATH and check known paths
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "PATH=%%B"
for %%P in (
    "C:\Program Files\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) do (
    if exist %%P (
        set "PY=%%~P"
        goto :py_found
    )
)

:: winget failed — direct download
echo  [..] winget failed, trying direct download...
for %%V in (3.12.7 3.12.8 3.12.6) do (
    set "PY_URL=https://www.python.org/ftp/python/%%V/python-%%V-amd64.exe"
    set "PY_INS=%TEMP%\python-%%V-amd64.exe"
    "%PS%" -ExecutionPolicy Bypass -NoProfile -Command "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_INS!' -UseBasicParsing" >nul 2>&1
    if exist "!PY_INS!" (
        echo  [..] Installing Python %%V...
        "!PY_INS!" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
        :: Wait for installer to finish and refresh PATH
        timeout /t 3 /nobreak >nul
        for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "PATH=%%B"
        :: Check the known install path
        if exist "C:\Program Files\Python312\python.exe" (
            set "PY=C:\Program Files\Python312\python.exe"
            goto :py_found
        )
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
            goto :py_found
        )
    )
)

echo  [FATAL] Cannot install Python. Download manually from python.org
pause & exit /b 1

:py_found
echo  [OK] Python: %PY%

:: Verify Python actually works before proceeding
"%PY%" -c "import sys; print('Python', sys.version)" >nul 2>&1
if !errorlevel! neq 0 (
    echo  [FATAL] Python at %PY% is not working [exit !errorlevel!]
    echo  [....] The Microsoft Store Python alias may still be interfering.
    echo  [....] Go to Settings ^> Apps ^> Advanced app settings ^> App execution aliases
    echo  [....] and turn OFF both "python.exe" and "python3.exe" aliases.
    pause & exit /b 1
)

:: ══════════════════════════════════════════════════════
::  STEP 1/4: Prerequisites
:: ══════════════════════════════════════════════════════
echo.
echo  ---------------------------------------------------
echo    STEP 1/4: Prerequisites
echo  ---------------------------------------------------
if exist "%STATE_DIR%\1-prereqs.ok" (
    echo  [SKIP] Prerequisites already completed.
) else (
    "%PY%" "%DEPLOY_DIR%1_prereqs.py"
    if !errorlevel! neq 0 (
        echo  [FAIL] Step 1 Prerequisites FAILED [exit !errorlevel!]
        echo  [....] Fix the issue and re-run deploy.bat
        pause & exit /b !errorlevel!
    )
    echo OK> "%STATE_DIR%\1-prereqs.ok"
    echo  [OK] Step 1 complete
)

:: ══════════════════════════════════════════════════════
::  STEP 2/4: Libraries
:: ══════════════════════════════════════════════════════
echo.
echo  ---------------------------------------------------
echo    STEP 2/4: Libraries
echo  ---------------------------------------------------
if exist "%STATE_DIR%\2-libraries.ok" (
    echo  [SKIP] Libraries already completed.
) else (
    "%PY%" "%DEPLOY_DIR%2_libraries.py"
    if !errorlevel! neq 0 (
        echo  [FAIL] Step 2 Libraries FAILED [exit !errorlevel!]
        echo  [....] Fix the issue and re-run deploy.bat
        pause & exit /b !errorlevel!
    )
    echo OK> "%STATE_DIR%\2-libraries.ok"
    echo  [OK] Step 2 complete
)

:: ══════════════════════════════════════════════════════
::  STEP 3/4: Ollama (optional, fail-forward)
:: ══════════════════════════════════════════════════════
echo.
echo  ---------------------------------------------------
echo    STEP 3/4: Ollama AI Engine (optional)
echo  ---------------------------------------------------
if exist "%STATE_DIR%\3-ollama.ok" (
    echo  [SKIP] Ollama already completed.
) else (
    "%PY%" "%DEPLOY_DIR%3_ollama.py"
    echo OK> "%STATE_DIR%\3-ollama.ok"
    echo  [OK] Step 3 complete (AI is optional)
)

:: ══════════════════════════════════════════════════════
::  STEP 4/4: Build Application
:: ══════════════════════════════════════════════════════
echo.
echo  ---------------------------------------------------
echo    STEP 4/4: Build Application
echo  ---------------------------------------------------
if exist "%STATE_DIR%\4-app.ok" (
    echo  [SKIP] Application already built.
) else (
    if not exist "%STATE_DIR%\1-prereqs.ok" (
        echo  [FATAL] Prerequisites not completed.
        pause & exit /b 1
    )
    if not exist "%STATE_DIR%\2-libraries.ok" (
        echo  [FATAL] Libraries not installed.
        pause & exit /b 1
    )
    "%PY%" "%DEPLOY_DIR%4_app.py"
    if !errorlevel! neq 0 (
        echo  [FAIL] Step 4 Build FAILED [exit !errorlevel!]
        echo  [....] Fix the issue and re-run deploy.bat
        pause & exit /b !errorlevel!
    )
    echo OK> "%STATE_DIR%\4-app.ok"
    echo  [OK] Step 4 complete
)

echo.
echo  ===================================================
echo    BUILD COMPLETE
echo    Output: C:\BoreholeIQ\src-tauri\target\release\
echo  ===================================================
echo.
pause
