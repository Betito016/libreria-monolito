"""
Punto de entrada de la aplicacion de escritorio.

    python main.py
"""
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"Se requiere Python 3.10 o superior (tienes {sys.version.split()[0]}).")

# Permite ejecutar `python main.py` desde cualquier carpeta.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from libreria_app.gui.app import main  # noqa: E402

if __name__ == '__main__':
    main()
