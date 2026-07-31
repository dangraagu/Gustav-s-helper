@echo off
REM ============================================================================
REM  play-gustav.bat  -  one-click: launch a RuneLite dev client with Gustav's
REM  Helper loaded, auto-logging into your JAGEX account.
REM
REM  First run: if no saved Jagex credentials are found, it opens the RuneLite
REM  "configure" window and walks you through a one-time setup. Every run after
REM  that is a true one-click launch of the latest build.
REM ============================================================================
setlocal enableextensions enabledelayedexpansion
cd /d "%~dp0"

REM --- locate JDK 11 (portable in %USERPROFILE%\jdk11, or system Temurin 11) ---
set "JH="
if exist "%USERPROFILE%\jdk11" for /d %%D in ("%USERPROFILE%\jdk11\jdk-11*") do set "JH=%%~fD"
if not defined JH for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-11*") do set "JH=%%~fD"
if defined JH (
  set "JAVA_HOME=!JH!"
) else (
  echo [WARN] JDK 11 not found. Run setup-jdk.bat first, or install Temurin 11.
)

set "CREDS=%USERPROFILE%\.runelite\credentials.properties"
if exist "%CREDS%" goto :launch

echo ============================================================
echo   ONE-TIME SETUP - link your Jagex login to the dev client
echo ============================================================
echo.
echo   A RuneLite "configure" window is opening now.
echo.
echo   1) In the "Client arguments" box, add exactly:
echo          --insecure-write-credentials
echo      then click Save.
echo.
echo   2) Launch RuneLite through the JAGEX launcher as normal and log in.
echo      (That writes your login to credentials.properties.)
echo.
echo   3) Close the game, then double-click THIS file again.
echo.
echo   (Security note: that flag stores your login token in a local plaintext
echo    file. Remove it from Client arguments again when you're done testing.)
echo ------------------------------------------------------------
set "RL=%LOCALAPPDATA%\RuneLite\RuneLite.exe"
if exist "%RL%" (
  start "" "%RL%" --configure
) else (
  echo [!] Could not find RuneLite.exe automatically.
  echo     Open "RuneLite (configure)" from the Start menu instead.
)
echo.
pause
exit /b

:launch
echo Jagex credentials found.
if defined JAVA_HOME echo Using JAVA_HOME=!JAVA_HOME!
echo Building + launching Gustav's Helper dev client (auto-login)...
echo (first run downloads dependencies - give it a minute)
call gradlew.bat run
echo.
echo Client closed. If login failed, launch once via the Jagex launcher to
echo refresh credentials, then run this again.
pause
endlocal
