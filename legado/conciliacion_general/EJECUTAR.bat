@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Conciliacion general de saldos - version 1.4
echo Mantenga esta ventana abierta hasta ver Resultado.
where py >nul 2>nul
if errorlevel 1 (
  python conciliar.py
) else (
  py -3 conciliar.py
)
if errorlevel 1 (
  echo El proceso no termino. Revise el mensaje anterior.
) else (
  start "" "%~dp0resultados"
)
pause
