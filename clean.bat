@echo off
title RegLens AI - Clean for Sharing
color 0C

echo.
echo  ============================================
echo    RegLens AI - Clean Project for Sharing
echo  ============================================
echo.
echo  WILL DELETE:
echo    venv, Module5\venv, Frontend\node_modules
echo    __pycache__, *.pyc, .deps_done, vault.db
echo    Generated reports and uploads
echo.
echo  WILL KEEP:
echo    All source code, trained models, Vosk model
echo    Training data, Frontend dist build, configs
echo.

set /p CONFIRM="Proceed? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
cd /d "%~dp0"

echo [1/7] Stopping servers...
for %%p in (8000 8003 3000) do (
    for /f "tokens=5" %%i in ('netstat -ano ^| findstr ":%%p" ^| findstr "LISTENING" 2^>nul') do (
        taskkill /F /PID %%i >nul 2>&1
    )
)
timeout /t 2 /nobreak >nul
echo       Done.

echo [2/7] Removing venv...
if exist "venv" rmdir /s /q "venv"
if exist "Module5\venv" rmdir /s /q "Module5\venv"
echo       Done.

echo [3/7] Removing node_modules...
if exist "Frontend\node_modules" rmdir /s /q "Frontend\node_modules"
echo       Done.

echo [4/7] Removing __pycache__...
for /d /r . %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d" 2>nul
del /s /q *.pyc >nul 2>&1
echo       Done.

echo [5/7] Removing generated reports...
if exist "Module5\reports" del /q "Module5\reports\*.pdf" "Module5\reports\*.docx" 2>nul
if exist "Module5\uploads" del /q "Module5\uploads\*" 2>nul
if exist "Module4\reports" (
    del /q "Module4\reports\*.json" "Module4\reports\*.csv" "Module4\reports\*.log" "Module4\reports\*.png" 2>nul
    if exist "Module4\reports\evaluation" del /q "Module4\reports\evaluation\*" 2>nul
)
if exist "Module3\backend\reports" del /q "Module3\backend\reports\*.html" "Module3\backend\reports\*.json" "Module3\backend\reports\*.pdf" 2>nul
if exist "Module3\backend\uploads" del /q "Module3\backend\uploads\*" 2>nul
echo       Done.

echo [6/7] Removing temp files...
del /q ".deps_done" 2>nul
del /q "Module1\vault.db" 2>nul
del /q /s ".DS_Store" 2>nul
del /q /s "Thumbs.db" 2>nul
for /d /r . %%d in (.pytest_cache) do if exist "%%d" rmdir /s /q "%%d" 2>nul
for /d /r . %%d in (*.egg-info) do if exist "%%d" rmdir /s /q "%%d" 2>nul
if exist "Module_2\cdsco_data_summarisation\output" rmdir /s /q "Module_2\cdsco_data_summarisation\output" 2>nul
if exist "Module_2\cdsco_data_summarisation\logs" rmdir /s /q "Module_2\cdsco_data_summarisation\logs" 2>nul
if exist "Module4\data\processed" rmdir /s /q "Module4\data\processed" 2>nul
echo       Done.

echo [7/7] Checking kept files...
if exist "Module4\models\severity_classifier.pkl" echo       [KEPT] Module4 trained model
if exist "Module_2\cdsco_data_summarisation\models\vosk-model-en-in-0.5\am" echo       [KEPT] Vosk speech model
if exist "Module4\data\raw" echo       [KEPT] Module4 training data
if exist "Frontend\dist\index.html" echo       [KEPT] Frontend build

echo.
echo  ============================================
echo    Clean complete! Ready to zip and share.
echo    To restore run: start.bat
echo  ============================================
echo.
pause
