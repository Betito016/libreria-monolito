"""Widgets reutilizables: semaforo, area con scroll, mensajes e imagenes."""
import io
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR, COLOR_MENSAJE, COLOR_NIVEL


class Semaforo(tk.Canvas):
    """Luz circular de estado: verde, amarillo, rojo o gris (sin comprobar)."""

    def __init__(self, parent, diametro: int = 16, fondo: str = COLOR['fondo']):
        super().__init__(parent, width=diametro + 2, height=diametro + 2,
                         highlightthickness=0, bg=fondo)
        self._luz = self.create_oval(1, 1, diametro + 1, diametro + 1,
                                     fill=COLOR['gris'], outline='#475569')

    def fijar(self, nivel: Optional[str]) -> None:
        self.itemconfigure(self._luz, fill=COLOR_NIVEL.get(nivel, COLOR['gris']))


class AreaDesplazable(ttk.Frame):
    """Contenedor con barra de desplazamiento vertical y rueda del mouse."""

    def __init__(self, parent, fondo: str = COLOR['fondo']):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=fondo)
        barra = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, bg=fondo)
        self._ventana = self.canvas.create_window((0, 0), window=self.interior, anchor='nw')

        self.interior.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self._ventana, width=e.width))
        self.canvas.configure(yscrollcommand=barra.set)

        self.canvas.pack(side='left', fill='both', expand=True)
        barra.pack(side='right', fill='y')

        # La rueda solo desplaza esta area mientras el puntero esta encima.
        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all('<MouseWheel>', self._rueda))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all('<MouseWheel>'))

    def _rueda(self, evento) -> None:
        self.canvas.yview_scroll(int(-evento.delta / 120), 'units')

    def al_inicio(self) -> None:
        self.canvas.yview_moveto(0)


class Mensaje(tk.Label):
    """Etiqueta para avisos al usuario, con color segun el tipo."""

    def __init__(self, parent, fondo: str = COLOR['fondo'], **kwargs):
        super().__init__(parent, text='', bg=fondo, anchor='w', justify='left',
                         font=(theme.FUENTE, 10), wraplength=kwargs.pop('ancho', 700), **kwargs)

    def mostrar(self, texto: str, tipo: str = 'info') -> None:
        self.configure(text=texto, fg=COLOR_MENSAJE.get(tipo, COLOR['texto']))

    def limpiar(self) -> None:
        self.configure(text='')


def formulario(parent, campos: List[Tuple[str, str]], fondo: str = COLOR['superficie'],
               ancho: int = 36, columna: int = 0, fila_inicial: int = 0) -> Dict[str, tk.Entry]:
    """Crea pares etiqueta/entrada en una cuadricula. Devuelve {clave: Entry}."""
    entradas = {}
    for i, (clave, etiqueta) in enumerate(campos):
        tk.Label(parent, text=etiqueta, bg=fondo, anchor='w').grid(
            row=fila_inicial + i, column=columna, sticky='w', padx=(0, 10), pady=4)
        entrada = ttk.Entry(parent, width=ancho, show='•' if 'password' in clave else '')
        entrada.grid(row=fila_inicial + i, column=columna + 1, sticky='we', pady=4)
        entradas[clave] = entrada
    return entradas


# ----------------------------------------------------------------------
# Imagenes
# ----------------------------------------------------------------------
class ImagenesRemotas:
    """Descarga, decodifica y conserva las portadas.

    - La descarga ocurre en segundo plano; el PhotoImage se crea en el hilo
      de Tkinter (los objetos de Tk no se pueden crear desde otros hilos).
    - Se conserva una referencia a cada PhotoImage. Si Python la libera, Tk
      borra la imagen y la portada aparece en blanco.
    - Usa su propia sesion HTTP SIN cookies: las portadas vienen de un
      tercero (Open Library) y no debe recibir la cookie de sesion.
    - Open Library responde con una imagen de 1x1 cuando no tiene portada
      para un ISBN; se detecta y se trata como "imagen no disponible".
    """

    SIN_IMAGEN = 'sin_imagen'
    NO_DISPONIBLE = 'no_disponible'
    OK = 'ok'

    def __init__(self, runner):
        self.runner = runner
        self._http = requests.Session()
        self._originales: Dict[str, Optional[Image.Image]] = {}
        self._fotos: Dict[Tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._marcadores: Dict[Tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._esperando: Dict[str, List[Tuple[int, int, Callable]]] = {}

    def marcador(self, ancho: int, alto: int, texto: str = 'Sin imagen') -> ImageTk.PhotoImage:
        clave = (texto, ancho, alto)
        if clave not in self._marcadores:
            img = Image.new('RGB', (ancho, alto), '#e2e8f0')
            dibujo = ImageDraw.Draw(img)
            dibujo.rectangle([4, 4, ancho - 5, alto - 5], outline='#94a3b8', width=2)
            try:
                fuente = ImageFont.load_default(size=max(11, ancho // 11))
            except TypeError:
                fuente = ImageFont.load_default()
            caja = dibujo.textbbox((0, 0), texto, font=fuente)
            x = (ancho - (caja[2] - caja[0])) // 2
            y = (alto - (caja[3] - caja[1])) // 2
            dibujo.text((x, y), texto, fill='#475569', font=fuente)
            self._marcadores[clave] = ImageTk.PhotoImage(img)
        return self._marcadores[clave]

    def obtener(self, url: Optional[str], ancho: int, alto: int,
                al_listo: Callable[[ImageTk.PhotoImage, str], None]) -> None:
        """al_listo(foto, estado) con estado 'ok', 'sin_imagen' o 'no_disponible'."""
        if not url:
            al_listo(self.marcador(ancho, alto, 'Sin imagen'), self.SIN_IMAGEN)
            return
        if url in self._originales:
            self._entregar(url, ancho, alto, al_listo)
            return
        if url in self._esperando:
            self._esperando[url].append((ancho, alto, al_listo))
            return
        self._esperando[url] = [(ancho, alto, al_listo)]
        self.runner.run(self._descargar, url, al_terminar=lambda img: self._descargada(url, img))

    def _descargar(self, url: str) -> Optional[Image.Image]:
        try:
            respuesta = self._http.get(url, timeout=10)
            respuesta.raise_for_status()
            img = Image.open(io.BytesIO(respuesta.content))
            img.load()
        except Exception:
            return None
        if img.width < 10 or img.height < 10:
            return None
        return img.convert('RGB')

    def _descargada(self, url: str, img) -> None:
        self._originales[url] = img if isinstance(img, Image.Image) else None
        for ancho, alto, al_listo in self._esperando.pop(url, []):
            self._entregar(url, ancho, alto, al_listo)

    def _entregar(self, url: str, ancho: int, alto: int, al_listo: Callable) -> None:
        original = self._originales.get(url)
        if original is None:
            al_listo(self.marcador(ancho, alto, 'Imagen no disponible'), self.NO_DISPONIBLE)
            return
        clave = (url, ancho, alto)
        if clave not in self._fotos:
            lienzo = Image.new('RGB', (ancho, alto), '#f8fafc')
            ajustada = ImageOps.contain(original, (ancho, alto))
            lienzo.paste(ajustada, ((ancho - ajustada.width) // 2, (alto - ajustada.height) // 2))
            self._fotos[clave] = ImageTk.PhotoImage(lienzo)
        al_listo(self._fotos[clave], self.OK)
