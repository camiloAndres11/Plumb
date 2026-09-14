"""Envio de correos: SMTP por URL, o consola cuando no hay SMTP.

    correo.enviar(destinatario, asunto, cuerpo_html, cuerpo_texto)

Con SMTP_URL vacio (desarrollo y pruebas) el correo no sale: se imprime en
el log y se guarda en `enviados` (lista en memoria, la vacian las pruebas)
para poder leer el enlace de verificacion sin abrir ningun buzon.

Formato de SMTP_URL:  smtp://usuario:clave@host:587?tls=1
                      smtps://usuario:clave@host:465          (TLS implicito)
Sin SDKs: funciona con Resend, Postmark, SES, Gmail o lo que se contrate.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import parse_qs, unquote, urlparse

from plataforma.config import config

log = logging.getLogger("pliego.correo")
enviados: list[dict] = []   # solo en modo consola


def enviar(destinatario: str, asunto: str, html: str, texto: str) -> None:
    if not config.smtp_url:
        enviados.append({"a": destinatario, "asunto": asunto, "texto": texto, "html": html})
        # warning, no info: sin SMTP el enlace tiene que verse en el log de
        # uvicorn aunque corra con --log-level warning.
        log.warning("correo sin SMTP (no enviado) a %s: %s\n%s", destinatario, asunto, texto)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.correo_remitente, destinatario, asunto
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    u = urlparse(config.smtp_url)
    puerto = u.port or (465 if u.scheme == "smtps" else 587)
    tls = parse_qs(u.query).get("tls", ["1"])[0] not in ("0", "false", "no")
    if u.scheme == "smtps":
        servidor = smtplib.SMTP_SSL(u.hostname, puerto, timeout=20)
    else:
        servidor = smtplib.SMTP(u.hostname, puerto, timeout=20)
    with servidor:
        if u.scheme != "smtps" and tls:
            servidor.starttls()
        if u.username:
            servidor.login(unquote(u.username), unquote(u.password or ""))
        servidor.send_message(msg)


# ------------------------------------------------------------ plantillas
def _plantilla(titulo: str, parrafos: list[str], enlace: str, boton: str) -> tuple[str, str]:
    texto = f"{titulo}\n\n" + "\n\n".join(parrafos) + f"\n\n{boton}: {enlace}\n\n— Pliego"
    ps = "".join(f'<p style="margin:0 0 14px;color:#444;font-size:15px;line-height:1.5">{p}</p>' for p in parrafos)
    html = f"""<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px">
<div style="font-weight:600;font-size:18px;margin-bottom:24px">Pliego.</div>
<h1 style="font-size:22px;font-weight:500;margin:0 0 18px">{titulo}</h1>{ps}
<p style="margin:24px 0"><a href="{enlace}" style="display:inline-block;padding:12px 20px;background:#111;color:#fff;border-radius:10px;text-decoration:none;font-size:15px">{boton}</a></p>
<p style="color:#888;font-size:13px">Si el botón no funciona, copie este enlace: <br><a href="{enlace}" style="color:#888">{enlace}</a></p>
</div>"""
    return html, texto


def verificacion(destinatario: str, nombre: str, enlace: str) -> None:
    html, texto = _plantilla(
        f"Hola, {nombre}. Confirme su correo.",
        ["Con este paso queda activa la cuenta de su empresa en Pliego.",
         "El enlace vale por 24 horas."], enlace, "Confirmar correo")
    enviar(destinatario, "Confirme su correo en Pliego", html, texto)


def restablecer(destinatario: str, nombre: str, enlace: str) -> None:
    html, texto = _plantilla(
        f"Hola, {nombre}. Restablezca su contraseña.",
        ["Alguien pidió cambiar la contraseña de esta cuenta. Si no fue usted, ignore este correo.",
         "El enlace vale por 1 hora y sirve una sola vez."], enlace, "Elegir nueva contraseña")
    enviar(destinatario, "Restablecer contraseña de Pliego", html, texto)


def invitacion(destinatario: str, empresa: str, invita: str, enlace: str) -> None:
    html, texto = _plantilla(
        f"{invita} lo invita a {empresa} en Pliego.",
        ["Pliego es la herramienta con la que su empresa decide a qué licitaciones presentarse y con qué precio.",
         "Cree su usuario con el enlace; vale por 7 días."], enlace, "Aceptar invitación")
    enviar(destinatario, f"Invitación a {empresa} en Pliego", html, texto)
