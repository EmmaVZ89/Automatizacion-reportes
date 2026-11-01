"""Controles estáticos de la interfaz: los dos temas definen las mismas variables, los pares de
contraste declarados cumplen 4,5:1, no se usa innerHTML y los textos no tienen jerga."""
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / 'app' / 'web'
JERGA = ['sqlite', 'json', 'token', 'backend', 'endpoint', 'subproceso', 'stdout', 'localhost', 'puerto ', 'debug']


def variables_de(css, tema):
    bloque = re.search(r':root\[data-tema="%s"\]\s*\{(.*?)\}' % tema, css, re.S).group(1)
    return dict(re.findall(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', bloque))


def luminancia(hexa):
    hexa = hexa.lstrip('#')
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contraste(a, b):
    la, lb = luminancia(a), luminancia(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


class WebEstaticaTests(unittest.TestCase):
    def setUp(self):
        self.css = (WEB / 'estilos.css').read_text(encoding='utf-8')
        self.js = (WEB / 'app.js').read_text(encoding='utf-8')
        self.html = (WEB / 'index.html').read_text(encoding='utf-8')

    def test_index_tiene_dos_temas_y_variables_iguales(self):
        claro = variables_de(self.css, 'claro')
        oscuro = variables_de(self.css, 'oscuro')
        self.assertGreater(len(claro), 15)
        self.assertEqual(set(claro), set(oscuro))
        self.assertIn('data-tema', self.html)
        self.assertIn('btn-tema', self.html)

    def test_contraste_minimo_en_los_pares_declarados(self):
        for tema in ('claro', 'oscuro'):
            v = variables_de(self.css, tema)
            pares = [('--text', '--bg'), ('--text', '--panel'), ('--text', '--panel2'), ('--text2', '--panel'), ('--muted', '--panel'), ('--muted', '--bg'), ('--muted', '--panel2'),
                     ('--accent', '--panel'), ('--accent', '--bg'), ('--accent', '--accent-suave'), ('--text', '--accent-suave'), ('--accent-btn-text', '--accent-btn'), ('--accent-btn-text', '--accent-hover'),
                     ('--marca-texto', '--marca'), ('--marca-texto', '--marca-2'), ('--marca-activa-texto', '--marca-activa'),
                     ('--ok', '--panel'), ('--warn', '--panel'), ('--error', '--panel'), ('--ok', '--ok-suave'), ('--warn', '--warn-suave'), ('--error', '--error-suave'), ('--text', '--warn-suave'),
                     ('--naranja-celda-texto', '--naranja-celda')]
            for r in ('conciliacion', 'sga', 'mora', 'cheques', 'facturas'):
                pares += [(f'--r-{r}', f'--r-{r}-suave'), (f'--r-{r}', '--panel')]
            for texto, fondo in pares:
                c = contraste(v[texto].strip(), v[fondo].strip())
                self.assertGreaterEqual(c, 4.5, f'{tema}: {texto} sobre {fondo} = {c:.2f}')

    def test_no_hay_innerhtml_ni_eval(self):
        self.assertNotRegex(self.js, r'\.innerHTML\s*=')
        self.assertNotRegex(self.js, r'\binsertAdjacentHTML\b')
        self.assertNotRegex(self.js, r'\beval\(')
        self.assertNotRegex(self.js, r'new Function\(')
        self.assertNotIn('document.write', self.js)

    def test_sin_recursos_externos(self):
        for texto in (self.html, self.css, self.js):
            self.assertNotRegex(texto, r'https?://(?!127\.0\.0\.1|www\.w3\.org)')

    def test_textos_sin_jerga(self):
        cadenas = re.findall(r"'([^'\\]*(?:\\.[^'\\]*)*)'", self.js)
        visibles = [c for c in cadenas if len(c) > 25 and ' ' in c and not c.startswith(('/', '#', '--'))]
        self.assertGreater(len(visibles), 30)
        for c in visibles:
            for palabra in JERGA:
                self.assertNotIn(palabra, c.lower(), f'jerga en: {c}')

    def test_las_animaciones_no_dependen_de_reducir_movimiento(self):
        # Decisión del dueño del repositorio: las animaciones van siempre, aunque Windows o el navegador tengan
        # "reducir movimiento" activado.
        for texto in (self.css, self.js, self.html):
            self.assertNotIn('prefers-reduced-motion', texto)
            self.assertNotRegex(texto, r'matchMedia\([^)]*reduce')

    def test_sin_saltos_al_cambiar_de_contenido(self):
        # La barra de desplazamiento siempre reservada (si aparece o desaparece, nada se corre a los costados), la
        # grilla con alto fijo, los desplegables animados y la tabla elegida sin negrita (la negrita ensancha el texto).
        self.assertRegex(self.css, r'html\s*\{[^}]*scrollbar-gutter:\s*stable')
        self.assertRegex(self.css, r'\.marco-grilla\s*\{\s*height:')
        self.assertIn('details::details-content', self.css)
        activa = re.search(r'\.lista-tablas button\.activa\s*\{([^}]*)\}', self.css).group(1)
        self.assertNotIn('font-weight', activa)
        # la grilla conserva su alto mientras arma la tabla nueva; la vista toma su ancho junto con el contenido nuevo
        self.assertIn('const soltar = conservarAlto(cont);', self.js)
        self.assertNotIn("$('#vista').classList.toggle('ancha'", self.js)


if __name__ == '__main__':
    unittest.main()
