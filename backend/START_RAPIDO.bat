@echo off
REM Start rapido PersGest - avvio diretto (chiude subito la finestra)
cd "%~dp0app"
start "PersGest" /b python -m streamlit run persgest.py
exit
