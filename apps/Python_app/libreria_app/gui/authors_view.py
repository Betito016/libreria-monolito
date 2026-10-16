"""
Autores y su relacion con libros (microservicio authors :5005).
Lectura publica con cache en Redis (la respuesta trae X-Cache: HIT | MISS);
crear, modificar y eliminar requieren JWT de administrador.
"""
from tkinter import ttk
from typing import Any, Dict, List

from libreria_app.gui.crud_view import Campo, VistaRecurso


class AuthorsView(VistaRecurso):
    titulo = 'Autores'
    subtitulo = ('GET /authors (público, caché Redis) · POST/PATCH/DELETE /authors/{id} (JWT de administrador) · '
                 'microservicio authors :5005')
    columnas = (('id', 'Id', 45), ('nombre', 'Nombre', 220), ('nacionalidad', 'Nacionalidad', 110),
                ('total_libros', 'Libros', 55))
    clave_lista = 'autores'
    nombre_singular = 'autor'

    def __init__(self, parent, app, panel):
        super().__init__(parent, app, panel)
        if not app.auth.sesion.es_administrador:
            self.mostrar_aviso('Puedes consultar los autores. Crearlos o modificarlos es solo para administradores.')

    def definir_campos(self) -> List[Campo]:
        return [Campo('nombre', 'Nombre'), Campo('nacionalidad', 'Nacionalidad'),
                Campo('biografia', 'Biografía', 'multilinea'),
                Campo('libros', 'Libros (ISBN separados por coma)', 'multilinea')]

    def construir_barra(self, barra) -> None:
        ttk.Label(barra, text='Buscar por nombre:').pack(side='left')
        self.busqueda = ttk.Entry(barra, width=24)
        self.busqueda.pack(side='left', padx=6)
        self.busqueda.bind('<Return>', lambda e: self.recargar())
        ttk.Button(barra, text='Buscar', command=self.recargar).pack(side='left')

    def leer_filtros(self):
        return {'q': self.busqueda.get().strip() or None}

    def llamar_listar(self):
        return self.app.authors.listar(self.filtros.get('q'))

    def llamar_detalle(self, ident):
        return self.app.authors.detalle(ident)

    def llamar_crear(self, datos):
        return self.app.authors.crear(datos)

    def llamar_modificar(self, ident, cambios):
        return self.app.authors.modificar(ident, cambios)

    def llamar_eliminar(self, ident):
        return self.app.authors.eliminar(ident)

    def desde_registro(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {'nombre': r.get('nombre'), 'nacionalidad': r.get('nacionalidad'), 'biografia': r.get('biografia'),
                'libros': ', '.join(l['isbn'] for l in r.get('libros', []))}

    def a_cuerpo(self, valores: Dict[str, Any], crear: bool) -> Dict[str, Any]:
        cuerpo = dict(valores)
        if 'libros' in cuerpo:
            cuerpo['libros'] = [i.strip() for i in cuerpo['libros'].replace('\n', ',').split(',') if i.strip()]
        for campo in ('nacionalidad', 'biografia'):
            if campo in cuerpo and not cuerpo[campo]:
                cuerpo[campo] = None
        if crear:
            cuerpo = {k: v for k, v in cuerpo.items() if v not in ('', None, [])}
        return cuerpo

    def registro_de_respuesta(self, datos):
        return datos.get('autor')

    def descripcion(self, registro):
        libros = len(registro.get('libros', []))
        return f"{registro.get('nombre')} ({libros} libro(s) relacionados)"

    def despues_de_escribir(self, metodo: str) -> None:
        # authors invalido books:* en Redis: el catalogo debe volver a pedirse.
        self.panel.catalogo_modificado()
