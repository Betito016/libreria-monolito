"""
Vista base para los recursos de los microservicios (usuarios, autores,
pedidos, pagos): tabla con el listado, formulario de detalle y acciones.

    Seleccionar fila  -> GET /<recurso>/{id}   (llena el formulario)
    Nuevo + Guardar   -> POST                  (todos los campos del formulario)
    Guardar (editar)  -> PATCH                 (SOLO los campos que cambiaron)
    Eliminar          -> DELETE                (con confirmacion previa)

Cada subclase define las columnas, los campos y que servicio llamar. Los
permisos se piden a la subclase (puede_crear / puede_editar / puede_eliminar):
la interfaz deshabilita lo que el rol no permite, pero quien decide de verdad
es el microservicio (responderia 401/403).
"""
import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from libreria_app.api.http_client import ApiResult
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import Mensaje

SUP = COLOR['superficie']


class Campo:
    """Un campo del formulario. tipo: texto | password | multilinea | combo | bool."""

    def __init__(self, clave: str, etiqueta: str, tipo: str = 'texto', opciones: Optional[List[str]] = None,
                 solo_lectura: bool = False, solo_al_crear: bool = False):
        self.clave, self.etiqueta, self.tipo = clave, etiqueta, tipo
        self.opciones = opciones or []
        self.solo_lectura, self.solo_al_crear = solo_lectura, solo_al_crear
        self.widget = None
        self.variable = None

    def leer(self) -> Any:
        if self.tipo == 'bool':
            return bool(self.variable.get())
        if self.tipo == 'multilinea':
            return self.widget.get('1.0', 'end').strip()
        return self.widget.get().strip()

    def escribir(self, valor: Any) -> None:
        if self.tipo == 'bool':
            self.variable.set(bool(valor))
            return
        texto = '' if valor is None else str(valor)
        estado = str(self.widget.cget('state'))
        self.widget.configure(state='normal')
        if self.tipo == 'multilinea':
            self.widget.delete('1.0', 'end')
            self.widget.insert('1.0', texto)
        elif self.tipo == 'combo':
            self.widget.set(texto)
        else:
            self.widget.delete(0, 'end')
            self.widget.insert(0, texto)
        self.widget.configure(state=estado)

    def habilitar(self, si: bool) -> None:
        estado = ('readonly' if self.tipo == 'combo' else 'normal') if si else 'disabled'
        self.widget.configure(state=estado)


