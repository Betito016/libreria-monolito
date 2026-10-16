"""
Pedidos (microservicio pedidos :5003). Todo requiere JWT:
    - un cliente crea pedidos, ve los suyos y puede cancelarlos mientras estan pendientes;
    - un administrador ve todos, marca enviado/entregado y elimina.
Crear un pedido descuenta stock (el catalogo se vuelve a consultar) y lleva
una Idempotency-Key para que un reintento no lo duplique. El estado 'pagado'
solo lo pone el microservicio pagos.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List

from libreria_app.api.http_client import ApiResult
from libreria_app.gui.crud_view import SUP, Campo, VistaRecurso

ESTADOS = ['pendiente', 'pagado', 'enviado', 'entregado', 'cancelado']


class OrdersView(VistaRecurso):
    titulo = 'Pedidos'
    subtitulo = 'GET/POST /orders · PATCH/DELETE /orders/{id} · microservicio pedidos :5003 · requiere JWT'
    columnas = (('id', 'Pedido', 55), ('estado', 'Estado', 85), ('total', 'Total', 80), ('total_lineas', 'Libros', 50),
                ('user_email', 'Cliente', 190), ('creado_en', 'Fecha', 130))
    clave_lista = 'pedidos'
    nombre_singular = 'pedido'

    def __init__(self, parent, app, panel):
        self.libros: Dict[str, Dict[str, Any]] = {}
        self.lineas: List[Dict[str, Any]] = []
        super().__init__(parent, app, panel)
        if not app.auth.sesion.es_administrador:
            self.mostrar_aviso('Ves solo tus pedidos. Puedes crear pedidos y cancelar los pendientes; '
                               'los envíos los gestiona un administrador.')

    def definir_campos(self) -> List[Campo]:
        return [Campo('direccion_envio', 'Dirección de envío'),
                Campo('estado', 'Estado', 'combo', ESTADOS, solo_lectura=True)]

    def construir_barra(self, barra) -> None:
        ttk.Label(barra, text='Estado:').pack(side='left')
        self.filtro_estado = ttk.Combobox(barra, values=['(todos)'] + ESTADOS, state='readonly', width=12)
        self.filtro_estado.set('(todos)')
        self.filtro_estado.pack(side='left', padx=6)
        self.filtro_estado.bind('<<ComboboxSelected>>', lambda e: self.recargar())

    def construir_extra(self, marco) -> None:
        tk.Label(marco, text='Libros del pedido', bg=SUP, anchor='w').pack(fill='x', pady=(8, 2))
        fila = tk.Frame(marco, bg=SUP)
        fila.pack(fill='x')
        self.selector = ttk.Combobox(fila, state='readonly', width=34)
        self.selector.pack(side='left')
        self.cantidad = ttk.Spinbox(fila, from_=1, to=100, width=4)
        self.cantidad.set(1)
        self.cantidad.pack(side='left', padx=4)
        self.boton_agregar = ttk.Button(fila, text='Agregar', command=self._agregar_linea)
        self.boton_agregar.pack(side='left')
        self.tabla_lineas = ttk.Treeview(marco, columns=('isbn', 'titulo', 'cantidad', 'precio'), show='headings', height=4)
        for clave, texto, ancho in (('isbn', 'ISBN', 100), ('titulo', 'Título', 150), ('cantidad', 'Cant.', 45),
                                    ('precio', 'Precio', 65)):
            self.tabla_lineas.heading(clave, text=texto)
            self.tabla_lineas.column(clave, width=ancho, anchor='w')
        self.tabla_lineas.pack(fill='x', pady=(4, 0))
        self.total = tk.Label(marco, text='', bg=SUP, anchor='e', font=('Segoe UI', 10, 'bold'))
        self.total.pack(fill='x')

    def construir_acciones(self, botones) -> None:
        self.boton_cancelar = ttk.Button(botones, text='Cancelar pedido', command=lambda: self._estado('cancelado'))
        self.boton_enviado = ttk.Button(botones, text='Marcar enviado', command=lambda: self._estado('enviado'))
        self.boton_entregado = ttk.Button(botones, text='Marcar entregado', command=lambda: self._estado('entregado'))
        self.boton_pagar = ttk.Button(botones, text='Pagar →', style='Primario.TButton', command=self._ir_a_pagar)
        for b in (self.boton_cancelar, self.boton_enviado, self.boton_entregado, self.boton_pagar):
            b.pack(side='left', padx=(0, 6))
        self.boton_eliminar.configure(text='Eliminar')

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        super().al_mostrar()
        if not self.libros:
            self.app.runner.run(self.app.books.buscar, {}, 1, 100, al_terminar=self._libros)

    def _libros(self, r) -> None:
        if isinstance(r, ApiResult) and r.ok:
            self.libros = {f"{l['titulo'][:38]} — ${l['precio']:,.2f} (stock {l['stock']}) — {l['isbn']}": l
                           for l in r.data['libros']}
            self.selector.configure(values=list(self.libros))

    def puede_crear(self) -> bool:
        return True

    def _es_mio(self, registro) -> bool:
        return registro is not None and registro.get('user_id') == self.app.auth.sesion.user_id

    def puede_editar(self, registro) -> bool:
        return registro is not None and registro.get('estado') in ('pendiente', 'pagado') and \
            (self.app.auth.sesion.es_administrador or self._es_mio(registro))

    def puede_eliminar(self, registro) -> bool:
        return self.app.auth.sesion.es_administrador and registro is not None and \
            registro.get('estado') in ('pendiente', 'cancelado')

    def leer_filtros(self):
        estado = self.filtro_estado.get()
        return {'estado': None if estado == '(todos)' else estado}

    def llamar_listar(self):
        return self.app.orders.listar(self.filtros.get('estado'))

    def llamar_detalle(self, ident):
        return self.app.orders.detalle(ident)

    def llamar_crear(self, datos):
        return self.app.orders.crear(datos['items'], datos.get('direccion_envio'))

    def llamar_modificar(self, ident, cambios):
        return self.app.orders.modificar(ident, cambios)

    def llamar_eliminar(self, ident):
        return self.app.orders.eliminar(ident)

    def valores_fila(self, r: Dict[str, Any]):
        return (r['id'], r['estado'], f"${r['total']:,.2f}", r.get('total_lineas', len(r.get('lineas', []))),
                r.get('user_email', ''), r.get('creado_en', '')[:16].replace('T', ' '))

    def registro_de_respuesta(self, datos):
        return datos.get('pedido')

    def descripcion(self, registro):
        return f"Estado: {registro.get('estado')} · total ${registro.get('total', 0):,.2f}"

    # ------------------------------------------------------------------
    def _agregar_linea(self) -> None:
        libro = self.libros.get(self.selector.get())
        if not libro:
            self.mensaje.mostrar('Elige un libro del catálogo.', 'aviso')
            return
        try:
            cantidad = int(self.cantidad.get())
        except ValueError:
            cantidad = 0
        if cantidad < 1:
            self.mensaje.mostrar('La cantidad debe ser al menos 1.', 'aviso')
            return
        existente = next((l for l in self.lineas if l['isbn'] == libro['isbn']), None)
        if existente:
            existente['cantidad'] += cantidad
        else:
            self.lineas.append({'isbn': libro['isbn'], 'titulo': libro['titulo'], 'cantidad': cantidad,
                                'precio_unitario': libro['precio']})
        self._pintar_lineas()

    def _pintar_lineas(self) -> None:
        self.tabla_lineas.delete(*self.tabla_lineas.get_children())
        for l in self.lineas:
            self.tabla_lineas.insert('', 'end', values=(l['isbn'], l['titulo'], l['cantidad'],
                                                        f"${float(l['precio_unitario']):,.2f}"))
        total = sum(float(l['precio_unitario']) * l['cantidad'] for l in self.lineas)
        self.total.configure(text=f"Total: ${total:,.2f}" if self.lineas else '')

    def registro_mostrado(self, registro) -> None:
        nuevo = registro is None
        self.lineas = [] if nuevo else list(registro.get('lineas', []))
        self._pintar_lineas()
        for w in (self.selector, self.cantidad, self.boton_agregar):
            w.configure(state=('readonly' if w is self.selector else 'normal') if nuevo else 'disabled')
        estado = None if nuevo else registro.get('estado')
        admin = self.app.auth.sesion.es_administrador
        propio_o_admin = not nuevo and (admin or self._es_mio(registro))
        self.boton_cancelar.state(['!disabled'] if propio_o_admin and estado == 'pendiente' else ['disabled'])
        self.boton_enviado.state(['!disabled'] if admin and estado == 'pagado' else ['disabled'])
        self.boton_entregado.state(['!disabled'] if admin and estado == 'enviado' else ['disabled'])
        self.boton_pagar.state(['!disabled'] if propio_o_admin and estado == 'pendiente' else ['disabled'])

    def leer_formulario(self) -> Dict[str, Any]:
        valores = super().leer_formulario()
        if self.original is None:
            if not self.lineas:
                raise ValueError('Agrega al menos un libro al pedido.')
            valores['items'] = [{'isbn': l['isbn'], 'cantidad': l['cantidad']} for l in self.lineas]
        return valores

    def a_cuerpo(self, valores: Dict[str, Any], crear: bool) -> Dict[str, Any]:
        cuerpo = dict(valores)
        cuerpo.pop('estado', None)
        if not cuerpo.get('direccion_envio'):
            cuerpo['direccion_envio'] = None
            if crear:
                cuerpo.pop('direccion_envio')
        return cuerpo

    def _estado(self, nuevo: str) -> None:
        if self.original:
            cuerpo = {'estado': nuevo}
            self._enviar('PATCH', cuerpo, self.llamar_modificar, self.original['id'], cuerpo)

    def _ir_a_pagar(self) -> None:
        if self.original:
            self.panel.pagar_pedido(self.original)

    def despues_de_escribir(self, metodo: str) -> None:
        # El stock cambio (pedido creado o cancelado): catalogo y selector se recargan.
        self.libros = {}
        self.app.runner.run(self.app.books.buscar, {}, 1, 100, al_terminar=self._libros)
        self.panel.catalogo_modificado()
