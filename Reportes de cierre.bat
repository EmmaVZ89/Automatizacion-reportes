@echo off
rem Reportes de cierre: abre la herramienta (o la reusa si ya esta abierta) y el navegador.
setlocal
cd /d "%~dp0"
set "PY="
where pyw >nul 2>nul && set "PY=pyw -3"
if not defined PY where pythonw >nul 2>nul && set "PY=pythonw"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto sinpython
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if errorlevel 1 goto viejo
)
start "" /B %PY% -m app.arranque
exit /b 0

:sinpython
echo.
echo  No se encontro Python en esta PC, y la herramienta lo necesita.
echo.
echo  Como instalarlo (una sola vez):
echo   1. Entra a https://www.python.org/downloads/windows/ y baja el instalador de Python 3.
echo   2. Al instalarlo, marca la casilla "Add python.exe to PATH" antes de apretar Install.
echo   3. Cuando termine, volve a hacer doble clic en este archivo.
echo.
pause
exit /b 1

:viejo
echo.
echo  La version de Python de esta PC es anterior a la 3.10 y la herramienta necesita 3.10 o posterior.
echo  Instala una version nueva desde https://www.python.org/downloads/windows/ (marcando "Add python.exe to PATH")
echo  y volve a hacer doble clic en este archivo.
echo.
pause
exit /b 1
