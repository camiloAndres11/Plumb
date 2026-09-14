"""Contrasenas, tokens, CSRF y rate limit. Sin estado propio: lo que
persiste va a Postgres (tabla pliego.intentos) y lo firmado lleva la
SECRET_KEY.

    hashear("clave") / verificar(hash, "clave")      argon2id
    firmar("id") / leer_firma(valor, max_edad)        cookie de sesion
    nuevo_token()                                     ids de sesion y tokens de un uso
    huella(token)                                     lo que se guarda en la base: su SHA-256
    permitir("login:ip:1.2.3.4", max=10, ventana=900) rate limit por ventana fija
    ip_cliente(request)                               la IP real detras de los proxies de confianza
    validar_contrasena(clave, email)                  politica minima
    nit_valido("900.195.855-1") -> "900195855"        NIT con digito de verificacion DIAN
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from plataforma import db
from plataforma.config import config

_ph = PasswordHasher()   # argon2id, parametros por defecto de la libreria (RFC 9106 low-memory)


class SinSecreto(RuntimeError):
    """Falta SECRET_KEY: no se puede firmar nada."""


# ------------------------------------------------------------- contrasenas
def hashear(clave: str) -> str:
    return _ph.hash(clave)


def verificar(hash_: str, clave: str) -> bool:
    try:
        return _ph.verify(hash_, clave)
    except VerifyMismatchError:
        return False
    except Exception:   # hash corrupto o de otro algoritmo: no autentica
        return False


def validar_contrasena(clave: str, email: str = "") -> str | None:
    """None si sirve; si no, el motivo en espanol para el formulario."""
    if len(clave) < 10:
        return "La contraseña debe tener al menos 10 caracteres."
    if len(clave) > 200:
        return "La contraseña es demasiado larga."
    if email and clave.strip().lower() == email.strip().lower():
        return "La contraseña no puede ser igual al correo."
    if clave.strip().lower() in {"contraseña1", "password12", "1234567890", "qwertyuiop"}:
        return "Esa contraseña es demasiado común."
    return None


# ------------------------------------------------------------------ firmas
def _serializador() -> URLSafeTimedSerializer:
    if not config.secret_key:
        raise SinSecreto("falta SECRET_KEY en el entorno (ver .env.example)")
    return URLSafeTimedSerializer(config.secret_key, salt="pliego.sesion")


def firmar(valor: str) -> str:
    return _serializador().dumps(valor)


def leer_firma(firmado: str | None, max_edad_seg: int) -> str | None:
    if not firmado:
        return None
    try:
        return _serializador().loads(firmado, max_age=max_edad_seg)
    except (BadSignature, SignatureExpired):
        return None


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def huella(token: str) -> str:
    """En la base solo va el hash: un volcado de pliego.sesiones o
    pliego.tokens no debe servir para entrar ni para restablecer nada."""
    return hashlib.sha256(token.encode()).hexdigest()


# -------------------------------------------------------------- rate limit
def ip_cliente(request, proxies: int | None = None) -> str:
    """La IP del cliente. Con `proxies` (config.proxies_confiables) saltos de
    confianza delante, es el salto N-esimo desde la derecha de
    X-Forwarded-For: lo que el cliente ponga a la izquierda no cuenta. Con 0
    proxies se ignora la cabecera y vale la IP del socket."""
    proxies = config.proxies_confiables if proxies is None else proxies
    socket = request.client.host if request.client else "?"
    if proxies <= 0:
        return socket
    saltos = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return saltos[-proxies] if len(saltos) >= proxies else socket


def permitir(clave: str, maximo: int, ventana_seg: int, ahora: datetime | None = None) -> bool:
    """Cuenta el intento y dice si cabe. Ventana deslizante aproximada con
    dos ventanas fijas: lo de la ventana anterior pesa por la fraccion que
    le queda por solapar. Asi 10 intentos al final de una ventana y 10 al
    principio de la siguiente ya no pasan (con la ventana fija pasaban 20
    en segundos)."""
    ahora = ahora or datetime.now(UTC)
    desfase = ahora.timestamp() % ventana_seg
    inicio = ahora - timedelta(seconds=desfase)
    anterior = inicio - timedelta(seconds=ventana_seg)
    fila = db.uno("""
        INSERT INTO pliego.intentos (clave, ventana, n) VALUES (%s, %s, 1)
        ON CONFLICT (clave, ventana) DO UPDATE SET n = pliego.intentos.n + 1
        RETURNING n""", [clave, inicio])
    if not fila:
        return False
    prev = db.uno("SELECT n FROM pliego.intentos WHERE clave = %s AND ventana = %s", [clave, anterior])
    n_prev = prev["n"] if prev else 0
    # Limpieza oportunista de ventanas viejas, para que la tabla no crezca.
    if fila["n"] == 1:
        db.ejecutar("DELETE FROM pliego.intentos WHERE ventana < %s", [ahora - timedelta(days=1)])
    return fila["n"] + n_prev * (1 - desfase / ventana_seg) <= maximo


# --------------------------------------------------------------------- NIT
_PESOS_NIT = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)   # de derecha a izquierda


def digito_verificacion(nit: str) -> int:
    """Algoritmo de la DIAN: suma ponderada modulo 11."""
    suma = sum(int(d) * p for d, p in zip(reversed(nit), _PESOS_NIT))
    r = suma % 11
    return r if r < 2 else 11 - r


def nit_valido(texto: str) -> str | None:
    """'900.195.855-1' -> '900195855' si el DV coincide; sin DV se acepta tal
    cual (muchas empresas lo escriben sin el). None si no es un NIT."""
    s = re.sub(r"[.\s]", "", (texto or "").strip())
    m = re.fullmatch(r"(\d{6,10})(?:-(\d))?", s)
    if not m:
        return None
    nit, dv = m.group(1), m.group(2)
    if dv is not None and int(dv) != digito_verificacion(nit):
        return None
    return nit


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(texto: str) -> str | None:
    s = (texto or "").strip().lower()
    return s if _EMAIL.match(s) and len(s) <= 254 else None
