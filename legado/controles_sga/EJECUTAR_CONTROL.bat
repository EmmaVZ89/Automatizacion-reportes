@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "ENTRADA" mkdir "ENTRADA"
if not exist "SALIDA" mkdir "SALIDA"
echo CONTROLES SGA - VERSION 1.5
echo Pega un unico reporte SGA .xlsx en ENTRADA antes de ejecutar.
echo.
where py >nul 2>nul
if errorlevel 1 goto usar_python
py -3 control_sga.py
goto fin
:usar_python
python control_sga.py
:fin
echo.
pause
