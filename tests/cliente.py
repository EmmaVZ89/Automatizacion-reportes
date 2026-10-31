"""Cliente HTTP mínimo para probar el server, y arranque de un server de prueba en carpeta temporal."""
import http.client
import json
import socket
import sys
from pathlib import Path

from app import catalogo
from app.servidor import crear_servidor

MOTOR_FALSO = Path(__file__).resolve().parent / 'motor_falso.py'
REPORTE_FALSO = {'codigo': 'falso', 'nombre': 'Reporte falso', 'descripcion': 'Motor de prueba', 'entradas': [], 'parametros': [
    {'clave': 'nota', 'titulo': 'Nota', 'tipo': 'texto', 'default': ''}],
    'salidas': [{'tabla': 'resultado', 'titulo': 'Resultado', 'clave': ['a'], 'archivo': 'Resultado.csv'}], 'requiere': 'stdlib', 'pausas': ['login']}


def servidor_de_prueba(dir_datos, puerto=7390, args_motor=(), **kw):
    s = crear_servidor(dir_datos, puerto_inicial=puerto, intentos=30, probar_venv=False, inactividad_segundos=0, **kw)
    catalogo.registrar_para_pruebas('falso', REPORTE_FALSO, [sys.executable, str(MOTOR_FALSO), *args_motor])
    s.api.modo_pruebas = True
    s.servir_en_hilo()
    return s


class Cliente:
    def __init__(self, servidor):
        self.puerto = servidor.puerto
        self.token = servidor.token

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None, sin_token=False, origin=None, crudo=None):
        con = http.client.HTTPConnection('127.0.0.1', self.puerto, timeout=30)
        cab = {}
        if not sin_token:
            cab['Cookie'] = f'reportes_token={self.token}'
        if origin:
            cab['Origin'] = origin
        datos = None
        if crudo is not None:
            datos = crudo
        elif cuerpo is not None:
            datos = json.dumps(cuerpo).encode('utf-8')
            cab['Content-Type'] = 'application/json'
        cab.update(cabeceras or {})
        con.request(metodo, ruta, body=datos, headers=cab)
        r = con.getresponse()
        contenido = r.read()
        con.close()
        tipo = r.getheader('Content-Type', '')
        if 'json' in tipo:
            try:
                contenido = json.loads(contenido.decode('utf-8'))
            except ValueError:
                pass
        return r.status, dict(r.getheaders()), contenido

    def get(self, ruta, **kw):
        return self.pedir('GET', ruta, **kw)

    def post(self, ruta, cuerpo=None, **kw):
        return self.pedir('POST', ruta, cuerpo, **kw)

    def patch(self, ruta, cuerpo=None, **kw):
        return self.pedir('PATCH', ruta, cuerpo, **kw)

    def delete(self, ruta, **kw):
        return self.pedir('DELETE', ruta, **kw)

    def socket_crudo(self, peticion):
        """Manda bytes tal cual y devuelve lo que llega hasta que el server cierra o pasan 5 s."""
        s = socket.create_connection(('127.0.0.1', self.puerto), timeout=5)
        s.sendall(peticion)
        partes = []
        try:
            while True:
                b = s.recv(65536)
                if not b:
                    break
                partes.append(b)
        except (socket.timeout, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            s.close()
        return b''.join(partes)

    def sse(self, cuantos=1, timeout=20, filtro=None):
        """Abre /api/eventos y devuelve los primeros `cuantos` eventos (tipo, datos) que pasen el filtro."""
        s = socket.create_connection(('127.0.0.1', self.puerto), timeout=timeout)
        s.sendall(f'GET /api/eventos HTTP/1.1\r\nHost: 127.0.0.1:{self.puerto}\r\nCookie: reportes_token={self.token}\r\n\r\n'.encode())
        buffer = b''
        eventos = []
        try:
            while len(eventos) < cuantos:
                b = s.recv(65536)
                if not b:
                    break
                buffer += b
                while b'\n\n' in buffer:
                    bloque, buffer = buffer.split(b'\n\n', 1)
                    lineas = bloque.decode('utf-8').split('\n')
                    tipo = next((l[7:] for l in lineas if l.startswith('event: ')), None)
                    datos = next((l[6:] for l in lineas if l.startswith('data: ')), None)
                    if tipo and (filtro is None or filtro(tipo, datos)):
                        eventos.append((tipo, json.loads(datos) if datos else None))
        finally:
            s.close()
        return eventos
