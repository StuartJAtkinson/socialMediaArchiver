@echo off
REM Run the multi-source crawler orchestrator on Windows.
REM Entry point is main.py (subcommands: crawl, status, resume, facebook-login).
REM Usage: run.bat [crawl|status|resume|facebook-login] [main.py options]
REM Examples:
REM   run.bat
REM   run.bat status
REM   run.bat crawl --verbose --debug

SET VENV_DIR=.venv
SET SCRIPTS_DIR=%VENV_DIR%\Scripts
SET PYTHON=%SCRIPTS_DIR%\python.exe

IF NOT EXIST %PYTHON% (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

echo Activating virtual environment and running crawler...
"%PYTHON%" -u main.py %*

IF errorlevel 1 (
    echo.
    echo Crawler exited with error code %errorlevel%
)

pause
