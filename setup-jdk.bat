@echo off
REM ============================================================
REM  Osiris Guide - toolchain bootstrap
REM  Installs Eclipse Temurin JDK 11 (required to build the
REM  RuneLite plugin) via winget. Double-click to run.
REM ============================================================
setlocal enableextensions enabledelayedexpansion

echo(
echo === Osiris Guide toolchain setup (JDK 11) ===
echo(

where winget >nul 2>&1
if errorlevel 1 (
  echo [ERROR] winget not found. Install "App Installer" from the Microsoft Store, then re-run.
  goto :end
)

echo Installing Eclipse Temurin JDK 11 via winget...
winget install -e --id EclipseAdoptium.Temurin.11.JDK ^
  --accept-source-agreements --accept-package-agreements --silent
set WINGET_RC=%errorlevel%
echo winget exit code: %WINGET_RC%
echo(

REM Try to locate the freshly installed JDK 11 and expose JAVA_HOME
set "JDK_DIR="
for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-11*") do set "JDK_DIR=%%~fD"
if defined JDK_DIR (
  echo Found JDK at: !JDK_DIR!
  setx JAVA_HOME "!JDK_DIR!" >nul
  echo JAVA_HOME set (takes effect in NEW shells).
  "!JDK_DIR!\bin\java.exe" -version
) else (
  echo [WARN] Could not locate JDK 11 install dir under "C:\Program Files\Eclipse Adoptium".
  echo        If winget succeeded, open a NEW terminal so PATH refreshes.
)

echo(
echo === done ===
:end
endlocal
pause
