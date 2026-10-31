@echo off
cd /d "%~dp0"
py -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
 echo Falta openpyxl o no se encuentra Python.
 echo Si Python esta instalado, ejecutar: py -m pip install openpyxl
 pause
 exit /b 1
)
py control_cheques.py
pause
