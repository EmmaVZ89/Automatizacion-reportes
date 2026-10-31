@echo off
setlocal
cd /d "%~dp0"
echo.
echo  Instalacion de la Descarga de facturas
echo  ======================================
echo.
echo  Este paso se hace una sola vez. Prepara, dentro de esta misma carpeta,
echo  los componentes que necesita la descarga de facturas: el control de Chrome
echo  y la lectura de los PDF. Usa el Chrome que ya esta instalado en esta PC;
echo  no instala otro navegador.
echo.
echo  Necesita conexion a internet y suele tardar entre 2 y 5 minutos.
echo  Dejala terminar sin cerrar esta ventana.
echo.
set "PY=py -3"
where py >nul 2>nul
if errorlevel 1 set "PY=python"
echo  Paso 1 de 2: creando la carpeta de componentes (.venv)...
%PY% -m venv .venv
if errorlevel 1 goto error
if not exist ".venv\Scripts\python.exe" goto error
echo  Paso 2 de 2: descargando e instalando los componentes...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-facturas.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" -c "import playwright, pdfplumber"
if errorlevel 1 goto error
echo.
echo  Listo: ya podes usar Descarga de facturas en la herramienta.
echo  Si la herramienta estaba abierta, cerrala y volvela a abrir.
echo.
pause
exit /b 0

:error
echo.
echo  No se completo la instalacion.
echo  Copia el error que aparece arriba (o saca una captura de esta ventana)
echo  y mandaselo a quien te dio la herramienta. Podes volver a intentar
echo  abriendo este mismo archivo otra vez.
echo.
pause
exit /b 1
