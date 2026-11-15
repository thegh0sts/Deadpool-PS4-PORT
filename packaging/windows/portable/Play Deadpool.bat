@echo off
rem Deadpool PS4 Port without the launcher (Deadpool-PS4-PORT.exe does the same with a window).
rem The dumped game goes in .\CUSA03528 (or set BB_GAME_DIR).
rem The port's in-game menu: the Insert key or L3+R3 on the controller.
setlocal
cd /d "%~dp0"
if "%BB_GAME_DIR%"=="" set "BB_GAME_DIR=%~dp0CUSA03528"
set "PYEXE=python"
set "PYARGS="
if exist "%~dp0python\python.exe" (
    set "PYEXE=%~dp0python\python.exe"
) else (
    where py >nul 2>nul && set "PYEXE=py" && set "PYARGS=-3"
)
"%PYEXE%" %PYARGS% -X utf8 run.py %*
if %errorlevel% neq 0 (
    echo.
    echo The game ended with an error. See last_run.log and README.txt.
    pause
)
