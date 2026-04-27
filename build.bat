@echo off
setlocal enabledelayedexpansion

echo ================================================
echo   Whisper Subtitle Generator  -  EXE Builder
echo ================================================
echo.

REM ── 1. Check Python ──────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Download Python 3.9+ from https://www.python.org/downloads/
    pause & exit /b 1
)
echo [OK] Python found.

REM ── 2. Install runtime dependencies ──────────────
echo.
echo [1/3] Installing runtime dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo [OK] Dependencies installed.

REM ── 3. Install PyInstaller ────────────────────────
echo.
echo [2/3] Installing PyInstaller...
pip install "pyinstaller>=6.0"
if errorlevel 1 (
    echo ERROR: Could not install PyInstaller.
    pause & exit /b 1
)
echo [OK] PyInstaller ready.

REM ── 4. Build the EXE ─────────────────────────────
echo.
echo [3/3] Building SubtitleGenerator.exe  (this may take several minutes)...
echo.

pyinstaller --onefile --windowed ^
    --name "SubtitleGenerator" ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --collect-all tokenizers ^
    --collect-all tkinterdnd2 ^
    --collect-all huggingface_hub ^
    --hidden-import faster_whisper ^
    --hidden-import ctranslate2 ^
    --hidden-import huggingface_hub ^
    --hidden-import tokenizers ^
    --hidden-import tkinterdnd2 ^
    subtitle_app.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    echo Common fixes:
    echo   - Run: pip install --upgrade pyinstaller
    echo   - Delete the 'build' and 'dist' folders and try again
    pause & exit /b 1
)

echo.
echo ================================================
echo   BUILD COMPLETE
echo   Output:  dist\SubtitleGenerator.exe
echo ================================================
echo.
echo NOTES:
echo   * First launch downloads the AI model from the internet
echo     (tiny ~75 MB  /  base ~145 MB  /  large-v3 ~3 GB)
echo   * Models are cached at %%USERPROFILE%%\.cache\huggingface
echo   * The EXE may take 5-10 seconds to start (self-extraction)
echo   * CPU-only; no GPU required
echo.
pause
