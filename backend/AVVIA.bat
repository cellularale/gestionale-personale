@echo off
REM Script avvio PersGest - VERSIONE CORRETTA
REM Usa python -m streamlit invece di streamlit diretto

echo.
echo ========================================
echo    PersGest v7 - Avvio Applicazione
echo ========================================
echo.

REM Vai nella cartella app
cd "%~dp0app"

echo [1/3] Controllo Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRORE: Python non trovato!
    echo.
    echo Installa Python da: https://www.python.org/downloads/
    echo IMPORTANTE: Seleziona "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo     Python OK!

echo.
echo [2/3] Controllo Streamlit...
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo Streamlit non installato!
    echo.
    echo Installazione in corso...
    pip install streamlit pandas openpyxl plotly xlsxwriter python-dateutil
    echo.
    if %errorlevel% neq 0 (
        echo ERRORE: Installazione fallita!
        pause
        exit /b 1
    )
)
echo     Streamlit OK!

echo.
echo [3/3] Avvio PersGest...
echo.
echo App si aprirà nel browser tra pochi secondi...
echo.
echo Per chiudere: premi Ctrl+C in questa finestra
echo.
echo ----------------------------------------
echo.

REM USA PYTHON -M invece di chiamare streamlit diretto
python -m streamlit run persgest.py

echo.
echo ----------------------------------------
echo App terminata
pause
