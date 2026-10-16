"""
Prepara la ventana de consola actual (titulo, UTF-8, colores, fuente y tamano)
y ejecuta un script de Python en ella.

    python ventana_consola.py "TITULO" <columnas> <filas> <carpeta> <script.py> [args...]
"""
import ctypes
import os
import runpy
import sys
from ctypes import wintypes

titulo, columnas, filas, carpeta, script, *resto = sys.argv[1:]
k32 = ctypes.windll.kernel32
salida = k32.GetStdHandle(-11)

k32.SetConsoleTitleW(titulo)
k32.SetConsoleOutputCP(65001)                       # UTF-8: acentos y flechas
modo = wintypes.DWORD()
k32.GetConsoleMode(salida, ctypes.byref(modo))
k32.SetConsoleMode(salida, modo.value | 0x0004)     # colores ANSI de werkzeug


class COORD(ctypes.Structure):
    _fields_ = [('X', ctypes.c_short), ('Y', ctypes.c_short)]


class FUENTE(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_ulong), ('nFont', ctypes.c_ulong), ('dwFontSize', COORD),
                ('FontFamily', ctypes.c_uint), ('FontWeight', ctypes.c_uint), ('FaceName', ctypes.c_wchar * 32)]


fuente = FUENTE(ctypes.sizeof(FUENTE), 0, COORD(0, 15), 54, 400, 'Consolas')
k32.SetCurrentConsoleFontEx(salida, False, ctypes.byref(fuente))
os.system(f'mode con: cols={columnas} lines={filas}')
k32.SetConsoleScreenBufferSize(salida, COORD(int(columnas), 5000))   # historial para desplazarse

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.chdir(carpeta)
sys.path.insert(0, carpeta)
sys.argv = [script, *resto]
runpy.run_path(script, run_name='__main__')
