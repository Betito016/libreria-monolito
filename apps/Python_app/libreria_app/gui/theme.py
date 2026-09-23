"""Colores, tipografia y estilos ttk de toda la aplicacion."""
from tkinter import ttk

FUENTE = 'Segoe UI'

COLOR = {
    'fondo': '#f1f5f9',
    'superficie': '#ffffff',
    'barra_lateral': '#1e293b',
    'barra_lateral_activa': '#334155',
    'texto': '#0f172a',
    'texto_suave': '#64748b',
    'texto_claro': '#f8fafc',
    'acento': '#2563eb',
    'acento_oscuro': '#1d4ed8',
    'borde': '#cbd5e1',
    'exito': '#15803d',
    'aviso': '#b45309',
    'error': '#b91c1c',
    'verde': '#16a34a',
    'amarillo': '#eab308',
    'rojo': '#dc2626',
    'gris': '#94a3b8',
}

COLOR_NIVEL = {'verde': COLOR['verde'], 'amarillo': COLOR['amarillo'],
               'rojo': COLOR['rojo'], None: COLOR['gris']}

TEXTO_NIVEL = {'verde': 'Funcionando', 'amarillo': 'Degradado', 'rojo': 'Inaccesible', None: 'Sin comprobar'}

COLOR_MENSAJE = {'info': COLOR['texto_suave'], 'exito': COLOR['exito'],
                 'aviso': COLOR['aviso'], 'error': COLOR['error']}


def aplicar(root) -> None:
    root.configure(bg=COLOR['fondo'])
    estilo = ttk.Style(root)
    estilo.theme_use('clam')

    estilo.configure('.', font=(FUENTE, 10), background=COLOR['fondo'], foreground=COLOR['texto'])
    estilo.configure('TFrame', background=COLOR['fondo'])
    estilo.configure('Card.TFrame', background=COLOR['superficie'], relief='solid', borderwidth=1)
    estilo.configure('TLabel', background=COLOR['fondo'])
    estilo.configure('Card.TLabel', background=COLOR['superficie'])
    estilo.configure('Titulo.TLabel', font=(FUENTE, 18, 'bold'))
    estilo.configure('Subtitulo.TLabel', font=(FUENTE, 12, 'bold'))
    estilo.configure('CardTitulo.TLabel', font=(FUENTE, 12, 'bold'), background=COLOR['superficie'])
    estilo.configure('Suave.TLabel', foreground=COLOR['texto_suave'])
    estilo.configure('CardSuave.TLabel', foreground=COLOR['texto_suave'], background=COLOR['superficie'])

    estilo.configure('TLabelframe', background=COLOR['superficie'], bordercolor=COLOR['borde'])
    estilo.configure('TLabelframe.Label', background=COLOR['superficie'],
                     font=(FUENTE, 10, 'bold'), foreground=COLOR['texto'])

    estilo.configure('TButton', padding=(10, 5))
    estilo.configure('Primario.TButton', background=COLOR['acento'], foreground='white', padding=(12, 6))
    estilo.map('Primario.TButton',
               background=[('disabled', COLOR['gris']), ('active', COLOR['acento_oscuro'])])
    estilo.configure('Peligro.TButton', background=COLOR['error'], foreground='white', padding=(12, 6))
    estilo.map('Peligro.TButton', background=[('disabled', COLOR['gris']), ('active', '#991b1b')])

    estilo.configure('TNotebook', background=COLOR['superficie'])
    estilo.configure('TNotebook.Tab', padding=(14, 6))

    estilo.configure('Treeview', rowheight=24)
    estilo.configure('Treeview.Heading', font=(FUENTE, 10, 'bold'))
