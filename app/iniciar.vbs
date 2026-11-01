' Abre Reportes de cierre sin ventana de consola. Lo usa el acceso directo "Reportes de cierre.lnk" (lo crea la
' herramienta al abrirse: ver app\acceso_directo.py). Busca Python igual que "Reportes de cierre.bat"; si falta o es
' anterior a la 3.10, lo explica en un mensaje. app.arranque abre el navegador, o reusa la instancia ya abierta.
Option Explicit

Dim sh, fso, raiz, py, candidatos, c
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
raiz = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = raiz

' Primero los que no abren consola (pyw, pythonw); si no están, py o python con la ventana oculta.
candidatos = Array(Array("pyw", "pyw -3"), Array("pythonw", "pythonw"), Array("py", "py -3"), Array("python", "python"))
py = ""
For Each c In candidatos
  If sh.Run("cmd /c where " & c(0) & " >nul 2>nul", 0, True) = 0 Then
    py = c(1)
    Exit For
  End If
Next

If py = "" Then
  MsgBox "No se encontró Python en esta PC, y la herramienta lo necesita." & vbCrLf & vbCrLf & _
    "Instalalo desde https://www.python.org/downloads/windows/ marcando la casilla ""Add python.exe to PATH"" " & _
    "y volvé a abrir la herramienta.", vbExclamation, "Reportes de cierre"
  WScript.Quit 1
End If

If sh.Run(py & " -c ""import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)""", 0, True) <> 0 Then
  MsgBox "La versión de Python de esta PC es anterior a la 3.10 y la herramienta necesita 3.10 o posterior." & vbCrLf & vbCrLf & _
    "Instalá una versión nueva desde https://www.python.org/downloads/windows/ (marcando ""Add python.exe to PATH"") " & _
    "y volvé a abrir la herramienta.", vbExclamation, "Reportes de cierre"
  WScript.Quit 1
End If

sh.Run py & " -m app.arranque", 0, False
