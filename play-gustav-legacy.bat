@echo off
REM ============================================================================
REM  play-gustav-legacy.bat  -  launch the dev client with Gustav's Helper for a
REM  REGULAR (non-Jagex-launcher) account: the normal username/password login.
REM
REM  play-gustav.bat auto-logs into your JAGEX account using the saved
REM  .runelite\credentials.properties. This one temporarily moves that file aside
REM  so the client shows the ordinary RuneScape login screen instead, then puts
REM  it back when you close the client (so the Jagex launcher keeps working).
REM ============================================================================
setlocal enableextensions enabledelayedexpansion
cd /d "%~dp0"

set "CREDS=%USERPROFILE%\.runelite\credentials.properties"
set "STASH=%USERPROFILE%\.runelite\credentials.properties.gustavbak"

REM Self-heal: a previous run that was killed (window closed) may have left the
REM file stashed. Put it back before doing anything else.
if exist "%STASH%" if not exist "%CREDS%" (
  echo Restoring Jagex credentials left stashed by a previous run...
  move /y "%STASH%" "%CREDS%" >nul
)
REM If BOTH exist, the live file is authoritative (the launcher rewrote it since
REM the stash was made) — drop the stale copy so the exit path can never restore
REM an older credential file over the current one.
if exist "%STASH%" if exist "%CREDS%" del /q "%STASH%" >nul 2>&1

REM --- locate JDK 11 (portable in %USERPROFILE%\jdk11, or system Temurin 11) ---
set "JH="
if exist "%USERPROFILE%\jdk11" for /d %%D in ("%USERPROFILE%\jdk11\jdk-11*") do set "JH=%%~fD"
if not defined JH for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-11*") do set "JH=%%~fD"
if defined JH (
  set "JAVA_HOME=!JH!"
) else (
  echo [WARN] JDK 11 not found. Run setup-jdk.bat first, or install Temurin 11.
)

REM Only set MOVED if the move actually SUCCEEDED — if the file is locked (client
REM running, AV, ACL) we must not later "restore" something we never stashed.
set "MOVED="
if exist "%CREDS%" (
  move /y "%CREDS%" "%STASH%" >nul && set "MOVED=1"
  if defined MOVED (
    echo Jagex auto-login disabled for this session ^(restored on exit^).
  ) else (
    echo [WARN] Could not move credentials aside ^(file in use?^) - Jagex auto-login may still apply.
  )
)

echo.
echo Starting RuneLite with Gustav's Helper - LEGACY login.
echo Type your regular RuneScape username + password on the login screen.
echo (first run downloads dependencies - give it a minute)
echo.
call gradlew.bat run

REM --- always put the Jagex credentials back ---
if defined MOVED (
  if exist "%STASH%" move /y "%STASH%" "%CREDS%" >nul
  echo Jagex credentials restored - play-gustav.bat will auto-login again.
)
echo.
pause
endlocal
