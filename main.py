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
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

ZONA_MONTERREY = ZoneInfo("America/Monterrey")

API_FOOTBALL_URL = (
    "https://v3.football.api-sports.io"
)

HEADERS_API = {
    "x-apisports-key": API_FOOTBALL_KEY or ""
}

# Guarda el ID mientras la aplicación esté activa.
TIGRES_ID_CACHE = None


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
# PETICIONES A API-FOOTBALL
# --------------------------------------------------

def solicitar_api(ruta, parametros=None):
    if not API_FOOTBALL_KEY:
        print(
            "ERROR: No se encontró API_FOOTBALL_KEY."
        )
        return None

    url = API_FOOTBALL_URL + ruta

    try:
        respuesta = requests.get(
            url,
            headers=HEADERS_API,
            params=parametros,
            timeout=15
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        errores = datos.get("errors")

        if errores:
            print(
                "ERROR DE API-FOOTBALL:",
                errores
            )
            return None

        return datos

    except requests.RequestException as error:
        print(
            "ERROR DE CONEXIÓN CON API-FOOTBALL:",
            repr(error)
        )
        return None

    except ValueError as error:
        print(
            "ERROR AL LEER API-FOOTBALL:",
            repr(error)
        )
        return None


# --------------------------------------------------
# BUSCAR ID DE TIGRES
# --------------------------------------------------

def obtener_id_tigres():
    global TIGRES_ID_CACHE

    if TIGRES_ID_CACHE:
        return TIGRES_ID_CACHE

    datos = solicitar_api(
        "/teams",
        {
            "search": "Tigres UANL"
        }
    )

    if not datos:
        return None

    resultados = datos.get("response", [])

    for resultado in resultados:
        equipo = resultado.get("team", {})

        nombre = equipo.get("name", "")
        pais = equipo.get("country", "")

        if (
            "tigres" in nombre.lower()
            and pais.lower() == "mexico"
        ):
            TIGRES_ID_CACHE = equipo.get("id")

            print(
                "ID DE TIGRES ENCONTRADO:",
                TIGRES_ID_CACHE
            )

            return TIGRES_ID_CACHE

    print(
        "ERROR: No se encontró Tigres UANL "
        "en API-Football."
    )

    return None


# --------------------------------------------------
# OBTENER CALENDARIO
# --------------------------------------------------
def obtener_calendario():
    ahora = datetime.now(ZONA_MONTERREY)

    partidos = [
        {
            "local": "Tigres UANL",
            "visitante": "Puebla",
            "fecha_iso": "2026-09-26T19:00:00-06:00",
            "estadio": "Estadio Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1296.png",
        },
        {
            "local": "Tigres UANL",
            "visitante": "Toluca",
            "fecha_iso": "2026-10-09T21:00:00-06:00",
            "estadio": "Estadio Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1286.png",
        },
        {
            "local": "Guadalajara",
            "visitante": "Tigres UANL",
            "fecha_iso": "2026-10-17T17:07:00-06:00",
            "estadio": "Estadio Akron",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1283.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
        },
        {
            "local": "Tigres UANL",
            "visitante": "León",
            "fecha_iso": "2026-10-20T21:00:00-06:00",
            "estadio": "Estadio Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1293.png",
        },
        {
            "local": "Pumas UNAM",
            "visitante": "Tigres UANL",
            "fecha_iso": "2026-10-24T21:00:00-06:00",
            "estadio": "Estadio Olímpico Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1297.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
        },
        {
            "local": "Pachuca",
            "visitante": "Tigres UANL",
            "fecha_iso": "2026-10-31T17:00:00-06:00",
            "estadio": "Estadio Hidalgo",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1295.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
        },
        {
            "local": "Tigres UANL",
            "visitante": "Cruz Azul",
            "fecha_iso": "2026-11-07T17:00:00-06:00",
            "estadio": "Estadio Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/853.png",
        },
        {
            "local": "Tigres UANL",
            "visitante": "América",
            "fecha_iso": "2026-11-21T21:00:00-06:00",
            "estadio": "Estadio Universitario",
            "logo_local": "https://golstatsimages.blob.core.windows.net/teams-80/2/1294.png",
            "logo_visitante": "https://golstatsimages.blob.core.windows.net/teams-80/2/1292.png",
        },
    ]

    calendario = []

    for partido in partidos:
        fecha_local = datetime.fromisoformat(partido["fecha_iso"])

        if fecha_local <= ahora:
            continue

        calendario.append({
            "local": partido["local"],
            "visitante": partido["visitante"],
            "fecha": fecha_local.strftime("%d/%m/%Y"),
            "hora": fecha_local.strftime("%I:%M %p"),
            "estadio": partido["estadio"],
            "orden": fecha_local.isoformat(),
            "fecha_local_iso": fecha_local.isoformat(),
            "logo_local": partido["logo_local"],
            "logo_visitante": partido["logo_visitante"],
            "google_calendar_url": crear_enlace_google_calendar(
                partido["local"],
                partido["visitante"],
                fecha_local,
                partido["estadio"],
            ),
        })

    return calendario


# --------------------------------------------------
# PRÓXIMO PARTIDO
# --------------------------------------------------

def partido_por_confirmar():
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


def obtener_proximo_partido():
    calendario = obtener_calendario()

    if calendario:
        return calendario[0]

    return partido_por_confirmar()


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
            "ERROR: No se encontró "
            "DISCORD_WEBHOOK_URL."
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

    partido = (
        calendario[0]
        if calendario
        else partido_por_confirmar()
    )

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
# PRUEBA DE DISCORD
# --------------------------------------------------

@app.get("/probar-alerta")
def probar_alerta():
    partido = obtener_proximo_partido()
    mensaje = crear_mensaje_discord(partido)

    enviado = enviar_alerta(mensaje)

    print(
        "ALERTA DE PRUEBA:",
        "ENVIADA" if enviado else "FALLÓ"
    )

    return RedirectResponse(
        url="/",
        status_code=303
    )


# --------------------------------------------------
# ALERTA AUTOMÁTICA
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