"""Operaciones sobre empresas, usuarios y tokens de un uso. Los routers
solo validan formularios y llaman aqui; aqui esta la logica y el SQL.

Decisiones que no son obvias:
  - `registrar` es atomico: empresa + primer admin + token de verificacion
    en una transaccion. Si el email o el NIT ya existen devuelve None y el
    router responde LO MISMO que si hubiera funcionado ("revise su correo"),
    para no revelar que cuentas existen.
  - Los tokens son de un solo uso y con vencimiento: verificar 24 h,
    reset 1 h, invitacion 7 d. Consumir uno marca `usado`; un reset ademas
    cierra las demas sesiones del usuario.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plataforma import correo, db, seguridad
from plataforma.config import config

VENCE = {"verificar": timedelta(hours=24), "reset": timedelta(hours=1), "invitacion": timedelta(days=7)}


# ------------------------------------------------------------- consultas
def usuario_por_email(email: str) -> dict | None:
    return db.uno("SELECT * FROM pliego.usuarios WHERE email = %s", [email.lower()])


def usuario_por_id(uid: int) -> dict | None:
    return db.uno("SELECT * FROM pliego.usuarios WHERE id = %s", [uid])


def empresa_por_id(eid: int) -> dict | None:
    return db.uno("SELECT * FROM pliego.empresas WHERE id = %s", [eid])


def equipo(empresa_id: int) -> list[dict]:
    return db.todos("SELECT id, email, nombre, rol, email_verificado, creado, ultimo_acceso "
                    "FROM pliego.usuarios WHERE empresa_id = %s ORDER BY creado", [empresa_id])


def invitaciones_pendientes(empresa_id: int) -> list[dict]:
    return db.todos("SELECT id, email, rol, expira FROM pliego.tokens WHERE tipo = 'invitacion' "
                    "AND empresa_id = %s AND usado IS NULL AND expira > now() ORDER BY expira", [empresa_id])


# ---------------------------------------------------------------- tokens
def _emitir(tipo: str, cur, **campos) -> str:
    tid = seguridad.nuevo_token()
    cur.execute("INSERT INTO pliego.tokens (id, tipo, usuario_id, empresa_id, email, rol, expira) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [tid, tipo, campos.get("usuario_id"), campos.get("empresa_id"), campos.get("email"),
                 campos.get("rol"), datetime.now(UTC) + VENCE[tipo]])
    return tid


def leer_token(tid: str, tipo: str) -> dict | None:
    """El token si existe, es de ese tipo, no se uso y no vencio."""
    return db.uno("SELECT * FROM pliego.tokens WHERE id = %s AND tipo = %s AND usado IS NULL AND expira > now()",
                  [tid, tipo])


def enlace(ruta: str, tid: str) -> str:
    return config.base_url.rstrip("/") + ruta + "/" + tid


# --------------------------------------------------------------- registro
def registrar(nombre: str, email: str, clave: str, empresa_nombre: str, nit: str) -> dict | None:
    """Crea empresa + admin sin verificar y manda el correo. None si el
    email o el NIT ya estan tomados (el router no lo revela)."""
    email = email.lower()
    if usuario_por_email(email) or db.uno("SELECT 1 FROM pliego.empresas WHERE nit = %s", [nit]):
        return None
    with db.transaccion() as cur:
        cur.execute("INSERT INTO pliego.empresas (nit, nombre) VALUES (%s, %s) RETURNING id", [nit, empresa_nombre])
        empresa_id = cur.fetchone()["id"]
        cur.execute("INSERT INTO pliego.usuarios (empresa_id, email, nombre, hash, rol) VALUES (%s, %s, %s, %s, 'admin') RETURNING id",
                    [empresa_id, email, nombre, seguridad.hashear(clave)])
        usuario_id = cur.fetchone()["id"]
        tid = _emitir("verificar", cur, usuario_id=usuario_id)
    correo.verificacion(email, nombre, enlace("/verificar", tid))
    return {"id": usuario_id, "empresa_id": empresa_id}


def reenviar_verificacion(usuario: dict) -> None:
    if usuario.get("email_verificado"):
        return
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE tipo = 'verificar' AND usuario_id = %s AND usado IS NULL",
                    [usuario["id"]])
        tid = _emitir("verificar", cur, usuario_id=usuario["id"])
    correo.verificacion(usuario["email"], usuario["nombre"], enlace("/verificar", tid))


def verificar(tid: str) -> dict | None:
    """Marca el correo como verificado; devuelve el usuario o None."""
    t = leer_token(tid, "verificar")
    if not t:
        return None
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE id = %s", [tid])
        cur.execute("UPDATE pliego.usuarios SET email_verificado = coalesce(email_verificado, now()) WHERE id = %s",
                    [t["usuario_id"]])
    return usuario_por_id(t["usuario_id"])


# ------------------------------------------------------------------ login
def autenticar(email: str, clave: str) -> dict | None:
    u = usuario_por_email(email)
    if not u or not seguridad.verificar(u["hash"], clave):
        # Se verifica contra un hash de todos modos para que el tiempo de
        # respuesta no delate si el email existe.
        if not u:
            seguridad.verificar(_HASH_SENUELO, clave)
        return None
    return u


_HASH_SENUELO = seguridad.hashear("senuelo-para-tiempo-constante")


# ------------------------------------------------------------------ reset
def pedir_reset(email: str) -> None:
    """Siempre 'ok' hacia afuera; solo manda correo si el usuario existe."""
    u = usuario_por_email(email)
    if not u:
        return
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE tipo = 'reset' AND usuario_id = %s AND usado IS NULL", [u["id"]])
        tid = _emitir("reset", cur, usuario_id=u["id"])
    correo.restablecer(u["email"], u["nombre"], enlace("/restablecer", tid))


def restablecer(tid: str, clave: str) -> dict | None:
    t = leer_token(tid, "reset")
    if not t:
        return None
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE id = %s", [tid])
        cur.execute("UPDATE pliego.usuarios SET hash = %s, email_verificado = coalesce(email_verificado, now()) WHERE id = %s",
                    [seguridad.hashear(clave), t["usuario_id"]])
        cur.execute("DELETE FROM pliego.sesiones WHERE usuario_id = %s", [t["usuario_id"]])
    return usuario_por_id(t["usuario_id"])


def cambiar_contrasena(usuario_id: int, actual: str, nueva: str) -> bool:
    u = usuario_por_id(usuario_id)
    if not u or not seguridad.verificar(u["hash"], actual):
        return False
    db.ejecutar("UPDATE pliego.usuarios SET hash = %s WHERE id = %s", [seguridad.hashear(nueva), usuario_id])
    return True


def cambiar_nombre(usuario_id: int, nombre: str) -> None:
    db.ejecutar("UPDATE pliego.usuarios SET nombre = %s WHERE id = %s", [nombre, usuario_id])


# ----------------------------------------------------------------- equipo
def invitar(empresa: dict, invita: dict, email: str, rol: str) -> str | None:
    """Emite la invitacion y manda el correo. Si ese email ya es usuario (de
    esta o de otra empresa: un email es una sola cuenta) no se emite nada y
    se devuelve None; el router responde IGUAL en ambos casos, para que
    /invitar no sirva para enumerar que correos son clientes."""
    email = email.lower()
    if usuario_por_email(email):
        return None
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE tipo = 'invitacion' AND empresa_id = %s AND email = %s AND usado IS NULL",
                    [empresa["id"], email])
        tid = _emitir("invitacion", cur, empresa_id=empresa["id"], email=email, rol=rol)
    correo.invitacion(email, empresa["nombre"], invita["nombre"], enlace("/invitacion", tid))
    return tid


def aceptar_invitacion(tid: str, nombre: str, clave: str) -> dict | None:
    t = leer_token(tid, "invitacion")
    if not t or usuario_por_email(t["email"]):
        return None
    with db.transaccion() as cur:
        cur.execute("UPDATE pliego.tokens SET usado = now() WHERE id = %s", [tid])
        cur.execute("INSERT INTO pliego.usuarios (empresa_id, email, nombre, hash, rol, email_verificado) "
                    "VALUES (%s, %s, %s, %s, %s, now()) RETURNING id",
                    [t["empresa_id"], t["email"], nombre, seguridad.hashear(clave), t["rol"]])
        uid = cur.fetchone()["id"]
    return usuario_por_id(uid)


def revocar_invitacion(empresa_id: int, tid: str) -> None:
    db.ejecutar("UPDATE pliego.tokens SET usado = now() WHERE id = %s AND empresa_id = %s AND tipo = 'invitacion'",
                [tid, empresa_id])


def cambiar_rol(empresa_id: int, usuario_id: int, rol: str) -> str | None:
    """None si fue bien; si no, el motivo."""
    if rol not in ("admin", "miembro"):
        return "Rol desconocido."
    if rol == "miembro" and _es_ultimo_admin(empresa_id, usuario_id):
        return "La empresa necesita al menos un administrador."
    db.ejecutar("UPDATE pliego.usuarios SET rol = %s WHERE id = %s AND empresa_id = %s", [rol, usuario_id, empresa_id])
    return None


def quitar_usuario(empresa_id: int, usuario_id: int) -> str | None:
    if _es_ultimo_admin(empresa_id, usuario_id):
        return "La empresa necesita al menos un administrador."
    db.ejecutar("DELETE FROM pliego.usuarios WHERE id = %s AND empresa_id = %s", [usuario_id, empresa_id])
    return None


def _es_ultimo_admin(empresa_id: int, usuario_id: int) -> bool:
    fila = db.uno("SELECT count(*) AS n FROM pliego.usuarios WHERE empresa_id = %s AND rol = 'admin' AND id <> %s",
                  [empresa_id, usuario_id])
    u = db.uno("SELECT rol FROM pliego.usuarios WHERE id = %s AND empresa_id = %s", [usuario_id, empresa_id])
    return bool(u and u["rol"] == "admin" and fila and fila["n"] == 0)
