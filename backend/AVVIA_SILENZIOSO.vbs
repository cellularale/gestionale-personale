' Avvio PersGest senza finestra console (PowerShell nascosto)
Option Explicit

Dim shell, fso, base, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)

' Usa PowerShell nascosto per avviare Streamlit nella cartella app
cmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ""cd '" & base & "\\app'; python -m streamlit run persgest.py"""

' 0 = finestra nascosta, False = non attendere
shell.Run cmd, 0, False
