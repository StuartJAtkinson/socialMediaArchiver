@echo off
REM Set up the Python virtual environment and install dependencies for bytebytego-grabber.

REM --- Configuration ---
SET VENV_DIR=.venv
REM Uses whatever `python` is on PATH; the venv is created from that interpreter.

REM --- Setup Virtual Environment ---
echo Creating virtual environment in %VENV_DIR%...
if exist %VENV_DIR% (
    echo Virtual environment already exists.
) else (
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment. Make sure Python is installed and in your PATH.
        exit /b 1
    )
    echo Virtual environment created successfully.
)

REM --- Activate Virtual Environment ---
echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    exit /b 1
)
echo Virtual environment activated.

REM --- Install Dependencies ---
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies. Check requirements.txt and your internet connection.
    exit /b 1
)
echo Dependencies installed successfully.

REM --- Install Playwright Browsers (Facebook browser tiers need this) ---
echo Installing Playwright Chromium browser...
playwright install chromium
if %errorlevel% neq 0 (
    echo WARNING: Playwright browser installation may have encountered issues.
    echo Try again after activating the venv: .\%VENV_DIR%\Scripts\activate ^&^& playwright install chromium
) else (
    echo Playwright browsers installed successfully.
)

echo --- Setup complete! ---
echo You can now run the crawler: run.bat
echo To activate the venv manually, run: %VENV_DIR%\Scripts\activate.bat
pause
