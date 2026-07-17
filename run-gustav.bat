@echo off
REM Launch a RuneLite dev client with the Gustav's Helper plugin loaded.
REM Auto-locates JDK 11 (portable install in %USERPROFILE%\jdk11, or a system Temurin 11).
setlocal enableextensions enabledelayedexpansion
cd /d "%~dp0"

set "JH="
if exist "%USERPROFILE%\jdk11" for /d %%D in ("%USERPROFILE%\jdk11\jdk-11*") do set "JH=%%~fD"
if not defined JH for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-11*") do set "JH=%%~fD"
if defined JH (
  set "JAVA_HOME=!JH!"
  echo Using JAVA_HOME=!JAVA_HOME!
) else (
  echo [WARN] JDK 11 not found. Run setup-jdk.bat first, or install Temurin 11.
)

echo Starting RuneLite with Gustav's Helper (first run downloads dependencies)...
call gradlew.bat run
endlocal
pause
