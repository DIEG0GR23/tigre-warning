import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


load_dotenv()


# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

app = FastAPI(title="Tigre Warning")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(directory="templates")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CRON_SECRET = os.getenv("CRON_SECRET")

TIGRES_SOFASCORE_ID = "1940"
ZONA_MONTERREY = ZoneInfo("America/Monterrey")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json"
}


# --------------------------------------------------
# GOOGLE CALENDAR
# --------------------------------------------------

def crear_enlace_google_calendar(
    local,
    visitante,
    fecha_local,
    estadio
):
    final_partido = fecha_local + timedelta(hours=2)

    parametros = {
        "action": "TEMPLATE",
        "text": f"{local} vs. {visitante}",
        "dates": (
            f"{fecha_local.strftime('%Y%m%dT%H%M%S')}/"
            f"{final_partido.strftime('%Y%m%dT%H%M%S')}"
        ),
        "ctz": "America/Monterrey",
        "location": estadio,
        "details": (
            "Partido de Tigres UANL.\n"
            "Horario sujeto a cambios."
        )
    }

    return (
        "https://calendar.google.com/calendar/render?"
        + urlencode(parametros)
    )


# --------------------------------------------------
# OBTENER ESTADIO
# --------------------------------------------------

def obtener_nombre_estadio(evento):
    venue = evento.get("venue") or {}
    stadium = venue.get("stadium") or {}

    return (
        stadium.get("name")
        or venue.get("name")
        or "Por confirmar"
    )


# --------------------------------------------------
# OBTENER CALENDARIO DE SOFASCORE
# --------------------------------------------------

def obtener_calendario():
    ahora = datetime.now(timezone.utc)
    fecha_final = ahora + timedelta(days=180)

    url = (
    "https://www.sofascore.com/api/v1/team/"
    f"{TIGRES_SOFASCORE_ID}/events/next/0"
)   

    try:
        respuesta = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        calendario = []

        for evento in datos.get("events", []):
            try:
                timestamp = evento.get("startTimestamp")

                if not timestamp:
                    continue

                fecha_utc = datetime.fromtimestamp(
                    timestamp,
                    tz=timezone.utc
                )

                if fecha_utc <= ahora:
                    continue

                if fecha_utc > fecha_final:
                    continue

                equipo_local = evento.get("homeTeam") or {}
                equipo_visitante = evento.get("awayTeam") or {}

                local = equipo_local.get(
                    "name",
                    "Por confirmar"
                )

                visitante = equipo_visitante.get(
                    "name",
                    "Por confirmar"
                )

                id_local = equipo_local.get("id")
                id_visitante = equipo_visitante.get("id")

                logo_local = (
                    "https://img.sofascore.com/api/v1/"
                    f"team/{id_local}/image"
                    if id_local
                    else None
                )

                logo_visitante = (
                    "https://img.sofascore.com/api/v1/"
                    f"team/{id_visitante}/image"
                    if id_visitante
                    else None
                )

                fecha_local = fecha_utc.astimezone(
                    ZONA_MONTERREY
                )

                estadio = obtener_nombre_estadio(evento)

                enlace_calendar = crear_enlace_google_calendar(
                    local,
                    visitante,
                    fecha_local,
                    estadio
                )

                calendario.append({
                    "local": local,
                    "visitante": visitante,
                    "fecha": fecha_local.strftime("%d/%m/%Y"),
                    "hora": fecha_local.strftime("%I:%M %p"),
                    "estadio": estadio,
                    "orden": fecha_utc.isoformat(),
                    "fecha_local_iso": fecha_local.isoformat(),
                    "google_calendar_url": enlace_calendar,
                    "logo_local": logo_local,
                    "logo_visitante": logo_visitante
                })

            except (
                KeyError,
                ValueError,
                TypeError
            ) as error:
                print(
                    "ERROR AL PROCESAR PARTIDO:",
                    repr(error)
                )

        calendario.sort(
            key=lambda partido: partido["orden"]
        )

        print(
            f"PARTIDOS ENCONTRADOS: {len(calendario)}"
        )

        return calendario

    except requests.RequestException as error:
        print(
            "ERROR DE CONEXIÓN CON SOFASCORE:",
            repr(error)
        )
        return []

    except ValueError as error:
        print(
            "ERROR AL LEER JSON DE SOFASCORE:",
            repr(error)
        )
        return []


