@echo off
setlocal enabledelayedexpansion
title RegLens AI - CDSCO Platform
color 0A

echo.
echo  ============================================
echo    RegLens AI - CDSCO Hackathon Platform
echo  ============================================
echo.

:: ── Check prerequisites ──────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Python + Node.js found
echo.

:: ── Kill any running servers ─────────────────────────────────
echo [0/5] Stopping old servers...
call :killport 8000
call :killport 8003
call :killport 3000
timeout /t 1 /nobreak >nul
echo       Done.
echo.

cd /d "%~dp0"

:: ── Create venv if missing ───────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo       Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

:: ── Install Python deps (skip if .deps_done exists) ─────────
echo [1/5] Python dependencies...

if exist ".deps_done" (
    echo       [SKIP] Already installed. Delete .deps_done to force reinstall.
    goto :skip_deps
)

echo       [1a] Main requirements...
pip install -r requirements.txt --quiet 2>nul

echo       [1b] Module 4 ML requirements...
pip install xgboost lightgbm datasketch rapidfuzz pyyaml loguru imbalanced-learn --quiet 2>nul

echo       [1c] Module 2 audio...
pip install vosk==0.3.45 imageio-ffmpeg --quiet 2>nul

echo       [1d] Fixing numpy for spacy compatibility...
pip install "numpy<2.0" --quiet 2>nul

echo       [1e] spaCy model...
python -c "import spacy; spacy.load('en_core_web_sm')" 2>nul
if %errorlevel% neq 0 (
    pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl" --quiet 2>nul
)

echo       [1f] NLTK data...
python -c "import nltk; nltk.download('punkt',quiet=True); nltk.download('punkt_tab',quiet=True); nltk.download('stopwords',quiet=True)" 2>nul

echo       [1g] Verifying critical packages...
python -c "import vosk; print('       vosk OK')" 2>nul
python -c "import xgboost; print('       xgboost OK')" 2>nul
python -c "import lightgbm; print('       lightgbm OK')" 2>nul
python -c "from imageio_ffmpeg import get_ffmpeg_exe; print('       ffmpeg OK')" 2>nul
python -c "import spacy; spacy.load('en_core_web_sm'); print('       spacy OK')" 2>nul

echo done> .deps_done
echo       [OK] Dependencies installed

:skip_deps
call "%~dp0venv\Scripts\activate.bat"
echo.

:: ── Frontend deps (skip if node_modules exists) ──────────────
echo [2/5] Frontend dependencies...
cd /d "%~dp0Frontend"
if exist "node_modules" (
    echo       [SKIP] Already installed
) else (
    echo       Running npm install...
    call npm install --silent 2>nul
    echo       [OK] Installed
)
cd /d "%~dp0"
echo.

:: ── Module 4 model check ─────────────────────────────────────
echo [3/5] Module 4 model...
if exist "%~dp0Module4\models\severity_classifier.pkl" (
    echo       [OK] Trained model found
    goto :skip_train
)
echo       Training SAE classifier...
cd /d "%~dp0Module4"
call "%~dp0venv\Scripts\activate.bat"
python pipeline.py --mode train --input data\raw --output reports 2>nul
if exist "models\severity_classifier.pkl" (
    echo       [OK] Model trained
) else (
    echo       [WARN] Training failed. Module 4 classification may not work.
)
cd /d "%~dp0"
:skip_train
echo.

:: ── Free ports ───────────────────────────────────────────────
echo [4/5] Freeing ports...
call :killport 8000
call :killport 8003
call :killport 3000
timeout /t 2 /nobreak >nul
echo       [OK] Ports freed
echo.

:: ── Start servers ────────────────────────────────────────────
echo [5/5] Starting servers...

cd /d "%~dp0Module1"
start "RegLens-Backend" cmd /k "title RegLens Backend [8000] && color 0B && call "%~dp0venv\Scripts\activate.bat" && python -m uvicorn api:app --port 8000 --host 127.0.0.1"
echo       Backend on port 8000 (M1+M2+M4+M5)

cd /d "%~dp0Module3\backend"
start "RegLens-Module3" cmd /k "title Module 3 [8003] && color 0D && call "%~dp0venv\Scripts\activate.bat" && python -m uvicorn app:app --port 8003 --host 127.0.0.1"
echo       Module 3 on port 8003

echo       Waiting for backends (15s)...
timeout /t 15 /nobreak >nul

cd /d "%~dp0Frontend"
start "RegLens-Frontend" cmd /k "title Frontend [3000] && color 0E && npm run dev"
echo       Frontend on port 3000

timeout /t 4 /nobreak >nul
echo.
echo  ============================================
echo    RegLens AI is running!
echo.
echo    Frontend:  http://localhost:3000
echo    Backend:   http://localhost:8000
echo    Module 3:  http://localhost:8003
echo.
echo    Port 8000: M1 Anonymisation, M2 Summarisation
echo               M4 Classification, M5 Inspection
echo    Port 8003: M3 Completeness and Comparison
echo  ============================================
echo.

start http://localhost:3000
goto :eof

:killport
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%1" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%p >nul 2>&1
)
exit /b 0
