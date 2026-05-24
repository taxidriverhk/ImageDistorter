@echo off
setlocal

set VENV=.venv
set ENTRY=main.py
set APP_NAME=ImageDistorter

:: ── Virtual environment ──────────────────────────────────────────────────────
if not exist "%VENV%\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv %VENV%
    if errorlevel 1 ( echo ERROR: Failed to create venv. & exit /b 1 )
)

call %VENV%\Scripts\activate.bat

:: ── Dependencies ─────────────────────────────────────────────────────────────
echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed. & exit /b 1 )

pip install -q pyinstaller
if errorlevel 1 ( echo ERROR: Failed to install PyInstaller. & exit /b 1 )

:: ── Icon ─────────────────────────────────────────────────────────────────────
if not exist icon.ico (
    echo Generating icon...
    python make_icon.py
    if errorlevel 1 ( echo ERROR: Icon generation failed. & exit /b 1 )
)

:: ── Build ────────────────────────────────────────────────────────────────────
echo Building %APP_NAME%.exe...
pyinstaller --onefile --windowed --name %APP_NAME% --icon=icon.ico %ENTRY%
if errorlevel 1 ( echo ERROR: PyInstaller build failed. & exit /b 1 )

echo.
echo Build complete: dist\%APP_NAME%.exe
endlocal
