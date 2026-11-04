---
trigger: glob
globs: ["app/web/**"]
---

# Interfaz (`app/web/`)

- Antes de cambiar la pantalla, leer `docs/interfaz.md`: piezas comunes, lo que controlan los tests y los criterios de pantalla acordados con quien usa la herramienta.
- Todo se construye con `el()`: nada de `innerHTML`, `eval` ni recursos externos. Los íconos salen del sprite de `index.html`.
- Todo color nuevo es una variable en los dos temas de `estilos.css`, y cada par texto/fondo nuevo va a la lista de `test_contraste_minimo_en_los_pares_declarados`.
- Lo que tarda va por `tareas.correr` y las descargas por `descargar`; las confirmaciones, con `dialogo()`, y los avisos, con `aviso()`. No se arman versiones nuevas de estas piezas.
- Sin saltos de maquetado: un bloque que se vuelve a armar conserva su alto (`conservarAlto`) y lo elegido no cambia el grosor de letra. Se mide con `layout-shift` en Playwright.
- Las animaciones van siempre, también con "reducir movimiento" del sistema (decisión del dueño del repositorio).
- Lenguaje llano, sin la jerga de la regla 4 de `AGENTS.md`; los errores dicen qué pasó y qué hacer.
- Columnas estables todos los meses y validación en el paso donde se elige: un cambio que contradiga un criterio de pantalla de `docs/interfaz.md` se consulta antes.
- Se prueba con `REPORTES_DATOS` apuntando a una carpeta temporal y se apaga la herramienta al terminar. `tests/test_web_estatico.py` tiene que seguir en verde.