class VistaRecurso(ttk.Frame):

    titulo = ''
    subtitulo = ''
    columnas: Tuple[Tuple[str, str, int], ...] = ()
    clave_lista = ''          # clave de la respuesta con la lista (p. ej. 'usuarios')
    clave_id = 'id'
    nombre_singular = 'registro'

    def __init__(self, parent, app, panel):
        super().__init__(parent)
        self.app, self.panel = app, panel
        self.campos: List[Campo] = self.definir_campos()
        self.original: Optional[Dict[str, Any]] = None
        self.filas: Dict[str, Dict[str, Any]] = {}
        self.filtros: Dict[str, Any] = {}
        self.cargado = False

        ttk.Label(self, text=self.titulo, style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text=self.subtitulo, style='Suave.TLabel').pack(anchor='w', pady=(0, 6))
        self.aviso = tk.Label(self, bg='#fef3c7', fg='#78350f', anchor='w', justify='left', padx=12, pady=6)

        barra = self._barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 6))
        self.construir_barra(barra)
        ttk.Button(barra, text='↻ Actualizar', command=self.recargar).pack(side='right')
        self.resumen = ttk.Label(barra, text='', style='Suave.TLabel')
        self.resumen.pack(side='right', padx=10)

        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill='both', expand=True)

        # --- Tabla ---
        tabla = ttk.Frame(cuerpo)
        tabla.pack(side='left', fill='both', expand=True)
        self.arbol = ttk.Treeview(tabla, columns=[c[0] for c in self.columnas], show='headings', selectmode='browse')
        for clave, encabezado, ancho in self.columnas:
            self.arbol.heading(clave, text=encabezado)
            self.arbol.column(clave, width=ancho, anchor='w', stretch=True)
        barra_v = ttk.Scrollbar(tabla, orient='vertical', command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra_v.set)
        self.arbol.pack(side='left', fill='both', expand=True)
        barra_v.pack(side='left', fill='y')
        self.arbol.bind('<<TreeviewSelect>>', self._seleccion)

        # --- Formulario ---
        derecha = ttk.Frame(cuerpo)
        derecha.pack(side='left', fill='both', padx=(12, 0))
        self.marco = ttk.LabelFrame(derecha, text=f'Detalle', padding=12)
        self.marco.pack(fill='x')
        self.marco.columnconfigure(1, weight=1)
        for fila, campo in enumerate(self.campos):
            tk.Label(self.marco, text=campo.etiqueta, bg=SUP, anchor='w').grid(row=fila, column=0, sticky='nw', pady=3, padx=(0, 8))
            if campo.tipo == 'multilinea':
                campo.widget = tk.Text(self.marco, height=3, width=34, font=(theme.FUENTE, 9), relief='solid', bd=1, wrap='word')
            elif campo.tipo == 'combo':
                campo.widget = ttk.Combobox(self.marco, values=campo.opciones, state='readonly', width=32)
            elif campo.tipo == 'bool':
                campo.variable = tk.BooleanVar(value=True)
                campo.widget = ttk.Checkbutton(self.marco, variable=campo.variable)
            else:
                campo.widget = ttk.Entry(self.marco, width=36, show='•' if campo.tipo == 'password' else '')
            campo.widget.grid(row=fila, column=1, sticky='we', pady=3)
        self.marco_extra = tk.Frame(self.marco, bg=SUP)
        self.marco_extra.grid(row=len(self.campos), column=0, columnspan=2, sticky='we')
        self.construir_extra(self.marco_extra)

        self.botones = tk.Frame(self.marco, bg=SUP)
        self.botones.grid(row=len(self.campos) + 1, column=0, columnspan=2, sticky='w', pady=(10, 0))
        self.boton_nuevo = ttk.Button(self.botones, text='+ Nuevo', command=self.nuevo)
        self.boton_guardar = ttk.Button(self.botones, text='Guardar', style='Primario.TButton', command=self._guardar)
        self.boton_eliminar = ttk.Button(self.botones, text='Eliminar', style='Peligro.TButton', command=self._eliminar)
        for b in (self.boton_nuevo, self.boton_guardar, self.boton_eliminar):
            b.pack(side='left', padx=(0, 6))
        # Acciones propias del recurso (cancelar, pagar, reembolsar...) en una
        # segunda fila: en pantallas de 1366 px no caben junto a las comunes.
        self.acciones = tk.Frame(self.marco, bg=SUP)
        self.acciones.grid(row=len(self.campos) + 2, column=0, columnspan=2, sticky='w', pady=(6, 0))
        self.construir_acciones(self.acciones)

        self.mensaje = Mensaje(derecha, ancho=400)
        self.mensaje.pack(fill='x', pady=(8, 0))
        self.peticion = tk.Text(derecha, height=9, width=48, wrap='word', relief='flat', bg='#0f172a', fg='#e2e8f0',
                                font=('Consolas', 8), padx=6, pady=6, state='disabled')
        self.peticion.pack(fill='both', expand=True, pady=(6, 0))
        self.nuevo()

    # ------------------------------------------------------------------
    # Lo que define cada subclase
    # ------------------------------------------------------------------
    def definir_campos(self) -> List[Campo]:
        return []

    def construir_barra(self, barra) -> None:
        pass

    def construir_extra(self, marco) -> None:
        pass

    def construir_acciones(self, botones) -> None:
        pass

    def puede_crear(self) -> bool:
        return self.app.auth.sesion.es_administrador

    def puede_editar(self, registro: Optional[Dict[str, Any]]) -> bool:
        return self.app.auth.sesion.es_administrador

    def puede_eliminar(self, registro: Optional[Dict[str, Any]]) -> bool:
        return self.app.auth.sesion.es_administrador

    def llamar_listar(self) -> ApiResult:
        raise NotImplementedError

    def llamar_detalle(self, ident) -> ApiResult:
        raise NotImplementedError

    def llamar_crear(self, datos) -> ApiResult:
        raise NotImplementedError

    def llamar_modificar(self, ident, cambios) -> ApiResult:
        raise NotImplementedError

    def llamar_eliminar(self, ident) -> ApiResult:
        raise NotImplementedError

    def valores_fila(self, r: Dict[str, Any]) -> Tuple:
        return tuple(r.get(c[0], '') for c in self.columnas)

    def desde_registro(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Valores del formulario a partir de lo que devolvio el servidor."""
        return {c.clave: r.get(c.clave) for c in self.campos}

    def a_cuerpo(self, valores: Dict[str, Any], crear: bool) -> Dict[str, Any]:
        """Convierte el formulario al JSON que espera el microservicio."""
        return {k: v for k, v in valores.items() if v not in ('', None) or not crear}

    def registro_de_respuesta(self, datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        if not self.cargado:
            self.recargar()

    def leer_filtros(self) -> Dict[str, Any]:
        """Valores de la barra de busqueda. Se leen en el hilo de Tkinter:
        llamar_listar corre en otro hilo y no debe tocar widgets."""
        return {}

    def recargar(self) -> None:
        self.mensaje.mostrar('Consultando…')
        self.filtros = self.leer_filtros()
        self.app.runner.run(self.llamar_listar, al_terminar=self._listado)

    def _listado(self, r) -> None:
        if not self.winfo_exists():
            return
        self.cargado = True
        if not isinstance(r, ApiResult):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        if self.app.verificar_sesion(r):
            return
        if not r.ok:
            self.mensaje.mostrar(f"{r.mensaje}" + (f" (HTTP {r.status})" if r.status else ''), 'error')
            return
        self.arbol.delete(*self.arbol.get_children())
        self.filas = {}
        for registro in r.data.get(self.clave_lista, []):
            iid = str(registro[self.clave_id])
            self.filas[iid] = registro
            self.arbol.insert('', 'end', iid=iid, values=self.valores_fila(registro))
        self.resumen.configure(text=f"{r.data.get('total', len(self.filas))} {self.nombre_singular}(s)")
        cache = f" · X-Cache: {r.cabeceras['X-Cache']} (Redis)" if r.cabeceras.get('X-Cache') else ''
        self.mensaje.mostrar(f"{r.metodo} → HTTP {r.status} en {r.duracion_ms} ms{cache}", 'exito')

    def _seleccion(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        ident = seleccion[0]
        self.mensaje.mostrar(f'Consultando el detalle de {ident}…')
        self.app.runner.run(self.llamar_detalle, self.convertir_id(ident), al_terminar=self._detalle)

    def convertir_id(self, ident: str):
        return int(ident) if ident.isdigit() else ident

    def _detalle(self, r) -> None:
        if not isinstance(r, ApiResult):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        if self.app.verificar_sesion(r):
            return
        if not r.ok:
            self.mensaje.mostrar(r.mensaje, 'error')
            return
        self.mostrar_registro(r.data)
        self.mensaje.mostrar(f"GET → HTTP {r.status} en {r.duracion_ms} ms", 'exito')

    def mostrar_registro(self, registro: Dict[str, Any]) -> None:
        self.original = registro
        valores = self.desde_registro(registro)
        for campo in self.campos:
            campo.escribir(valores.get(campo.clave))
            campo.habilitar(self.puede_editar(registro) and not campo.solo_lectura and not campo.solo_al_crear)
        self.marco.configure(text=f"{self.nombre_singular.capitalize()} {registro.get(self.clave_id)}")
        self.boton_guardar.configure(text='Guardar cambios (PATCH)')
        self.boton_guardar.state(['!disabled'] if self.puede_editar(registro) else ['disabled'])
        self.boton_eliminar.state(['!disabled'] if self.puede_eliminar(registro) else ['disabled'])
        self.registro_mostrado(registro)

    def registro_mostrado(self, registro: Optional[Dict[str, Any]]) -> None:
        pass

    def nuevo(self) -> None:
        self.original = None
        for campo in self.campos:
            campo.escribir(True if campo.tipo == 'bool' else '')
            campo.habilitar(self.puede_crear() and not campo.solo_lectura)
        self.marco.configure(text=f'Nuevo {self.nombre_singular}')
        self.boton_guardar.configure(text='Crear (POST)')
        self.boton_guardar.state(['!disabled'] if self.puede_crear() else ['disabled'])
        self.boton_eliminar.state(['disabled'])
        self.arbol.selection_remove(*self.arbol.selection())
        self.registro_mostrado(None)

    # ------------------------------------------------------------------
    def leer_formulario(self) -> Dict[str, Any]:
        return {c.clave: c.leer() for c in self.campos if not c.solo_lectura}

    def _guardar(self) -> None:
        try:
            valores = self.leer_formulario()
        except ValueError as exc:
            self.mensaje.mostrar(str(exc), 'aviso')
            return
        if self.original is None:
            cuerpo = self.a_cuerpo(valores, crear=True)
            self._enviar('POST', cuerpo, self.llamar_crear, cuerpo)
            return
        previo = self.desde_registro(self.original)
        cambios = {k: v for k, v in valores.items()
                   if not self.campo(k).solo_al_crear and v != ('' if previo.get(k) is None else previo.get(k))
                   and not (self.campo(k).tipo == 'password' and v == '')}
        if not cambios:
            self.mensaje.mostrar('No modificaste ningún campo: no hay nada que enviar con PATCH.', 'aviso')
            return
        cuerpo = self.a_cuerpo(cambios, crear=False)
        self._enviar('PATCH', cuerpo, self.llamar_modificar, self.original[self.clave_id], cuerpo)

    def campo(self, clave: str) -> Campo:
        return next(c for c in self.campos if c.clave == clave)

    def _eliminar(self) -> None:
        if not self.original:
            return
        ident = self.original[self.clave_id]
        if not messagebox.askyesno('Confirmar eliminación',
                                   f"¿Eliminar definitivamente {self.nombre_singular} {ident}?\n\n"
                                   f"{self.descripcion(self.original)}\n\nSe enviará DELETE al microservicio.",
                                   icon='warning', parent=self.app):
            self.mensaje.mostrar('Eliminación cancelada: no se envió ninguna petición.')
            return
        self._enviar('DELETE', None, self.llamar_eliminar, ident)

    def descripcion(self, registro: Dict[str, Any]) -> str:
        return ''

    def _enviar(self, metodo: str, cuerpo, funcion: Callable, *args) -> None:
        self.mensaje.mostrar(f"Enviando {metodo}…")

        def listo(r):
            self._resultado(metodo, cuerpo, r)
        self.app.runner.run(funcion, *args, al_terminar=listo)

    def _resultado(self, metodo: str, cuerpo, r) -> None:
        if not isinstance(r, ApiResult):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        self._mostrar_peticion(metodo, cuerpo, r)
        if self.app.verificar_sesion(r):
            return
        if not r.ok:
            self.mensaje.mostrar(f"{r.mensaje} (HTTP {r.status})" if r.status else r.mensaje, 'error')
            return
        self.mensaje.mostrar(f"{r.mensaje} (HTTP {r.status})", 'exito')
        registro = self.registro_de_respuesta(r.data) if metodo != 'DELETE' else None
        if registro:
            self.mostrar_registro(registro)
        else:
            self.nuevo()
        self.despues_de_escribir(metodo)
        self.recargar()

    def despues_de_escribir(self, metodo: str) -> None:
        pass

    def _mostrar_peticion(self, metodo: str, cuerpo, r: ApiResult) -> None:
        token = self.app.api.token
        lineas = [f"{metodo} {r.url.split('?')[0]}",
                  'Authorization: Bearer [JWT PRESENTE]' if token else 'Authorization: (sin JWT)',
                  f"Respuesta: HTTP {r.status or '—'} · {r.duracion_ms} ms", '']
        lineas.append(json.dumps(cuerpo, ensure_ascii=False, indent=2) if cuerpo is not None else 'Sin cuerpo.')
        if not r.ok:
            lineas += ['', f"Resultado: {r.codigo or 'error'} — {r.mensaje}"]
        self.peticion.configure(state='normal')
        self.peticion.delete('1.0', 'end')
        self.peticion.insert('1.0', '\n'.join(lineas))
        self.peticion.configure(state='disabled')

    def mostrar_aviso(self, texto: Optional[str]) -> None:
        if texto:
            self.aviso.configure(text=texto)
            self.aviso.pack(fill='x', pady=(0, 6), before=self._barra)
        else:
            self.aviso.pack_forget()
