"""
Microservicio authors: lectura publica con cache compartida e invalidacion,
escrituras con JWT de administrador. Repositorio en memoria y fakeredis.
"""
import os
import sys
import time
import uuid
from pathlib import Path

import fakeredis
import jwt
import pytest

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
os.environ.update(JWT_SECRET_KEY=CLAVE, REDIS_URL='redis://:x@127.0.0.1:6379/0')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as authors  # noqa: E402
from libreria_common.validacion import Conflicto, NoEncontrado  # noqa: E402


class RepoFalso:
    def __init__(self):
        self.autores = {1: {'id': 1, 'nombre': 'Thomas Erl', 'libros': [{'isbn': '9780134092669'}]}}
        self.consultas = 0

    def listar(self, nombre, page, size):
        self.consultas += 1
        return {'total': len(self.autores), 'autores': list(self.autores.values())}

    def obtener(self, i):
        self.consultas += 1
        if i not in self.autores:
            raise NoEncontrado('no')
        return self.autores[i]

    def crear(self, d):
        i = max(self.autores) + 1
        self.autores[i] = {'id': i, 'nombre': d['nombre'], 'libros': []}
        return self.autores[i]

    def modificar(self, i, d):
        self.obtener(i).update({k: v for k, v in d.items() if k != 'libros'})
        return self.autores[i]

    def eliminar(self, i):
        if self.obtener(i)['libros']:
            raise Conflicto('ERR_AUTOR_CON_LIBROS', 'tiene libros')
        return self.autores.pop(i)


@pytest.fixture
def cliente(monkeypatch):
    servidor = fakeredis.FakeServer()
    redis = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    monkeypatch.setattr(authors.servicio.redis, '_cliente', redis)
    authors.servicio.redis._abierto_hasta = 0
    repo = RepoFalso()
    monkeypatch.setattr(authors, 'repo', repo)
    authors.app.testing = True
    c = authors.app.test_client()
    c.redis, c.repo, c.servidor = redis, repo, servidor
    return c


def bearer(role_id=1):
    ahora = int(time.time())
    t = jwt.encode({'sub': 'u', 'user_id': 'u', 'email': 'a@b.c', 'role_id': role_id, 'jti': uuid.uuid4().hex,
                    'typ': 'access', 'iss': 'libreria-login', 'iat': ahora, 'exp': ahora + 1200}, CLAVE, algorithm='HS256')
    return {'Authorization': f'Bearer {t}'}


def test_lectura_publica_con_cache(cliente):
    r1, r2 = cliente.get('/authors?format=json'), cliente.get('/authors?format=json')
    assert (r1.headers['X-Cache'], r2.headers['X-Cache']) == ('MISS', 'HIT')
    assert cliente.repo.consultas == 1
    d1, d2 = cliente.get('/authors/1?format=json'), cliente.get('/authors/1?format=json')
    assert (d1.headers['X-Cache'], d2.headers['X-Cache']) == ('MISS', 'HIT')


def test_escrituras_requieren_admin(cliente):
    assert cliente.post('/authors?format=json', json={'nombre': 'X'}).status_code == 401
    assert cliente.post('/authors?format=json', json={'nombre': 'X'}, headers=bearer(2)).status_code == 403
    assert cliente.post('/authors?format=json', json={'nombre': 'X'}, headers=bearer()).status_code == 201


def test_escritura_invalida_cache_de_autores_y_de_libros(cliente):
    cliente.get('/authors?format=json')
    cliente.redis.set('books:list:todos', '{}'); cliente.redis.set('books:9780134092669', '{}')
    r = cliente.patch('/authors/1?format=json', json={'nombre': 'Thomas Erl (ed.)'}, headers=bearer())
    assert r.status_code == 200
    assert not list(cliente.redis.scan_iter('authors:*')) and not list(cliente.redis.scan_iter('books:*'))


def test_eliminar_autor_con_libros_409(cliente):
    assert cliente.delete('/authors/1?format=json', headers=bearer()).status_code == 409


def test_validacion(cliente):
    assert cliente.post('/authors?format=json', json={}, headers=bearer()).status_code == 400
    assert cliente.post('/authors?format=json', json={'nombre': 'X', 'edad': 3}, headers=bearer()).status_code == 400
    assert cliente.get('/authors/abc?format=json').status_code == 400


def test_redis_caido_lectura_ok_escritura_503(cliente):
    cliente.servidor.connected = False
    assert cliente.get('/authors?format=json').status_code == 200
    assert cliente.post('/authors?format=json', json={'nombre': 'X'}, headers=bearer()).status_code == 503
