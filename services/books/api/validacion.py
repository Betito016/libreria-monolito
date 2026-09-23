"""
Validacion y normalizacion del cuerpo de las peticiones de escritura.

Aqui es donde la diferencia entre los tres metodos se vuelve concreta:

  POST   (crear)      El libro no existe. Se exigen los datos minimos para
                      que tenga sentido; generos e imagenes son opcionales.

  PUT    (reemplazar) Se envia la representacion COMPLETA del libro. Se
                      exigen TODOS los campos, incluidas las listas: lo que
                      no se envie no se conserva. Una lista vacia vacia la
                      relacion (p. ej. "imagenes": [] deja el libro sin
                      imagenes).

  PATCH  (modificar)  Se envia SOLO lo que cambia. Cualquier subconjunto de
                      campos es valido; lo que no se envia queda igual.

En los tres casos el ISBN es inmutable: identifica al recurso en la URL
(/books/{isbn}), y cambiarlo seria crear otro libro, no modificar este.
"""
import math
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

ISBN_RE = re.compile(r'^(\d{9}[\dX]|\d{13})$')

CAMPOS_LIBRO = (
    'isbn', 'titulo', 'autores', 'generos', 'anio', 'precio',
    'stock', 'formato', 'categoria', 'imagenes',
)
OBLIGATORIOS = {
    'crear': ('isbn', 'titulo', 'anio', 'precio', 'stock', 'formato', 'categoria', 'autores'),
    'reemplazar': ('titulo', 'anio', 'precio', 'stock', 'formato', 'categoria',
                   'autores', 'generos', 'imagenes'),
    'modificar': (),
}

PRECIO_MAXIMO = 99_999_999.99   # NUMERIC(10, 2)
ANIO_MINIMO, ANIO_MAXIMO = 1400, 2100


class ValidacionError(Exception):
    def __init__(self, codigo: str, mensaje: str, **extra):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.extra = extra


def normalizar_isbn(valor: Any) -> str:
    """Quita guiones y espacios. Acepta ISBN-10 (con X final) o ISBN-13."""
    isbn = re.sub(r'[\s-]', '', str(valor or '')).upper()
    if not ISBN_RE.match(isbn):
        raise ValidacionError(
            'ERR_ISBN_INVALIDO',
            'El ISBN debe tener 10 caracteres (el último puede ser X) o 13 dígitos.',
            campo_invalido='isbn',
        )
    return isbn


def _texto(valor: Any, campo: str, maximo: int) -> str:
    texto = str(valor if valor is not None else '').strip()
    if not texto:
        raise ValidacionError('ERR_CAMPO_VACIO', f"El campo '{campo}' no puede estar vacio.", campo_invalido=campo)
    if len(texto) > maximo:
        raise ValidacionError(
            'ERR_CAMPO_DEMASIADO_LARGO', f"El campo '{campo}' admite máximo {maximo} caracteres.",
            campo_invalido=campo,
        )
    return texto


def _entero(valor: Any, campo: str, minimo: int, maximo: int) -> int:
    # bool es subclase de int en Python: sin esta comprobacion, `true`
    # pasaria como el numero 1.
    if isinstance(valor, bool):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser un número entero.", campo_invalido=campo)
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser un número entero.", campo_invalido=campo)
    if not minimo <= numero <= maximo:
        raise ValidacionError(
            'ERR_FUERA_DE_RANGO', f"El campo '{campo}' debe estar entre {minimo} y {maximo}.",
            campo_invalido=campo,
        )
    return numero


def _precio(valor: Any) -> float:
    if isinstance(valor, bool):
        raise ValidacionError('ERR_TIPO_INVALIDO', "El campo 'precio' debe ser numerico.", campo_invalido='precio')
    try:
        precio = float(str(valor).strip())
    except (TypeError, ValueError):
        raise ValidacionError('ERR_TIPO_INVALIDO', "El campo 'precio' debe ser numerico.", campo_invalido='precio')
    if math.isnan(precio) or math.isinf(precio) or not 0 <= precio <= PRECIO_MAXIMO:
        raise ValidacionError(
            'ERR_FUERA_DE_RANGO', f"El precio debe estar entre 0 y {PRECIO_MAXIMO:,.2f}.",
            campo_invalido='precio',
        )
    return round(precio, 2)


