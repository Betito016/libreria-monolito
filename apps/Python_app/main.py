"""
Punto de entrada de la aplicacion de escritorio.

    python main.py

La consola muestra el flujo HTTP (logger 'libreria.http') y el manejo del
JWT (logger 'libreria.auth'). Para ver tambien las comprobaciones periodicas
de /health: set LIBRERIA_LOG=DEBUG antes de ejecutar.
"""
import logging
import os
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"Se requiere Python 3.10 o superior (tienes {sys.version.split()[0]}).")

# Permite ejecutar `python main.py` desde cualquier carpeta.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def configurar_logs() -> None:
    if sys.stdout is None:          # pythonw.exe: no hay consola
        return
    try:
        # Acentos y flechas en la consola de Windows aunque se redirija la salida.
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    logging.basicConfig(
        level=getattr(logging, os.getenv('LIBRERIA_LOG', 'INFO').upper(), logging.INFO),
        format='%(asctime)s [%(name)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stdout,
    )
    # urllib3 (dentro de requests) no aporta al flujo que se quiere mostrar.
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)


from libreria_app.gui.app import main  # noqa: E402

if __name__ == '__main__':
    configurar_logs()
    main()
