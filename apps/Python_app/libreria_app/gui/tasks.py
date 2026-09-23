"""
Ejecucion en segundo plano sin congelar la ventana.

Tkinter tiene un solo hilo: si una peticion HTTP se ejecutara en el hilo de
la interfaz, la ventana dejaria de responder hasta que el servidor contestara
(o hasta el timeout, si el servicio esta caido).

Por eso cada peticion corre en un hilo de trabajo, y su resultado vuelve al
hilo de Tkinter a traves de una cola que se revisa cada 50 ms con after().
Los widgets de Tkinter SOLO se tocan desde el hilo principal: nunca desde el
hilo de trabajo.

    boton -> run(funcion) -> [hilo de trabajo] funcion() -> cola
          -> [hilo de Tkinter] _drenar() -> al_terminar(resultado) -> widgets
"""
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional


class BackgroundRunner:

    def __init__(self, root, trabajadores: int = 6):
        self.root = root
        self._cola: queue.Queue = queue.Queue()
        self._ejecutor = ThreadPoolExecutor(max_workers=trabajadores, thread_name_prefix='trabajo')
        self._activo = True
        self.root.after(50, self._drenar)

    def run(self, funcion: Callable[..., Any], *args,
            al_terminar: Optional[Callable[[Any], None]] = None, **kwargs) -> None:
        """Ejecuta funcion(*args) en otro hilo y entrega el resultado (o la
        excepcion, si la hubo) a al_terminar en el hilo de Tkinter."""
        def tarea():
            try:
                return funcion(*args, **kwargs)
            except Exception as exc:   # la interfaz decide que mostrar
                return exc

        futuro = self._ejecutor.submit(tarea)
        if al_terminar:
            futuro.add_done_callback(lambda f: self._cola.put((al_terminar, f.result())))

    def post(self, funcion: Callable[[], None]) -> None:
        """Pide que funcion() se ejecute en el hilo de Tkinter. Seguro de
        llamar desde cualquier hilo."""
        self._cola.put((lambda _r: funcion(), None))

    def _drenar(self) -> None:
        if not self._activo:
            return
        try:
            while True:
                try:
                    callback, resultado = self._cola.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback(resultado)
                except Exception as exc:
                    # Un error en UNA pantalla no debe detener este ciclo: si
                    # se detuviera, ninguna respuesta posterior llegaria a la
                    # interfaz y la app parecería colgada sin mensaje alguno.
                    self.root.report_callback_exception(type(exc), exc, exc.__traceback__)
        finally:
            try:
                self.root.after(50, self._drenar)
            except Exception:
                self._activo = False   # la ventana ya se cerro

    def detener(self) -> None:
        self._activo = False
        self._ejecutor.shutdown(wait=False, cancel_futures=True)
