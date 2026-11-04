"""Controles de la documentación: cada reporte tiene sus reglas y sus rules, y nada del repositorio
(público) menciona a la organización, a personas ni direcciones reales."""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPORTES = ['conciliacion_general', 'controles_sga', 'control_mora', 'control_cheques', 'descarga_facturas']
# Palabras que no pueden aparecer en ningún archivo del repo (además de las del archivo local opcional
# tests/palabras_prohibidas.txt, ignorado por git, una por línea).
PROHIBIDAS_BASE = ['sharepoint.com']
JERGA_LEEME = ['token', 'json', 'sqlite', 'puerto', 'servidor', 'subproceso', 'api ', 'backend', 'endpoint']
EXTENSIONES = {'.py', '.md', '.js', '.css', '.html', '.bat', '.txt', '.json'}
CARPETAS_FUERA = {'.git', 'datos', '.venv', '__pycache__', 'tests/_tmp', 'dist', 'vendor', 'docs/superpowers'}


def archivos_del_repo():
    for p in RAIZ.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONES:
            continue
        rel = p.relative_to(RAIZ).as_posix()
        if any(rel.startswith(c + '/') or rel == c for c in CARPETAS_FUERA):
            continue
        if rel in ('tests/palabras_prohibidas.txt', 'tests/test_docs.py'):
            continue
        yield p, rel


class DocsTests(unittest.TestCase):
    def test_cada_reporte_tiene_reglas_y_rules(self):
        for r in REPORTES:
            self.assertTrue((RAIZ / 'docs' / 'reglas' / f'{r}.md').exists(), r)
            rule = RAIZ / '.claude' / 'rules' / 'reportes' / f'{r}.md'
            self.assertTrue(rule.exists(), r)
            texto = rule.read_text(encoding='utf-8')
            self.assertRegex(texto, r'^---\n', 'frontmatter')
            self.assertIn('paths:', texto)
            self.assertIn(f'reportes/{r}', texto)
            ag = RAIZ / '.agent' / 'rules' / f'{r}.md'
            self.assertTrue(ag.exists(), r)
            self.assertIn('trigger: glob', ag.read_text(encoding='utf-8'))
        for nombre in ('LEEME.md', 'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'CHANGELOG.md', 'docs/regresion.md', 'docs/pendientes.md'):
            self.assertTrue((RAIZ / nombre).exists(), nombre)

    def test_reglas_de_interfaz_y_de_servidor(self):
        """Las prácticas viven en docs/ (las leen los tres agentes) y se cargan por ruta con la misma regla en
        .claude y en .agent; AGENTS.md remite a las dos."""
        agents = (RAIZ / 'AGENTS.md').read_text(encoding='utf-8')
        for regla, doc in (('web', 'docs/interfaz.md'), ('servidor', 'docs/servidor.md')):
            self.assertTrue((RAIZ / doc).exists(), doc)
            self.assertIn(doc, agents)
            claude = (RAIZ / '.claude' / 'rules' / f'{regla}.md').read_text(encoding='utf-8')
            agent = (RAIZ / '.agent' / 'rules' / f'{regla}.md').read_text(encoding='utf-8')
            self.assertRegex(claude, r'^---\ndescription: .+\npaths: \[')
            self.assertRegex(agent, r'^---\ntrigger: glob\nglobs: \[')
            self.assertIn(doc, claude)
            self.assertEqual(claude.split('---\n', 2)[2], agent.split('---\n', 2)[2], f'{regla}: el cuerpo difiere')

    def test_sin_datos_de_la_organizacion(self):
        prohibidas = list(PROHIBIDAS_BASE)
        extra = RAIZ / 'tests' / 'palabras_prohibidas.txt'
        if extra.exists():
            prohibidas += [l.strip() for l in extra.read_text(encoding='utf-8').splitlines() if l.strip()]
        for p, rel in archivos_del_repo():
            texto = p.read_text(encoding='utf-8', errors='replace').lower()
            # Marcadores de ejemplo permitidos (no son la dirección real).
            texto = texto.replace('ejemplo.sharepoint.com', '').replace('organizacion.sharepoint.com', '')
            for palabra in prohibidas:
                self.assertNotIn(palabra.lower(), texto, f'{rel} contiene {palabra!r}')
            self.assertNotRegex(texto, r'c:\\users\\(?!tu-usuario|<)', f'{rel} contiene una ruta personal')

    def test_leeme_sin_jerga(self):
        texto = (RAIZ / 'LEEME.md').read_text(encoding='utf-8').lower()
        for palabra in JERGA_LEEME:
            self.assertNotIn(palabra, texto, palabra)
        self.assertLessEqual(len(re.findall(r'\bpython\b', texto)), 10)


if __name__ == '__main__':
    unittest.main()