def _lista_texto(valor: Any, campo: str, maximo: int, minimo_elementos: int) -> List[str]:
    """Acepta una lista o un texto separado por comas (lo segundo facilita
    enviar el campo desde un formulario o desde XML). Elimina duplicados
    sin distinguir mayusculas, conservando el orden."""
    if isinstance(valor, str):
        valor = valor.split(',')
    if not isinstance(valor, list):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser una lista.", campo_invalido=campo)

    resultado, vistos = [], set()
    for elemento in valor:
        texto = str(elemento if elemento is not None else '').strip()
        if not texto:
            continue
        if len(texto) > maximo:
            raise ValidacionError(
                'ERR_CAMPO_DEMASIADO_LARGO',
                f"Cada elemento de '{campo}' admite máximo {maximo} caracteres.", campo_invalido=campo,
            )
        if texto.lower() not in vistos:
            vistos.add(texto.lower())
            resultado.append(texto)

    if len(resultado) < minimo_elementos:
        raise ValidacionError(
            'ERR_CAMPO_VACIO', f"El campo '{campo}' requiere al menos {minimo_elementos} elemento.",
            campo_invalido=campo,
        )
    return resultado


def _imagenes(valor: Any) -> List[Dict[str, Optional[str]]]:
    """Lista de URLs o de objetos {url, texto_alt}. La primera es la principal."""
    if isinstance(valor, str):
        valor = [v for v in valor.split(',') if v.strip()]
    if not isinstance(valor, list):
        raise ValidacionError('ERR_TIPO_INVALIDO', "El campo 'imagenes' debe ser una lista.", campo_invalido='imagenes')

    resultado, vistas = [], set()
    for elemento in valor:
        if isinstance(elemento, dict):
            url = str(elemento.get('url') or '').strip()
            alt = str(elemento.get('texto_alt') or '').strip() or None
        else:
            url, alt = str(elemento or '').strip(), None

        partes = urlparse(url)
        if partes.scheme not in ('http', 'https') or not partes.netloc or len(url) > 2000:
            raise ValidacionError(
                'ERR_URL_INVALIDA', f"La URL de imagen no es válida: '{url}'.", campo_invalido='imagenes'
            )
        if url not in vistas:
            vistas.add(url)
            resultado.append({'url': url, 'texto_alt': alt})
    return resultado


def validar_libro(datos: Dict[str, Any], modo: str, isbn_ruta: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve los campos validados y normalizados.

    modo: 'crear' (POST), 'reemplazar' (PUT) o 'modificar' (PATCH).
    """
    if not isinstance(datos, dict):
        raise ValidacionError('ERR_CUERPO_INVALIDO', 'El cuerpo de la petición debe ser un objeto JSON.')

    desconocidos = [k for k in datos if k not in CAMPOS_LIBRO]
    if desconocidos:
        raise ValidacionError(
            'ERR_CAMPOS_NO_PERMITIDOS',
            f"Campos desconocidos: {', '.join(desconocidos)}.",
            campos_rechazados=desconocidos, campos_permitidos=list(CAMPOS_LIBRO),
        )

    resultado: Dict[str, Any] = {}

    if modo == 'crear':
        if 'isbn' in datos:
            resultado['isbn'] = normalizar_isbn(datos['isbn'])
    elif 'isbn' in datos and normalizar_isbn(datos['isbn']) != isbn_ruta:
        raise ValidacionError(
            'ERR_ISBN_INMUTABLE',
            'El ISBN identifica al libro y no puede modificarse. Para cambiarlo, crea un libro nuevo.',
            campo_invalido='isbn',
        )

    faltantes = [c for c in OBLIGATORIOS[modo] if c not in datos]
    if faltantes:
        mensaje = f"Faltan campos obligatorios: {', '.join(faltantes)}."
        if modo == 'reemplazar':
            mensaje += ' PUT reemplaza el libro completo; para cambiar solo algunos campos usa PATCH.'
        raise ValidacionError('ERR_CAMPOS_OBLIGATORIOS', mensaje, campos_faltantes=faltantes)

    if modo == 'modificar' and not [k for k in datos if k != 'isbn']:
        raise ValidacionError('ERR_SIN_CAMBIOS', 'No se envió ningún campo para modificar.')

    if 'titulo' in datos:
        resultado['titulo'] = _texto(datos['titulo'], 'titulo', 255)
    if 'anio' in datos:
        resultado['anio'] = _entero(datos['anio'], 'anio', ANIO_MINIMO, ANIO_MAXIMO)
    if 'precio' in datos:
        resultado['precio'] = _precio(datos['precio'])
    if 'stock' in datos:
        resultado['stock'] = _entero(datos['stock'], 'stock', 0, 2_147_483_647)
    if 'formato' in datos:
        resultado['formato'] = _texto(datos['formato'], 'formato', 50)
    if 'categoria' in datos:
        resultado['categoria'] = _texto(datos['categoria'], 'categoria', 100)
    if 'autores' in datos:
        resultado['autores'] = _lista_texto(datos['autores'], 'autores', 150, minimo_elementos=1)
    if 'generos' in datos:
        resultado['generos'] = _lista_texto(datos['generos'], 'generos', 80, minimo_elementos=0)
    if 'imagenes' in datos:
        resultado['imagenes'] = _imagenes(datos['imagenes'])

    return resultado
