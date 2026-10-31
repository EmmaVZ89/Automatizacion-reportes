# Bibliotecas empaquetadas (vendor)

Puro Python, copiadas de los wheels oficiales de PyPI sin modificaciones. `app/arranque.py` y
`tests/__init__.py` agregan esta carpeta a `sys.path`.

| Paquete | Versión | Licencia | Wheel | SHA-256 del wheel |
|---|---|---|---|---|
| openpyxl | 3.1.5 | MIT | openpyxl-3.1.5-py2.py3-none-any.whl | 5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2 |
| et_xmlfile | 2.0.0 | MIT | et_xmlfile-2.0.0-py3-none-any.whl | 7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa |

Para actualizar: `py -3 -m pip download <paquete>==<versión> --no-deps -d /tmp/x`, verificar el SHA-256
contra PyPI, extraer el wheel y reemplazar la carpeta.
