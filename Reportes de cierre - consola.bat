@echo off
rem Reportes de cierre con ventana (para ver mensajes). Argumentos:
rem   (ninguno)   abre la herramienta con consola
rem   pruebas     corre los tests
rem   regresion   compara un motor con el legado: pasar los mismos argumentos que herramientas\regresion_legado.py
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo No se encontro Python. Ver "Reportes de cierre.bat" para instalarlo.
  pause
  exit /b 1
)
if /i "%~1"=="pruebas" (
  %PY% -m unittest discover -s tests -t . -v
  pause
  exit /b %errorlevel%
)
if /i "%~1"=="regresion" (
  shift
  %PY% herramientas\regresion_legado.py %*
  pause
  exit /b %errorlevel%
)
%PY% -m app.arranque --consola
pause
