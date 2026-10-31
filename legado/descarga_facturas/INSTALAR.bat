@echo off
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Instalacion terminada. Ahora podes abrir EJECUTAR.bat.
pause
exit /b 0
:error
echo No se completo la instalacion. Copia o captura el error que aparece arriba.
pause
exit /b 1
