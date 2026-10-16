"""
Pagos (microservicio pagos :5002). Todo requiere JWT:
    - un cliente paga sus pedidos pendientes y ve sus pagos;
    - un administrador ve todos, reembolsa (el pedido se cancela y el stock
      regresa) y elimina pagos rechazados o reembolsados.
El servicio toma un candado en Redis (lock:order:<id>) mientras registra el
pago, y la Idempotency-Key evita cobrar dos veces el mismo intento.
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List

from libreria_app.api.http_client import ApiResult
from libreria_app.gui.crud_view import SUP, Campo, VistaRecurso
from libreria_app.services.payments_service import METODOS


class PaymentsView(VistaRecurso):
    titulo = 'Pagos'
    subtitulo = 'GET/POST /payments · PATCH/DELETE /payments/{id} · microservicio pagos :5002 · requiere JWT'
    columnas = (('id', 'Pago', 50), ('order_id', 'Pedido', 55), ('monto', 'Monto', 85), ('metodo', 'Método', 95),
                ('estado', 'Estado', 90), ('estado_pedido', 'Pedido está', 85), ('referencia', 'Referencia', 120))
    clave_lista = 'pagos'
    nombre_singular = 'pago'

    def __init__(self, parent, app, panel):
        self.pendientes: Dict[str, Dict[str, Any]] = {}
        super().__init__(parent, app, panel)
        if not app.auth.sesion.es_administrador:
            self.mostrar_aviso('Ves solo tus pagos. Los reembolsos los hace un administrador.')

    def definir_campos(self) -> List[Campo]:
        return [Campo('pedido', 'Pedido pendiente', 'combo', solo_al_crear=True),
                Campo('metodo', 'Método', 'combo', list(METODOS), solo_al_crear=True),
                Campo('monto', 'Monto (total del pedido)', solo_lectura=True),
                Campo('estado', 'Estado del pago', solo_lectura=True)]

    def construir_acciones(self, botones) -> None:
        self.boton_reembolsar = ttk.Button(botones, text='Reembolsar', command=self._reembolsar)
        self.boton_reembolsar.pack(side='left', padx=(0, 6))
        self.campo('pedido').widget.bind('<<ComboboxSelected>>', lambda e: self._pedido_elegido())

    def al_mostrar(self) -> None:
        super().al_mostrar()
        self._cargar_pendientes()

    def _cargar_pendientes(self, seleccionar: int = None) -> None:
        def listo(r):
            if isinstance(r, ApiResult) and r.ok:
                self.pendientes = {f"Pedido {p['id']} — ${p['total']:,.2f}": p for p in r.data['pedidos']}
                self.campo('pedido').widget.configure(values=list(self.pendientes))
                if seleccionar:
                    clave = next((k for k, p in self.pendientes.items() if p['id'] == seleccionar), None)
                    if clave:
                        self.nuevo()
                        self.campo('pedido').escribir(clave)
                        self._pedido_elegido()
        self.app.runner.run(self.app.orders.listar, 'pendiente', al_terminar=listo)

    def preparar_pago(self, pedido: Dict[str, Any]) -> None:
        """Llamado desde Pedidos ("Pagar →")."""
        self._cargar_pendientes(seleccionar=pedido['id'])

    def _pedido_elegido(self) -> None:
        pedido = self.pendientes.get(self.campo('pedido').leer())
        monto = self.campo('monto')
        monto.widget.configure(state='normal')
        monto.escribir(f"{pedido['total']:.2f}" if pedido else '')
        monto.widget.configure(state='disabled')
        if not self.campo('metodo').leer():
            self.campo('metodo').escribir('tarjeta')

    def puede_crear(self) -> bool:
        return True

    def puede_editar(self, registro) -> bool:
        return False                      # un pago no se edita: se reembolsa

    def puede_eliminar(self, registro) -> bool:
        return self.app.auth.sesion.es_administrador and registro is not None and registro.get('estado') != 'aprobado'

    def llamar_listar(self):
        return self.app.payments.listar()

    def llamar_detalle(self, ident):
        return self.app.payments.detalle(ident)

    def llamar_crear(self, datos):
        return self.app.payments.pagar(datos['order_id'], datos['metodo'], datos['monto'])

    def llamar_eliminar(self, ident):
        return self.app.payments.eliminar(ident)

    def valores_fila(self, r: Dict[str, Any]):
        return (r['id'], r['order_id'], f"${r['monto']:,.2f}", r['metodo'], r['estado'], r.get('estado_pedido', ''),
                r.get('referencia', ''))

    def desde_registro(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {'pedido': f"Pedido {r['order_id']}", 'metodo': r['metodo'], 'monto': f"{r['monto']:.2f}",
                'estado': f"{r['estado']} (pedido {r.get('estado_pedido', '')})"}

    def leer_formulario(self) -> Dict[str, Any]:
        pedido = self.pendientes.get(self.campo('pedido').leer())
        if not pedido:
            raise ValueError('Elige un pedido pendiente.')
        metodo = self.campo('metodo').leer()
        if metodo not in METODOS:
            raise ValueError('Elige el método de pago.')
        return {'order_id': pedido['id'], 'metodo': metodo, 'monto': float(pedido['total'])}

    def a_cuerpo(self, valores, crear):
        return valores

    def registro_de_respuesta(self, datos):
        return datos.get('pago')

    def descripcion(self, registro):
        return f"Pedido {registro['order_id']} · ${registro['monto']:,.2f} · {registro['estado']}"

    def nuevo(self) -> None:
        super().nuevo()
        self.boton_guardar.configure(text='Pagar (POST)')

    def registro_mostrado(self, registro) -> None:
        admin = self.app.auth.sesion.es_administrador
        reembolsable = registro is not None and registro.get('estado') == 'aprobado' and registro.get('estado_pedido') == 'pagado'
        self.boton_reembolsar.state(['!disabled'] if admin and reembolsable else ['disabled'])
        if registro is not None:
            self.boton_guardar.state(['disabled'])

    def _reembolsar(self) -> None:
        if not self.original:
            return
        if not messagebox.askyesno('Confirmar reembolso',
                                   f"¿Reembolsar el pago {self.original['id']}?\n\nEl pedido {self.original['order_id']} "
                                   'se cancelará y el stock regresará al catálogo.', icon='warning', parent=self.app):
            return
        cuerpo = {'estado': 'reembolsado'}
        self._enviar('PATCH', cuerpo, lambda i: self.app.payments.reembolsar(i), self.original['id'])

    def despues_de_escribir(self, metodo: str) -> None:
        self._cargar_pendientes()
        self.panel.pedidos_modificados()
