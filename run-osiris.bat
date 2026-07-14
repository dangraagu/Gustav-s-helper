@echo off
REM Launch a RuneLite dev client with the Osiris Guide plugin loaded.
REM Requires JDK 11 (run setup-jdk.bat first).
setlocal
cd /d "%~dp0"
echo Starting RuneLite with Osiris Guide (this downloads deps on first run)...
call gradlew.bat run
endlocal
pause