# --------------------------------------------------
# PRÓXIMO PARTIDO
# --------------------------------------------------

def obtener_proximo_partido():
    calendario = obtener_calendario()

    if calendario:
        return calendario[0]

    return {
        "local": "Tigres UANL",
        "visitante": "Por confirmar",
        "fecha": "Por confirmar",
        "hora": "Por confirmar",
        "estadio": "Por confirmar",
        "google_calendar_url": "#",
        "logo_local": None,
        "logo_visitante": None,
        "fecha_local_iso": None
    }


# --------------------------------------------------
# DISCORD
# --------------------------------------------------

def crear_mensaje_discord(partido):
    return (
        "🐯 **¡Mañana juega Tigres!**\n"
        f"⚽ {partido['local']} vs. "
        f"{partido['visitante']}\n"
        f"📅 {partido['fecha']}\n"
        f"⏰ {partido['hora']}\n"
        f"🏟️ {partido['estadio']}"
    )


def enviar_alerta(mensaje):
    if not WEBHOOK_URL:
        print(
            "No se encontró DISCORD_WEBHOOK_URL."
        )
        return False

    try:
        respuesta = requests.post(
            WEBHOOK_URL,
            json={"content": mensaje},
            timeout=10
        )

        if respuesta.status_code in (200, 204):
            return True

        print(
            "ERROR DE DISCORD:",
            respuesta.status_code,
            respuesta.text
        )

        return False

    except requests.RequestException as error:
        print(
            "ERROR AL CONECTAR CON DISCORD:",
            repr(error)
        )
        return False


# --------------------------------------------------
# PÁGINA PRINCIPAL
# --------------------------------------------------

@app.get("/")
def inicio(request: Request):
    calendario = obtener_calendario()

    if calendario:
        partido = calendario[0]
    else:
        partido = {
            "local": "Tigres UANL",
            "visitante": "Por confirmar",
            "fecha": "Por confirmar",
            "hora": "Por confirmar",
            "estadio": "Por confirmar",
            "google_calendar_url": "#",
            "logo_local": None,
            "logo_visitante": None,
            "fecha_local_iso": None
        }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "partido": partido,
            "calendario": calendario
        }
    )


# --------------------------------------------------
# API DEL CALENDARIO
# --------------------------------------------------

@app.get("/api/calendario")
def api_calendario():
    return obtener_calendario()


# --------------------------------------------------
# PROBAR ALERTA MANUALMENTE
# --------------------------------------------------

@app.get("/probar-alerta")
def probar_alerta():
    partido = obtener_proximo_partido()
    mensaje = crear_mensaje_discord(partido)

    enviado = enviar_alerta(mensaje)

    if enviado:
        print("ALERTA DE PRUEBA ENVIADA.")
    else:
        print("NO SE PUDO ENVIAR LA ALERTA.")

    return RedirectResponse(
        url="/",
        status_code=303
    )


# --------------------------------------------------
# ALERTA AUTOMÁTICA DE VERCEL
# --------------------------------------------------

@app.get("/api/cron/alerta")
def alerta_automatica(
    authorization: str | None = Header(default=None)
):
    if (
        not CRON_SECRET
        or authorization != f"Bearer {CRON_SECRET}"
    ):
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    calendario = obtener_calendario()

    if not calendario:
        return {
            "ok": True,
            "mensaje": "No hay partidos próximos."
        }

    manana = (
        datetime.now(ZONA_MONTERREY).date()
        + timedelta(days=1)
    )

    for partido in calendario:
        fecha_local_iso = partido.get(
            "fecha_local_iso"
        )

        if not fecha_local_iso:
            continue

        fecha_partido = datetime.fromisoformat(
            fecha_local_iso
        ).date()

        if fecha_partido == manana:
            mensaje = crear_mensaje_discord(partido)
            enviado = enviar_alerta(mensaje)

            return {
                "ok": enviado,
                "mensaje": (
                    "Alerta enviada."
                    if enviado
                    else "No se pudo enviar la alerta."
                )
            }

    return {
        "ok": True,
        "mensaje": "Tigres no juega mañana."
    }