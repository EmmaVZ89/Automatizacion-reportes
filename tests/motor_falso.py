"""Motor de prueba: emite el protocolo completo. --fallar sale con error; --lento se queda 10 s;
--esperar pide una acción manual antes de terminar; --texto-plano imprime líneas sin JSON."""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.reportes._comun import protocolo  # noqa: E402


def main(argv):
    protocolo.paso('Leyendo archivos')
    protocolo.log('Reconocí 3 archivos')
    if '--texto-plano' in argv:
        print('línea suelta sin json', flush=True)
        print('{no es json}', flush=True)
    protocolo.progreso(0.5, '50 filas')
    if '--lento' in argv:
        time.sleep(10)
    if '--fallar' in argv:
        print('Traceback (most recent call last):\n  ValueError: falta la columna Importe', file=sys.stderr, flush=True)
        return 1
    if '--error-propio' in argv:
        protocolo.error('Hay dos archivos de SGA; dejá uno solo.')
        return 1
    if '--esperar' in argv:
        try:
            protocolo.esperar('login', 'Iniciá sesión en Chrome y después apretá Continuar.', 'Continuar')
        except protocolo.Cancelado:
            protocolo.log('cancelado por el usuario')
            return 2
        protocolo.log('continuó')
    if '--trabajo' in argv:
        # Como un motor real: deja resultados.sqlite y una salida en salidas/.
        from app.reportes._comun.salidas import Volcador
        carpeta = Path(argv[argv.index('--trabajo') + 1])
        (carpeta / 'salidas').mkdir(exist_ok=True)
        (carpeta / 'salidas' / 'Resultado.csv').write_text('a;b\n1;x\n2;y\n3;z\n', encoding='utf-8-sig')
        with Volcador(carpeta / 'resultados.sqlite') as v:
            v.tabla('resultado', ['a', 'b'], [['1', 'x'], ['2', 'y'], ['3', 'z']], clave=['a'], titulo='Resultado')
    else:
        protocolo.tabla('resultado', 12)
    protocolo.resumen({'filas': 12, 'estado': 'SIN DIFERENCIAS'})
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
